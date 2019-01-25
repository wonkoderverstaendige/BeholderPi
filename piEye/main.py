import io
import picamera
import numpy as np

from time import sleep, time, clock
from datetime import datetime as dt
import zmq

import logging

import socket


NUM_STREAMS = 4


def get_local_ip():
    local_ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [
        [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
         [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
    return local_ip


def send_image(buf, s):
    # TODO: This requires copying the whole buffer?

    buf_str = b'PYSPY' + buf.getvalue()
    s.send(buf_str)


class ZMQ_Output:
    def __init__(self, camera):
        self.camera = camera

        # ZMQ setup
        self.zmq_sockets = []
        for n in range(NUM_STREAMS):
            sock = context.socket(zmq.PUB)
            target = 'tcp://*:{port:d}'.format(port=5555 + n)
            sock.bind(target)
            logging.debug('Socket bound at ' + target)
            self.zmq_sockets.append(sock)

        # Buffer setup
        self.stream = io.BytesIO()

        self.last_write = time()

    def write(self, buf):
        elapsed = (time() - self.last_write) * 1000
        self.last_write = time()
        elapsed_str = "{:.1f} ms, {:.1f} ups ".format(elapsed, 1000 / elapsed)
        camera.annotate_text = dt.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f') + ' @ ' + elapsed_str

        idx = np.array(self.camera.frame.index, dtype='uint64')
        buf_str = b'PYSPY' + idx.tobytes() + buf

        for s in self.zmq_sockets:
            s.send(buf_str)


logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')
logging.info('Starting piEye @ {}'.format(get_local_ip()))

with picamera.PiCamera(sensor_mode=4) as camera, zmq.Context() as context:
    logging.info('Configuring camera')
    # PiCamera setup
    camera.resolution = (480, 640)
    camera.rotation = 90
    camera._preview_alpha = 200
    camera.framerate = 20
    camera.exposure_mode = 'sports'
#    camera.vflip = True
#    camera.hflip = True
    camera.annotate_background = picamera.Color('black')
    camera.annotate_frame_num = True
    camera.annotate_text_size = 16

    logging.debug('Starting Preview')
    camera.start_preview()

    output = ZMQ_Output(camera)

    camera.start_recording(output, format='mjpeg')
    while True:
        try:
            camera.wait_recording(1)
        except KeyboardInterrupt:
            break

    # # ZMQ setup
    # zmq_sockets = []
    # for n in range(NUM_STREAMS):
    #     sock = context.socket(zmq.PUB)
    #     target = 'tcp://*:{port:d}'.format(port=5555 + n)
    #     sock.bind(target)
    #     logging.debug('Socket bound at ' + target)
    #     zmq_sockets.append(sock)
    #
    # # Buffer setup
    # stream = io.BytesIO()

    # last = time()
    # for image in camera.capture_continuous(stream, format='jpeg', use_video_port=True):
    #     logging.info(camera.frame.index)
    #     elapsed = (time() - last) * 1000
    #     last = time()
    #     elapsed_str = "{:.1f} ms, {:.1f} ups ".format(elapsed, 1000 / elapsed)
    #     camera.annotate_text = dt.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f') + ' @ ' + elapsed_str
    #
    #     # TODO: Check if multiple images in stream!
    #     stream.truncate()
    #     kB = stream.tell() / 1000
    #     if kB > 230:
    #         print(kB, 'kB in buffer!')
    #
    #     stream.seek(0)
    #     for zs in zmq_sockets:
    #         send_image(stream, zs)
    camera.stop_preview()
