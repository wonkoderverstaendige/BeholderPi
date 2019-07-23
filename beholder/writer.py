import csv
import logging
import subprocess as sp
import threading
from queue import Empty

import numpy as np

from beholder.defaults import *


class Writer(threading.Thread):
    def __init__(self, cfg, in_queue, ev_alive, ev_recording, ev_trial_active, main_thread, idx=0):
        super().__init__()
        self.id = idx
        self.cfg = cfg

        self.name = 'Writer #{:02d}'.format(self.id)
        self.writer_pipe = None
        self.log_file = None
        self.log_csv = None
        self.log_csv_header_written = False
        self.logger = None

        self.n_frames = 0

        self.width = None
        self.height = None
        self.frame = None

        self.in_queue = in_queue
        self._ev_stop = ev_alive
        self._ev_recording = ev_recording
        self._ev_trial_active = ev_trial_active

        self.parent = main_thread

        self.recording = False
        logging.debug('Writer initialization done!')

    def start_recording(self):
        # Video output object
        logging.debug('Starting Recording in {}'.format(self.parent.recording_path))

        out_path = self.parent.recording_path / 'eye{:02d}_{}.mp4'.format(self.id + 1, self.parent.recording_ts)
        ffmpeg_cmd = FFMPEG_COMMAND + [str(out_path)]
        logging.debug(' '.join(ffmpeg_cmd))

        self.writer_pipe = sp.Popen(ffmpeg_cmd, stdin=sp.PIPE)
        self.log_file = open(out_path.with_suffix('.meta'), 'w', newline='')
        self.log_csv = csv.writer(self.log_file)
        self.log_csv_header_written = False

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

        if self.log_file is not None and not self.log_file.closed:
            self.log_csv = None
            self.log_file.close()

        self.logger = None

    def run(self):
        logging.debug('Starting loop in {}!'.format(self.name))
        try:
            while not self._ev_stop.is_set():
                try:
                    metadata, frame = self.in_queue.get(timeout=.5)

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
                        self.writer_pipe.stdin.write(frame)
                        if not self.log_csv_header_written:
                            self.log_csv.writerow(metadata.keys())
                            self.log_csv_header_written = True
                        self.log_csv.writerow(metadata.values())

            logging.debug('Stopping loop in {}!'.format(self.name))
        except BaseException as e:
            raise e
        finally:
            self.stop_recording()
