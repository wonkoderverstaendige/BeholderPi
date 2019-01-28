import csv
import time
import logging
import threading
from queue import Empty
from pathlib import Path

import subprocess as sp

from beholder.defaults import *


class Writer(threading.Thread):
    def __init__(self, cfg, in_queue, ev_alive, ev_recording, ev_trial_active, idx=0):
        super().__init__()
        self.id = idx
        self.cfg = cfg

        self.name = 'Writer #{:02d}'.format(self.id)
        self.writer_pipe = None
        self.logger = None

        self.n_frames = 0

        self.width = None
        self.height = None
        self.frame = None

        self.in_queue = in_queue
        self._ev_stop = ev_alive
        self._ev_recording = ev_recording
        self._ev_trial_active = ev_trial_active

        self.recording = False
        logging.debug('Writer initialization done!')

    def start_recording(self):
        # Video output object
        logging.debug('Starting Recording')

        ts_launch = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time()))
        cmd = FFMPEG_COMMAND + ['img/{}_piEye{:02d}.mp4'.format(self.id, ts_launch)]
        self.writer_pipe = sp.Popen(cmd, stdin=sp.PIPE)

        # # Frame metadata logger output
        # path_log = fname_base + '.csv'
        # try:
        #     self.logger = csv.writer(open(path_log, 'w', newline=''))
        # except FileNotFoundError:
        #     logging.error('Failed to open log file at {}'.format(path_log))
        #     self.stop_recording()
        #
        # self.logger.writerow(['index', 'bool_trial', 'timestamp', 'tickstamp'])

        self.recording = True

    def stop_recording(self):
        if self.recording:
            logging.debug('Stopping Recording')

        self.recording = False
        self._ev_recording.clear()

        if self.writer_pipe is not None:
            self.writer_pipe.stdin.close()
            self.writer_pipe.wait()
            self.writer_pipe = None

        self.logger = None

    def run(self):
        logging.debug('Starting loop in {}!'.format(self.name))
        try:
            while not self._ev_stop.is_set():
                try:
                    self.frame = self.in_queue.get(timeout=.5)
                except Empty:
                    continue

                rec = self._ev_recording.is_set()
                if self.recording != rec:
                    if rec:
                        self.start_recording()
                    else:
                        self.stop_recording()

                if self.recording:
                    if self.writer_pipe is None:
                        logging.error('Attempted to write to failed Writer!')
                        self.stop_recording()
                    else:
                        self.writer_pipe.stdin.write(self.frame)
                        # metadata = [self.frame.index, int(self._ev_trial_active.is_set()),
                        #             self.frame.time_text, self.frame.tickstamp]
                        # self.logger.writerow(metadata)

            logging.debug('Stopping loop in {}!'.format(self.name))
        except BaseException as e:
            raise e
        finally:
            self.stop_recording()
