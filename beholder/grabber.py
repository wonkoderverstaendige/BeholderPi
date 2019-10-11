import logging
import threading
import pkg_resources
from queue import Full
from collections import deque, defaultdict

import cv2
import zmq
import numpy as np
import datetime as dt

from beholder.defaults import *
from beholder.util import buf_to_numpy

no_signal_path = pkg_resources.resource_filename(__name__, 'resources/no_signal.png')
NO_SIGNAL_FRAME = np.rot90(cv2.imread(no_signal_path))

no_signal_path = pkg_resources.resource_filename(__name__, 'resources/fault.png')
FAULTY_FRAME = np.rot90(cv2.imread(no_signal_path))


class Grabber(threading.Thread):
    def __init__(self, cfg, ctx, arr, target, out_queue, trigger_event, main_thread, idx=0, transpose=False):
        super().__init__()
        self.id = idx
        self.cfg = cfg
        self.target = 'tcp://{}'.format(target)

        self.name = 'Grabber #{:02d}'.format(self.id)
        logging.debug(f'{self.name} Initializing ...')

        # Set up source socket
        self.zmq_context = ctx
        self.socket = None
        self.poller = zmq.Poller()

        self.timed_out = False
        self.faulted = False

        self.n_frames = 0
        self.frame = None
        self.last_frame_idx = None

        self.width = cfg['frame_width']
        self.height = cfg['frame_height']
        self.colors = cfg['frame_colors']

        self.n_row = self.id // cfg['n_cols']
        self.n_col = self.id % cfg['n_cols']

        self.crop_x = cfg['frame_crop_x']
        self.crop_y = cfg['frame_crop_y']
        self.crop_w = self.width - 2 * self.crop_x
        self.crop_h = self.height - self.crop_y

        self.transpose = transpose

        self.fault_frame = cv2.resize(FAULTY_FRAME, (self.width, self.height))
        self.no_signal_frame = cv2.resize(NO_SIGNAL_FRAME, (self.width, self.height))

        self.parent = main_thread

        # Attach to shared buffer
        with arr.get_lock():
            self._shared_arr = arr
            logging.debug('{} shared array: {}'.format(self.name, arr))
            self._fresh_frame = buf_to_numpy(arr, shape=self.cfg['shared_shape'])
            logging.debug('Numpy shared buffer at {}'.format(hex(self._fresh_frame.ctypes.data)))

        # self.__ff_view = self._fresh_frame[self.height * self.n_row:self.height * (self.n_row + 1),
        #                                    self.width * self.n_col:self.width * (self.n_col + 1), :]

        self._write_queue = out_queue
        self._ev_terminate = trigger_event
        self._avg_fps = cfg['frame_fps']
        self._t_loop = deque(maxlen=N_FRAMES_FPS_LOG)

        logging.debug('Grabber initialization done!')

    @staticmethod
    def get_metadata(md):
        if md is None:
            metadata = defaultdict(lambda: None)
        else:
            md = np.fromstring(md, dtype=PIEYE_METADATA_DTYPE)
            metadata = dict(zip(md.dtype.names, md[0]))
            metadata['name'] = metadata['name'].decode().strip()

        return metadata

    def run(self):
        # Start up ZMQ connection
        # TODO: Keep attempting to connect
        self.socket = self.zmq_context.socket(zmq.SUB)
        self.socket.setsockopt(zmq.SUBSCRIBE, PIEYE_SUB_TOPIC)
        logging.debug('Connecting to {}'.format(self.target))
        self.socket.connect(self.target)

        self.poller.register(self.socket, zmq.POLLIN)

        logging.debug('Starting loop in {}!'.format(self.name))
        t0 = cv2.getTickCount()

        annotate = False
        _frame_format_deprecation_warned = False
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
                    logging.info('Frame source (re)connected')
                    self.timed_out = False

                for socket, N in messages:
                    self.faulted = False

                    msg = socket.recv_multipart()
                    recv_clock_ts = dt.datetime.utcnow().timestamp()

                    # Handle metadata
                    # OLD FORMAT (single zmq message, topic:timestamp:frame
                    if len(msg) < 3:
                        metadata = self.get_metadata(None)
                        encoded_frame = msg[0][13:]
                        if not _frame_format_deprecation_warned:
                            logging.warning('Deprecated frame format received. Update eye at {}'.format(self.target))
                            _frame_format_deprecation_warned = True
                        metadata['frame_index'] = int.from_bytes(msg[0][5:13], byteorder='little')

                    # New format
                    else:
                        metadata = self.get_metadata(msg[1])
                        encoded_frame = msg[2]

                    metadata['recv_clock_ts'] = recv_clock_ts
                    metadata['bytes'] = len(encoded_frame)
                    frame_idx = metadata['frame_index']

                    if self._write_queue is not None:
                        try:
                            self._write_queue.put_nowait([metadata, encoded_frame])
                        except Full:
                            logging.warning('Write queue full! Dropping frame {}'.format(frame_idx))

                    # This for some reason is performance sensitive
                    self.frame = cv2.imdecode(np.fromstring(encoded_frame, dtype='uint8'), cv2.IMREAD_UNCHANGED)

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
                            # Initial debugging has every 10000th frame being intentionally drop to check for
                            # reliable frame skip detection
                            if delta == 2 and not (self.last_frame_idx + 1) % 10000:
                                logging.debug('Intentional frame skip')
                            else:
                                logging.warning('Frame skip! prev: {}, curr: {}, {} frame(s) lost'.format(
                                    self.last_frame_idx,
                                    frame_idx, delta - 1))

                    # Store current frame index
                    self.last_frame_idx = frame_idx

            # If no valid frame was decoded even though we did receive something, show a warning
            if self.frame is None:
                self.faulted = True
                self.frame = self.fault_frame

            if not self.timed_out and not self.faulted:
                self.annotate_frame()

            # Send frames to attached threads/processes
            self.relay_frames()

            self.n_frames += len(messages)

            self._t_loop.appendleft((cv2.getTickCount() - t0) / cv2.getTickFrequency() * 1000)
            t0 = cv2.getTickCount()

        logging.debug('Stopping loop in {}!'.format(self.name))
        self.close()

    def annotate_frame(self):
        pass
        # # vertical lines
        # ch_color = (0, 0, 0)
        # th_thickness = 1
        # cv2.line(self.frame, (300, 350), (300, 390), ch_color, thickness=th_thickness)
        # cv2.line(self.frame, (300, 410), (300, 450), ch_color, thickness=th_thickness)
        #
        # # horizontal lines
        # cv2.line(self.frame, (250, 400), (290, 400), ch_color, thickness=th_thickness)
        # cv2.line(self.frame, (310, 400), (350, 400), ch_color, thickness=th_thickness)

        # cv2.putText(self.frame, f'{frame_idx}', (200, 120), fontFace=cv2.FONT_HERSHEY_PLAIN, fontScale=1.1,
        #             color=(0, 0, 0), thickness=2, lineType=cv2.LINE_AA)
        # cv2.putText(self.frame, f'{frame_idx}', (200, 120), fontFace=cv2.FONT_HERSHEY_PLAIN, fontScale=1.1,
        #             color=(255, 255, 255), thickness=1, lineType=cv2.LINE_AA)

    def relay_frames(self):
        """Forward acquired image to entities downstream via queues or shared array.
        """
        # Forward frame for tracking and display
        try:
            # with self._shared_arr.get_lock():
            # self._fresh_frame[self.height * self.n_row:self.height * (self.n_row + 1),
            # self.width * self.n_col:self.width * (self.n_col + 1), :] = self.frame

            fc_lim_M = (self.crop_y, self.crop_y + self.crop_h) if self.n_row else (0, self.crop_h)
            fc_lim_N = (self.crop_x, self.crop_w + self.crop_x)

            self._fresh_frame[self.crop_h * self.n_row:self.crop_h * (self.n_row + 1),
            self.crop_w * self.n_col:self.crop_w * (self.n_col + 1), :] = \
                self.frame[fc_lim_M[0]:fc_lim_M[1], fc_lim_N[0]:fc_lim_N[1]]

        except ValueError as e:
            logging.debug(('VE', self.n_col, self.n_row, self._fresh_frame.shape, e))

    def close(self):
        pass
