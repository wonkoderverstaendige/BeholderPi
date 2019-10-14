import argparse
import math
from pathlib import Path

import cv2
import numpy as np
from tqdm import trange

GLOB_STR_OLD = '*_eye??.mp4'
GLOB_STR_NEW = 'eye??_*.mp4'


def assemble(frames, crop_x=104, crop_y=91, n_rows=2):
    if not all(frames):
        print('Missing frame?')
        return

    frame_shape = next(iter(frames.values())).shape
    h, w, d = frame_shape
    ch = h - crop_y
    cw = w - 2 * crop_x

    n_slots = len(frames) + len(missing)
    n_cols = math.ceil(n_slots / n_rows)

    stitched_rows = [np.zeros(shape=(ch, n_cols * cw, d), dtype=np.uint8) for n in range(n_rows)]

    for row in range(n_rows):
        for col in range(n_cols):
            stitched = stitched_rows[row]
            n = n_cols * row + col
            #             print(f'n={n}, row={row}, col={col}, missing={n not in frames}')

            # Available frame
            if n in frames:
                f = frames[n]
                fc = f[:h - crop_y, crop_x:w - crop_x, :]
                if row % 2:
                    fc = np.flip(fc, (0, 1))
                stitched[:, col * cw:(col + 1) * cw, :] = fc

            # Missing frame
            else:
                # there's at least one before this row
                if row > 0:
                    raise NotImplementedError('Not looking at previous row')

                # there's one to the left
                if n % n_cols:
                    fc = frames[n - 1][:-crop_y, -crop_x:, :]
                    if row:
                        fc = np.flip(fc, (0, 1))
                    stitched[:, col * cw:col * cw + crop_x, :] = fc

                # there's one to the right
                if col + 1 != n_cols:
                    fc = frames[n + 1][:-crop_y, :crop_x, :]
                    if row:
                        fc = np.flip(fc, (0, 1))
                    stitched[:, (col + 1) * cw - crop_x:(col + 1) * cw, :] = fc

                # there's a row after this one
                if row + 1 <= n_rows:
                    fc = frames[n + n_cols][h - crop_y:, crop_x:-crop_x, :]
                    if not row:
                        fc = np.flip(fc, (0, 1))
                    stitched[ch - crop_y:, col * cw:(col + 1) * cw, :] = fc

    # stitch it all up
    full_stitched = np.zeros(shape=(n_rows * ch, n_cols * cw, d), dtype=np.uint8)
    for n, row in enumerate(stitched_rows):
        h = row.shape[0]
        full_stitched[n * h:(n + 1) * h, :, :] = row

    return full_stitched


if __name__ == '__main__':
    parser = argparse.ArgumentParser('RatHexMaze video view combiner - REPAIR MODE')
    parser.add_argument('paths', help='Paths to video set', nargs='+')
    parser.add_argument('-cx', type=int, default=104, help='Horizontal crop per view (default: %(default)s)')
    parser.add_argument('-cy', type=int, default=91, help='Vertical crop per view (default: %(default)s)')
    parser.add_argument('-rows', type=int, default=2, help='Number of rows to distribute views over')
    parser.add_argument('-n', '--n_videos', default=12, type=int,
                        help='Number of videos to expect. Checks glob result (default: %(default)s)')
    parser.add_argument('-D', '--dry_run', help='Do not launch process, only print the command.', action='store_true')
    parser.add_argument('-g', '--glob', help='Video file glob (default: "%(default)s")', default=GLOB_STR_NEW)

    cli_args = parser.parse_args()

    for path in cli_args.paths:
        vid_dir = Path(path).resolve()
        if not vid_dir.exists():
            print('Could not find video path {}, SKIPPING!'.format(path))

        vid_paths = sorted(list(vid_dir.glob(GLOB_STR_NEW)))
        out_path = vid_dir / 'stitched_repair.mp4'

        eye_ids = [int(vp.name[3:5]) - 1 for vp in vid_paths]
        sources = dict(zip(eye_ids, vid_paths))
        missing = [n for n in range(0, 12) if n + 1 not in eye_ids]
        print('Missing cameras: {}'.format(missing))

        captures = dict(zip(eye_ids, [cv2.VideoCapture(str(vp)) for vp in vid_paths]))
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*'MP42'), 30., (2352, 1418))

        n_frames = [int(c.get(cv2.CAP_PROP_FRAME_COUNT)) for c in captures.values()]
        print(n_frames)

        for n in trange(min(n_frames)):
            frames = {eid: c.read()[1] for eid, c in captures.items()}
            stitched = assemble(frames)
            writer.write(stitched)
