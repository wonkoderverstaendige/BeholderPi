from imutils.video import VideoStream
from pyzbar import pyzbar

import imutils
import time

# initialize the video stream and allow the camera sensor to warm up
print("[INFO] starting video stream...")

vs = VideoStream(usePiCamera=True).start()
time.sleep(0.2)


while True:
    frame = vs.read()
    frame = imutils.resize(frame, width=400)

    barcodes = pyzbar.decode(frame)

    for barcode in barcodes:
        bc_data = barcode.data.decode('utf-8')
        bc_type = barcode.type

        bc_text = "{} ({})".format(bc_data, bc_type)
        print(bc_text)
