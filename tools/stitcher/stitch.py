import numpy as np
import cv2
from pathlib import Path

videos_path = Path('~/src/BeholderPi/beholder/img/').expanduser().resolve()

ts = '2019-02-17_17-53-02'

images = []
for n, img_path in enumerate(sorted(videos_path.glob(ts + '_eye*.png'))):
    images.append(cv2.imread(str(img_path)))

stitcher = cv2.Stitcher_create(True)
(status, stitched) = stitcher.stitch(images)

stitched = np.rot90(cv2.flip(cv2.flip(stitched, 1), 0))

# if the status is '0', then OpenCV successfully performed image
# stitching
if status == 0:
    # write the output stitched image to disk
    cv2.imwrite('test.png', stitched)

    # display the output stitched image to our screen
    cv2.imshow("Stitched", stitched)
    cv2.waitKey(0)

# otherwise the stitching failed, likely due to not enough keypoints)
# being detected
else:
    print("[INFO] image stitching failed ({})".format(status))
