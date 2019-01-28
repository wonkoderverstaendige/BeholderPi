# import io
import logging
import pkg_resources
import socket
import yaml

from random import randint
from time import sleep, time, clock
from datetime import datetime as dt

import numpy as np
import picamera
import zmq

NUM_STREAMS = 4

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')


def get_local_ip():
    local_ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [
        [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
         [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
    return local_ip


class ZMQ_Output:
    """Module for picamera to dump frame buffer into. Sends the encoded frames via ZMQ PUBLISHER."""

    def __init__(self, cfg, camera, context):
        self.camera = camera
        self.cfg = cfg

        # ZMQ setup
        self.zmq_sockets = []
        for n in range(NUM_STREAMS):
            sock = context.socket(zmq.PUB)
            target = 'tcp://*:{port:d}'.format(port=cfg['zmq_output_port'] + n)
            logging.debug('Binding socket at ' + target)
            sock.bind(target)
            self.zmq_sockets.append(sock)

        # # Buffer setup (only needed for `continuous_capture` mode, not in `recording` mode)
        # self.stream = io.BytesIO()

        self.last_write = time()

    def write(self, buf):
        """Callback method invoked by the camera when a complete (encoded) frame arrives."""
        elapsed = (time() - self.last_write) * 1000
        self.last_write = time()
        elapsed_str = "{:.1f} ms, {:.1f} ups ".format(elapsed, 1000 / elapsed)

        # write frame annotation. Frame id is written by the GPU, only write temporal information
        if cfg['camera_annotate_metadata']:
            self.camera.annotate_text = dt.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f') + ' @ ' + elapsed_str

        # Prepare output buffer
        #
        # Prefix with SUBSCRIBE topic and metadata, currently only frame index
        idx = self.camera.frame.index.to_bytes(length=8, byteorder='little', signed=False)

        # TODO: Use multi-part messages instead to avoid the copy?
        # Doesn't seem to take very long though, fraction of a ms
        buf_str = b'PYSPY' + idx + buf

        # For testing purposes drop every n-th frame
        if self.cfg['debug_drop_nth_frame']:
            if not idx % self.cfg['debug_drop_nth_frame']:
                logging.debug('Intended frame drop at index {}'.format(idx))
                return

        # Actually send the buffer to the zmq socket
        #
        # Note that in zmq PUB-SUB pattern, the first few frames will be lost, even if the Subscriber
        # is initialized even before the publisher starts sending out messages. The negotiation of
        # the connection drops those initial messages. Not a problem for us, as recording is handled manually
        # on the subscriber side on a very different time scale.
        for s in self.zmq_sockets:
            s.send(buf_str)


def main(cfg):
    logging.info('Starting piEye @ {}'.format(get_local_ip()))

    with picamera.PiCamera(sensor_mode=cfg['camera_sensor_mode']) as camera, \
            zmq.Context() as context:

        logging.info('Configuring camera')

        # PiCamera setup
        #
        # Sets up everything handled by the ISP and GPU, from acquisition modes to post-processing,
        # rendering and encoding.
        camera.rotation = cfg['camera_rotation']
        camera.resolution = (cfg['frame_width'], cfg['frame_height'])
        camera._preview_alpha = cfg['camera_preview_alpha']
        camera.framerate = cfg['camera_framerate']
        camera.exposure_mode = cfg['camera_exposure_mode']
        camera.vflip = cfg['camera_vflip']
        camera.hflip = cfg['camera_hflip']
        camera.annotate_background = picamera.Color(cfg['camera_annotate_bg_color'])
        camera.annotate_frame_num = cfg['camera_annotate_frame_num']
        camera.annotate_text_size = cfg['camera_annotate_text_size']

        if cfg['camera_preview_enable']:
            logging.debug('Starting Preview')
            camera.start_preview()

        # The capture handling module.
        output = ZMQ_Output(cfg, camera, context)

        # Recording loop
        #
        # when a frame comes in, it is handed to the output module.
        # We have to sue the 'recording' method instead of the continuous capture
        # as frame metadata (index, timestamp) is only available during recording.
        # TODO: A bunch of error handling is missing and taking care of releasing the camera handle
        camera.start_recording(output, format=cfg['camera_recording_format'])
        while True:
            try:
                camera.wait_recording(1)
            except KeyboardInterrupt:
                break

        camera.stop_recording()
        camera.stop_preview()


if __name__ == '__main__':
    # Load configuration data.
    # TODO: Argparse to load different configurations specified as command line parameters
    cfg_path = pkg_resources.resource_filename(__name__, 'resources/config_pieye_default.yml')
    with open(cfg_path, 'r') as cfg_f:
        cfg = yaml.load(cfg_f)

    main(cfg)
