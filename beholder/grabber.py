import logging
import threading
import pkg_resources
from queue import Full
from collections import deque

import cv2
import zmq
import numpy as np

from beholder.defaults import *
from beholder.util import buf_to_numpy

no_signal_path = pkg_resources.resource_filename(__name__, 'resources/no_signal.png')
NO_SIGNAL_FRAME = np.rot90(cv2.imread(no_signal_path))

no_signal_path = pkg_resources.resource_filename(__name__, 'resources/fault.png')
FAULTY_FRAME = np.rot90(cv2.imread(no_signal_path))


class Grabber(threading.Thread):
    def __init__(self, cfg, ctx, arr, target, out_queue, trigger_event, idx=0, transpose=False):
        super().__init__()
        self.id = idx
        self.cfg = cfg
        self.target = 'tcp://{}'.format(target)

        self.name = 'Grabber #{:02d}'.format(self.id)
        logging.info('Initializing ...')

        # Set up source socket
        self.zmq_context = ctx
        self.socket = None
        self.poller = zmq.Poller()

        self.timed_out = False

        self.n_frames = 0
        self.frame = None
        self.last_frame_idx = None

        self.width = cfg['frame_width']
        self.height = cfg['frame_height']
        self.colors = cfg['frame_colors']

        self.n_row = self.id // cfg['n_cols']
        self.n_col = self.id % cfg['n_cols']

        self.transpose = transpose

        # shape = (self.height + FRAME_METADATA_H, self.width, self.colors)
        # num_bytes = int(np.prod(shape))

        self.fault_frame = cv2.resize(FAULTY_FRAME, (self.width, self.height))
        self.no_signal_frame = cv2.resize(NO_SIGNAL_FRAME, (self.width, self.height))

        # Attach to shared buffer
        with arr.get_lock():
            self._shared_arr = arr
            logging.debug('{} shared array: {}'.format(self.name, arr))
            # self._fresh_frame = buf_to_numpy(arr, shape=shape, offset=self.id * num_bytes, count=num_bytes)
            self._fresh_frame = buf_to_numpy(arr, shape=(
                self.height * self.cfg['n_rows'], self.width * self.cfg['n_cols'], 3))
            logging.debug('Numpy shared buffer at {}'.format(hex(self._fresh_frame.ctypes.data)))

        self._write_queue = out_queue
        self._ev_terminate = trigger_event
        self._avg_fps = cfg['frame_fps']
        self._t_loop = deque(maxlen=N_FRAMES_FPS_LOG)

        logging.debug('Grabber initialization done!')

    def run(self):
        # Start up ZMQ connection
        # TODO: Keep attempting to connect
        self.socket = self.zmq_context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, PIEYE_SUB_TOPIC)
        logging.info('Connecting to {}'.format(self.target))
        self.socket.connect(self.target)

        self.poller.register(self.socket, zmq.POLLIN)

        logging.debug('Starting loop in {}!'.format(self.name))
        t0 = cv2.getTickCount()

        # Loop while stop flag not set
        while not self._ev_terminate.is_set():
            # Poll socket for incoming messages, timeout when nothing comes in
            messages = self.poller.poll(SOCKET_RECV_TIMEOUT)
            if len(messages) > 1:
                logging.debug(len(messages))

            if not len(messages):
                # Socket receive timeout, display warning
                if not self.timed_out:
                    self.timed_out = True
                    logging.info('Frame source timeout!')
                # TODO: Fault frames as JPG, so they can be handed over to the writer directly?
                self.frame = self.no_signal_frame

            else:
                # Source reconnected
                if self.timed_out:
                    self.timed_out = False
                    logging.info('Frame source connected')
                for socket, N in messages:
                    encoded_frame = socket.recv()

                    # This for some reason is performance sensitive
                    self.frame = cv2.imdecode(np.fromstring(encoded_frame[13:], dtype='uint8'), cv2.IMREAD_UNCHANGED)
                    frame_idx = int(np.fromstring(encoded_frame[5:13], dtype='uint64'))

                    # For cameras of the bottom row we fliplr/flipud them in the sensor firmware to have the time stamp
                    # on the outside of the frame. We need to reverse that now.
                    if self.transpose:
                        self.frame = cv2.flip(self.frame, -1)

                    # Look at current and previous frame index, check for shenanigans
                    if None not in [frame_idx, self.last_frame_idx]:
                        delta = frame_idx - self.last_frame_idx
                        if delta < 0:
                            logging.warning('Frame source restart? prev: {}, curr: {}, delta: {}'.format(
                                self.last_frame_idx,
                                frame_idx, delta - 1))
                        elif delta > 1:
                            if delta == 2 and not (self.last_frame_idx + 1) % 10000:
                                logging.debug('Intentional frame skip')
                            else:
                                logging.warning('Frame skip? prev: {}, curr: {}, {} frame(s) lost'.format(
                                    self.last_frame_idx,
                                    frame_idx, delta - 1))

                    # Store current frame index
                    self.last_frame_idx = frame_idx

                    if self._write_queue is not None:
                        try:
                            self._write_queue.put(encoded_frame[13:], timeout=.5)
                        except Full:
                            logging.warning('Dropped frame {}'.format(self.last_frame_idx))

            # If no valid frame was decoded even though we did receive something, show a warning
            if self.frame is None:
                self.frame = self.fault_frame

            # # Make space for the metadata bar at the bottom of each frame
            # frame.resize((frame.shape[0] + FRAME_METADATA_H, frame.shape[1], frame.shape[2]))
            # self.frame = Frame(self.n_frames, frame, 'Grabber', add_stamps=self.is_live)

            # Send frames to attached threads/processes
            self.relay_frames()

            self.n_frames += len(messages)

            self._t_loop.appendleft((cv2.getTickCount() - t0) / cv2.getTickFrequency() * 1000)
            t0 = cv2.getTickCount()

            # Every now and then show fps
            # if not self.n_frames % N_FRAMES_FPS_LOG:
            #     avg_fps = 1 / (sum(self._t_loop) / len(self._t_loop))
            #     logging.debug(
            #         'Grabbing frame {}... {}, avg. {:.1f} fps'.format(self.n_frames, 'OK' if rt else 'FAIL', avg_fps))

        logging.debug('Stopping loop in {}!'.format(self.name))
        self.close()

    # def embed_metadata(self, row, label, data):
    #     """Embed metadata into pixels. Note: Data has to be int64-able.
    #     """
    #     line = np.zeros(FRAME_METADATA_BYTE, dtype=np.uint8)
    #     line[0] = np.array([self.id], dtype=np.uint8)
    #     line[1:7] = np.fromstring('{:<6s}'.format(label), dtype=np.uint8)
    #     line[7:] = np.array([data], dtype=np.uint64).view(np.uint8)
    #     self._fresh_frame[-FRAME_METADATA_H + row:-FRAME_METADATA_H + row + 1, \
    # -FRAME_METADATA_BYTE // 3:] = line.reshape(1, -1, 3)

    def relay_frames(self):
        """Forward acquired image to entities downstream via queues or shared array.
        """

        # # FPS display
        # if len(self._t_loop):
        #     fps_str = 'G={:.1f}fps'.format(1000 / (sum(self._t_loop) / len(self._t_loop)))
        # else:
        #     fps_str = 'G=??.?fps'
        # cv2.putText(self.frame.img, fps_str, (270, self.frame.img.shape[0] - 5), FONT, 1.0,
        #             (255, 255, 255), lineType=cv2.LINE_AA)

        # Forward frame for tracking and display
        # NOTE: [:] indicates to reuse the buffer

        # vertical lines
        cv2.line(self.frame, (300, 350), (300, 390), (255, 255, 255), thickness=3)
        cv2.line(self.frame, (300, 410), (300, 450), (255, 255, 255), thickness=3)

        # horizontal lines
        cv2.line(self.frame, (250, 400), (290, 400), (255, 255, 255), thickness=3)
        cv2.line(self.frame, (310, 400), (350, 400), (255, 255, 255), thickness=3)

        # cv2.line(self.frame, (dx, dy), (dx + 600, dy + 800), (255, 255, 255), thickness=1)
        # cv2.line(self.frame, (dx, dy + 800), (dx + 600, dy), (255, 255, 255), thickness=1)
        # cv2.line(self.frame, (dx + 300, dy + 410), (dx + 300, dy + 450), (255, 255, 255), thickness=1)

        try:
            # with self._shared_arr.get_lock():
            self._fresh_frame[
            self.height * self.n_row:self.height * (self.n_row + 1),
            self.width * self.n_col:self.width * (self.n_col + 1), :] = self.frame
        except ValueError as e:
            logging.debug(('VE', self.n_col, self.n_row, self._fresh_frame.shape, e))
            # logging.info('test')
            # self.embed_metadata(row=0, label='index', data=self.frame.index)
            # self.embed_metadata(row=1, label='tickst', data=self.frame.tickstamp)
            # self.embed_metadata(row=2, label='timest', data=int(self.frame.timestamp))

    def close(self):
        pass
