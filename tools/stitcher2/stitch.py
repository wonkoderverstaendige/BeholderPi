import argparse
import logging
from pathlib import Path

import cv2
import math
import numpy as np
from tqdm import tqdm


def add_merge(img1, img2, mask, blur=False, inplace=True):
    if blur:
        print(mask.shape, mask.dtype)
        mask = cv2.GaussianBlur(mask.astype('float'), (3, 3), 0)

    if inplace:
        img1 += img2 * mask
    else:
        merged = img1 + img2 * mask
        return merged


class SourceView:
    def __init__(self, path, out_h, out_w, delay=0, skip=0):
        self.path = Path(path).resolve()
        self.__capture = None
        self.out_h, self.out_w = out_h, out_w
        self.img = None
        self.corrected = None
        self.mask = None
        self.delay = delay
        self.num_frames = 99999999999999999999999999
        self.frame_n = 0
        self.skip = skip

        # Create capture object if it's a video, else return always the same image.
        if self.path.suffix.lower() in ['.avi', '.mp4']:
            logging.debug(f'Source {self.path} seems to be a video file')
            self.__capture = cv2.VideoCapture(str(self.path))
            self.num_frames = int(self.__capture.get(cv2.CAP_PROP_FRAME_COUNT))

            # Skip the first n frames
            if self.delay:
                logging.debug(f'Skipping {self.delay} frames on source {self.path}')
                for n in range(self.delay):
                    self.__capture.read()

        elif source_path.suffix.lower() in ['.png', '.jpg', 'jpeg', '.bmp']:
            logging.debug(f'Source {self.path} seems to be an image file')
        else:
            raise NotImplementedError(f'File ending of source {self.path} unknown.')

        # Load homography matrix
        with open(self.path.with_suffix('.transformation.csv'), 'r') as tf:
            self.transformation = np.array(list(map(float, tf.readline().split(',')))).reshape(3, 3)
        logging.debug(f'Homography matrix: {self.transformation}')


    def next(self, initial=False):
        if self.__capture is None:
            img = cv2.imread(str(self.path))
        else:
            _, img = self.__capture.read()
            self.frame_n += 1
        if self.skip and not self.frame_n % self.skip:
            logging.debug('Skipping Frame!')
            _, img = self.__capture.read()

        if img is None:
            logging.debug(f'Could not read a valid image from source {self.path}')
            return False

        self.img = img
        self.corrected = cv2.warpPerspective(img, self.transformation, (self.out_h, self.out_w))

        if self.mask is None:
            self.mask = self.fix_mask(np.sum((self.corrected > 0).astype('uint8'), axis=2))

        return True

    @staticmethod
    def fix_mask(mask):
        """Get outline of a mask, fix smaller holes """
        contours, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        areas = np.array([cv2.contourArea(cnt) for cnt in contours])
        mask_outline = np.zeros((mask.shape[0], mask.shape[1], 3), dtype='uint8')
        cv2.drawContours(mask_outline, contours, np.argmax(areas), (1, 0, 0), maxLevel=0, thickness=-1)

        morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
        mask_outline = cv2.morphologyEx(mask_outline, cv2.MORPH_CLOSE, morph_kernel, iterations=2)

        return np.sum(mask_outline, axis=2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('sources', nargs="*",
                        help='List of path to camera view video files. If the string contains a wildcard character,'
                             'it will be used as a glob instead.')
    parser.add_argument('--target', help='Path to target alignment image for size estimation')
    parser.add_argument('--size', help='comma separated output image size')
    parser.add_argument('-v', '--verbose', help='Log debug messages', action='store_true')
    parser.add_argument('-N', '--num_frames', type=int, help='Limit to number of frames to extract, default=all',
                        default=0)
    parser.add_argument('--offsets', nargs='*', help='List of start offsets in frames per target')
    parser.add_argument('--skip', nargs='*', help='List of nth frames to skip for frame drift compensation')
    parser.add_argument('--preview', action='store_true', help='Show merged frames preview')
    parser.add_argument('--cropx', nargs=2, type=int, help='crop left and right', default=(0, 0))
    parser.add_argument('--cropy', nargs=2, type=int, help='crop top and bottom', default=(0, 0))
    parser.add_argument('--dry', action='store_true', help='Do not write to disk')

    cli_args = parser.parse_args()

    log_level = logging.DEBUG if cli_args.verbose else logging.INFO
    logging.basicConfig(level=log_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # find sources
    source_paths = []
    for source_path in map(Path, cli_args.sources):
        if '*' in source_path.name or '?' in source_path.name:
            src_expand = list(source_path.parent.glob(source_path.name))
            source_paths.extend(src_expand)
        else:
            source_paths.append(source_path)
    assert all([sp.exists() for sp in source_paths])

    # Skip files that do not have a transformation matrix calculated
    source_paths = [sp for sp in source_paths if sp.with_suffix('.transformation.csv').exists()]

    if cli_args.offsets is not None:
        assert len(cli_args.offsets) == len(source_paths)
        offsets = list(map(int, cli_args.offsets))
    else:
        offsets = [0 for n in range(len(source_paths))]
    logging.debug(f'Frame source delays: {offsets}')

    logging.debug(f'Found {len(source_paths)} video files.')
    print(source_paths)

    if cli_args.target:
        out_img = np.zeros_like(cv2.imread(str(Path(cli_args.target).resolve().as_posix())), dtype='float')
        out_h, out_w, _ = out_img.shape

    elif cli_args.size:
        out_h, out_w = cli_args.size.split(',') if ',' in cli_args.size else cli_args.size.split('x')
        out_img = np.zeros((out_w, out_h, 3), dtype=float)
    else:
        raise ValueError('Need either a target image or explicit size information to know output image size.')
    logging.info(f'Output image size: {out_w}px x {out_h}px, {out_img.shape}')

    # Skip parameter, skipping every nth frame per source.
    if cli_args.skip is not None:
        assert(len(cli_args.skip) == len(source_paths))
        skip = list(map(int, cli_args.skip))
    else:
        skip = [0 for n in range(len(source_paths))]
    logging.debug(f'Frame skips: {skip}')


    # Create Source instances
    sources = []
    for sn, sp in enumerate(source_paths):
        delay = 0 if offsets is None else int(offsets[sn])
        sv = SourceView(sp, out_w=out_h, out_h=out_w, delay=delay, skip=skip[sn])
        sources.append(sv)

    if not (len(sources)):
        raise FileNotFoundError('No valid source files found. Stopping.')

    mask = None

    key = -1
    num_frames = min([source.num_frames - source.delay for source in sources])
    if cli_args.num_frames:
        num_frames = min(cli_args.num_frames, num_frames)

    outdir = Path('./tmp').resolve()
    if not outdir.exists():
        outdir.mkdir(parents=True)

    cx = cli_args.cropx
    cy = cli_args.cropy
    logging.debug(f'Cropping in x: {cx}, cropping in y: {cy}')

    with tqdm(total=num_frames) as pbar:
        N = 0
        while key == -1:
            if cli_args.preview:
                key = cv2.waitKey(1)

            # advance all sources, check if an image was returned
            for sn, source in enumerate(sources):
                rv = source.next()
                if not rv:
                    key = ord('q')

            if mask is None:
                logging.debug('Calculating mask')
                mask = np.zeros((out_h, out_w), dtype='float')
                for source in sources:
                    mask += source.mask
                mask[mask == 0] = 1.
                mask = 1 / mask
                mask = mask[:, :, None]

            out_img[:] = 0
            for src in sources:
                add_merge(out_img, src.corrected, mask, inplace=True)

            if cli_args.preview:
                cv2.imshow('Merged', out_img[cy[0]:out_h - cy[1], cx[0]:out_w - cx[1], :].astype('uint8'))

            digits = str(math.ceil(math.log(num_frames, 10)))
            fmt = 'images{N:0' + digits + 'd}.png'

            # Write merged frames to disk
            if not cli_args.dry:
                cv2.imwrite(str(outdir / fmt.format(N=N)), out_img[cy[0]:out_h - cy[1], cx[0]:out_w - cx[1], :])

            pbar.update(1)
            N += 1

            # Check for frame extraction limit
            if cli_args.num_frames and N >= cli_args.num_frames:
                logging.debug('Reached maximum amount of frames to extract. Stopping.')
                key = ord('q')

            outfile = outdir / ('images%0'+digits+'d.png')
    logging.info(f'Join frames together with "ffmpeg -r 15 -f image2 -i {str(outfile)} -c:v libx264 -crf'
                 ' 18 -r 15 aligned_stitch.mp4"')
