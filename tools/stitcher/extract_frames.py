import numpy as np
from pathlib import Path
import cv2

videos_path = Path('~/src/BeholderPi/beholder/img/').expanduser().resolve()

ts = '2019-02-17_17-58-46'

# Prepare Images
images = []
for n, vid_path in enumerate(sorted(videos_path.glob(ts + '_eye*.mp4'))):
    img_path = vid_path.with_suffix('.png')
    capture = cv2.VideoCapture(str(vid_path))
    rt, frame = capture.read()
    if n > 5:
        frame = cv2.flip(cv2.flip(frame, 1), 0)

    if rt:
        cv2.imwrite(str(img_path), frame)

    images.append(frame)
    print(img_path)
    capture.release()

