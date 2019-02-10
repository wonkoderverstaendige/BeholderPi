import io
import time
import picamera
from PIL import Image
from pyzbar import pyzbar

# Create the in-memory stream
stream = io.BytesIO()
with picamera.PiCamera() as camera:
    camera.start_preview()
    while True:
        camera.capture(stream, format='jpeg')

        # "Rewind" the stream to the beginning so we can read its content
        stream.seek(0)
        image = Image.open(stream)

        barcodes = pyzbar.decode(image)

        for barcode in barcodes:
            bc_data = barcode.data.decode('utf-8')
            bc_type = barcode.type

            bc_text = "{} ({})".format(bc_data, bc_type)
            print(bc_text)

