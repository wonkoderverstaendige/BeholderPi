import argparse
import colorsys
import logging
import random
from pathlib import Path

import cv2
import numpy as np

REWIND_MSG = False


def random_rgb():
    h, s, l = random.random(), 0.5 + random.random() / 2.0, 0.4 + random.random() / 5.0
    r, g, b = [int(256 * i) for i in colorsys.hls_to_rgb(h, l, s)]
    return r, g, b


def rgb2hex(r, g, b):
    return hex(r * 255 * 255 + g * 255 + b)


def hex2rgb(hx):
    return tuple(int(hx[i:i + 2], 16) for i in (0, 2, 4))


def calculate_h(pairs):
    """Calculate homograpy matrix from lists of origin and destination points"""
    src_pts = [p[0] for p in pairs]
    dst_pts = [p[1] for p in pairs]

    # TODO: Try alternative approximation algorithms
    h, status = cv2.findHomography(np.array(src_pts), np.array(dst_pts))
    return h


def correct_image(img, corr_mat, width, height):
    return cv2.warpPerspective(img, corr_mat, (height, width))


class CameraView:
    def __init__(self, path, name, target, color=(255, 0, 255)):
        self.path = path
        self.target = target
        self.pairs = []
        self.color = color
        self.name = name
        self.capture = cv2.VideoCapture(str(self.path))
        rv, src_img = self.capture.read()
        if not rv:
            raise IOError(f'Could not read image from source {self.path}')
        self.img = src_img
        self.window = cv2.namedWindow(self.name)
        cv2.imshow(self.name, self.img)
        cv2.setMouseCallback(self.name, self.clicked)

        self.corrected = (0.3 * self.target.img.copy()).astype('uint8')
        self.preview_window = cv2.namedWindow(self.name + " corrected")

        self.h = None

    def clicked(self, event, x, y, flags, params):
        if event == cv2.EVENT_LBUTTONDBLCLK:
            if self.target.last_click is None:
                return
            tx, ty, tc = self.target.last_click
            self.pairs.append([(x, y), (tx, ty), tc])
            self.target.last_click = None
        if len(self.pairs) >= 3:
            self.h = calculate_h(self.pairs)
            preview = self.target.img * 0.3 + correct_image(self.img, self.h, self.target.h, self.target.w) * 0.7
            self.corrected = preview.astype('uint8')

    def read(self, retry_attempt=0):
        if retry_attempt > 10:
            raise IOError(f'Could not read from source {self.path}')

        rv, img = self.capture.read()
        if not rv:
            if REWIND_MSG:
                logging.debug('Unable to read, rewinding')
            self.rewind()
            self.read(retry_attempt + 1)
        else:
            self.img = img

    def update(self):
        self.read()
        for pair in self.pairs:
            cv2.circle(self.img, pair[0], 4, pair[2], -1)

        cv2.imshow(self.name, self.img)
        cv2.imshow(self.name + " corrected", self.corrected)

    def rewind(self):
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0.0)

    def save_state(self):
        with open(self.path.with_suffix('.align.csv'), 'w') as of:
            logging.info(f'Writing point pairs of {self.name} to {of}')
            of.write('target_x, target_y, maze_x, maze_y, color\n')
            for t_pos, c_pos, color in self.pairs:
                line = f'{t_pos[0]}, {t_pos[1]}, {c_pos[0]}, {c_pos[1]}, {rgb2hex(*color)}\n'
                of.write(line)

        with open(self.path.with_suffix('.transformation.csv'), 'w') as of:
            of.write(','.join(map(str, list(self.h.flatten()))))

        # write self labels image
        cv2.imwrite(str(self.path.with_suffix('.align.png')), self.img)

        # write target labels image
        cv2.imwrite(str(self.path.with_suffix('.target.png')), self.target.img)

        # write preview image
        cv2.imwrite(str(self.path.with_suffix('.preview.png')), self.corrected)


class Target:
    def __init__(self, path):
        self.path = path
        img_path = str(self.path.as_posix())
        img = cv2.imread(img_path)
        if img is None:
            raise IOError(f'Could not load target alignment image {path}')
        self.img = img
        self.h, self.w, _ = self.img.shape
        self.original = self.img.copy()
        self.name = 'Target'

        # present still images
        self.window = cv2.namedWindow(self.name)
        cv2.setMouseCallback(self.name, self.clicked)
        self.last_click = None
        self.update()

    def clicked(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDBLCLK:
            color = random_rgb()
            self.last_click = (x, y, color)
            cv2.circle(self.img, (x, y), 7, color, -1)

        if event == cv2.EVENT_MBUTTONDOWN:
            self.last_click = None
            self.img = self.original.copy()

    def update(self):
        cv2.imshow(self.name, self.img)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', help='Path to camera view video file.')
    parser.add_argument('--target', help='Path to target alignment image', default='data/alignment_target.png')
    parser.add_argument('-v', '--verbose', help='Log debug messages', action='store_true')

    cli_args = parser.parse_args()

    log_level = logging.DEBUG if cli_args.verbose else logging.INFO
    logging.basicConfig(level=log_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Load alignment target image
    target_path = Path(cli_args.target).resolve()
    if not target_path.exists():
        raise FileNotFoundError(f'Could not find alignment target image {target_path}')
    logging.debug(f'Using alignment target {target_path}')
    target_view = Target(target_path)

    source_path = Path(cli_args.source).resolve()
    num_cam = int(source_path.stem[-1])
    source_view = CameraView(source_path, f'Camera{num_cam:01d}', target=target_view)

    while True:
        key = cv2.waitKey(60)

        source_view.update()
        target_view.update()

        if key == -1:
            continue

        logging.debug(f'key: {key}, char: {chr(key)}')
        if chr(key) == 'q':
            break

        if chr(key) == 's':
            source_view.save_state()
