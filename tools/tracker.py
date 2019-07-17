import argparse
import math
from pathlib import Path

import cv2
import numpy as np
import subprocess as sp

KERNEL_5 = np.ones((5, 5))
KERNEL_3 = np.ones((3, 3))

FFMPEG_BINARY = 'ffmpeg'
FFMPEG_COMMAND = [FFMPEG_BINARY,
                  '-y', '-hide_banner', '-nostats',
                  '-loglevel', 'error',

                  '-pix_fmt', 'bgr24',
                  '-f', 'rawvideo',
                  '-vcodec', 'rawvideo',
                  '-s', '2352x1418',
                  '-r', '30.',
                  '-i', '-',

                  '-c:v', 'libx264',
                  '-preset', 'slow',
                  '-pix_fmt', 'yuvj420p',
                  '-vf', 'hqdn3d']


class KalmanFilter:
    def __init__(self):
        self.kf = cv2.KalmanFilter(4, 2)
        self.kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                              [0, 1, 0, 0]], dtype=np.float32)

        self.kf.transitionMatrix = np.array([[1, 0, 1, 0],
                                             [0, 1, 0, 1],
                                             [0, 0, 1, 0],
                                             [0, 0, 0, 1]], dtype=np.float32)

        self.kf.processNoiseCov = np.array([[1, 0, 0, 0],
                                            [0, 1, 0, 0],
                                            [0, 0, 1, 0],
                                            [0, 0, 0, 1]], np.float32) * 1

    def correct(self, x, y):
        self.kf.correct(np.array([x, y], dtype=np.float32))

    def predict(self):
        return self.kf.predict()


def centroid(cnt):
    """Centroid of an OpenCV contour"""
    m = cv2.moments(cnt)
    cx = int(m['m10'] / m['m00'])
    cy = int(m['m01'] / m['m00'])
    return cx, cy


def distance(x1, y1, x2, y2):
    """Euclidean distance."""
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser('RatHexMaze offline Tracker')
    parser.add_argument('path', help='Path to video')
    parser.add_argument('-m', '--mask', help='Path to mask image')

    cli_args = parser.parse_args()
    video_path = Path(cli_args.path).resolve()
    capture = cv2.VideoCapture(str(video_path))
    capture.set(cv2.CAP_PROP_POS_MSEC, 35000)

    mask_path = Path(str(cli_args.mask))
    mask = np.flipud(np.rot90(cv2.imread(str(mask_path), 0)))

    fgbg = cv2.createBackgroundSubtractorMOG2(detectShadows=True, varThreshold=20)

    kf = KalmanFilter()

    n = 0

    ffmpeg_cmd = FFMPEG_COMMAND + ['tracker_demo.mp4']
    writer_pipe = sp.Popen(ffmpeg_cmd, stdin=sp.PIPE)

    while True:
        ret, frame = capture.read()
        if not ret:
            break
        nf = cv2.bitwise_and(frame, frame, mask=mask)
        fg_mask = fgbg.apply(nf)
        fg_mask_clean = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, KERNEL_3)

        _, thresh = cv2.threshold(fg_mask_clean, 254, 255, cv2.THRESH_BINARY)

        contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        disp_frame = nf

        # find largest contour
        largest_cnt, largest_area = None, 0
        sum_area = 0
        for cnt in contours:
            area = int(cv2.contourArea(cnt))
            if area > 50:
                sum_area += area
                if area > largest_area:
                    largest_area = area
                    largest_cnt = cnt

        if largest_cnt is not None:
            cx, cy = centroid(largest_cnt)
            print(cx, cy, largest_area)
            cv2.drawContours(disp_frame, [largest_cnt], 0, (0, 0, 255), 2)
            kf.correct(cx, cy)

        kf_res = kf.predict()
        kfx = min(max(0, int(kf_res[0])), frame.shape[1])
        kfy = min(max(0, int(kf_res[1])), frame.shape[0])

        cv2.drawMarker(disp_frame, position=(kfx, kfy), color=(255, 128, 255), markerSize=20, thickness=3)

        # cv2.imshow('masked', disp_frame)
        # cv2.imshow('frame', fg_mask_clean)

        writer_pipe.stdin.write(disp_frame.tostring())

        key = cv2.waitKey(1)
        if key == 27 or key == ord('q'):
            break

    capture.release()
    cv2.destroyAllWindows()
    writer_pipe.stdin.close()
    writer_pipe.wait()
