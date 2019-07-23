#!/usr/bin/env python3

import argparse
import ctypes
import logging
import multiprocessing as mp
import threading
import time
from collections import deque
from pathlib import Path
from queue import Queue
import math

import cv2
import numpy as np
import pkg_resources
import yaml
import zmq

from beholder.defaults import *
from beholder.grabber import Grabber
from beholder.util import buf_to_numpy, fmt_time, euclidean_distance
from beholder.writer import Writer

SHARED_ARR = None
FONT = cv2.FONT_HERSHEY_PLAIN

PAUSABLE = True

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')


class Beholder:
    def __init__(self, cfg):
        threading.current_thread().name = 'Beholder'

        # Control events
        self.ev_stop = threading.Event()
        self.ev_recording = threading.Event()
        self.ev_tracking = threading.Event()
        self.ev_trial_active = threading.Event()

        # timing information
        self.t_phase = cv2.getTickCount()
        self.timing_trial_start = None
        self.timing_recording_start = None

        # recording target
        self.output_path = cfg['out_path']
        self.recording_path = None
        self.recording_ts = None
        self.__last_button_press = None

        self._loop_times = deque(maxlen=N_FRAMES_FPS_LOG)
        self.__last_display = time.time()

        self.cfg = cfg
        self.sources = self.cfg['sources']

        self.n_rows = min(self.cfg['n_rows'], len(self.sources))
        self.n_cols = math.ceil(len(self.cfg['sources']) / self.n_rows)
        self.cfg['n_cols'] = self.n_cols

        self.cfg['cropped_frame_width'] = cfg['frame_width'] - 2 * cfg['frame_crop_x']
        self.cfg['cropped_frame_height'] = cfg['frame_height'] - cfg['frame_crop_y']

        self.cfg['shared_shape'] = (self.cfg['cropped_frame_height'] * self.n_rows,
                                    self.cfg['cropped_frame_width'] * self.n_cols,
                                    cfg['frame_colors'])

        self.zmq_context = zmq.Context()

        # Construct the shared array to fit all frames
        bufsize = self.cfg['cropped_frame_width'] * self.cfg['cropped_frame_height'] * cfg['frame_colors'] * len(
            cfg['sources'])

        self._shared_arr = mp.Array(ctypes.c_ubyte, bufsize)
        logging.debug('Beholder shared array: {}'.format(self._shared_arr))
        self.frame = buf_to_numpy(self._shared_arr, shape=self.cfg['shared_shape'])

        self.disp_frame = np.zeros(self.frame.shape, dtype=np.uint8)

        self.measure_points = [None, None]

        # self.paused_frame = np.zeros_like(self.frame)

        # Frame queues for video file output
        self.write_queues = [Queue(maxsize=WRITE_QUEUE_LENGTH) for _ in range(len(self.sources))]

        # Grabber objects
        self.grabbers = [Grabber(cfg=self.cfg,
                                 target=self.sources[n],
                                 arr=self._shared_arr,
                                 out_queue=self.write_queues[n],
                                 trigger_event=self.ev_stop,
                                 ctx=self.zmq_context,
                                 idx=n,
                                 transpose=n >= 6,
                                 main_thread=self) for n in range(len(self.sources))]
        # Video storage writers
        self.writers = [Writer(cfg=cfg,
                               in_queue=self.write_queues[n],
                               ev_alive=self.ev_stop,
                               ev_recording=self.ev_recording,
                               ev_trial_active=self.ev_trial_active,
                               idx=n,
                               main_thread=self) for n in range(len(self.sources))]

        self.notes = []

        # Start threads
        for n in range(len(self.sources)):
            self.grabbers[n].start()
            self.writers[n].start()

        cv2.namedWindow('Beholder', cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback("Beholder", self.process_mouse)

        logging.debug('Beholder initialization done!')
        self.paused = False

    def loop(self):
        try:
            t0 = cv2.getTickCount()
            while not self.ev_stop.is_set():
                if not all([grabber.is_alive() for grabber in self.grabbers]):
                    self.stop()
                    break

                if self.paused:
                    pass
                else:
                    pass
                    # with self._shared_arr.get_lock():
                    #     # Copy shared frame content into display buffer
                self.disp_frame[:] = self.frame

                self.annotate_frame(self.disp_frame)
                if not self.paused:
                    cv2.imshow('Beholder', self.disp_frame)  # instead of self.disp_frame

                elapsed = ((cv2.getTickCount() - t0) / cv2.getTickFrequency()) * 1000
                self._loop_times.appendleft(elapsed)
                if time.time() - self.__last_display > 1:
                    # print(elapsed)
                    self.__last_display = time.time()

                t0 = cv2.getTickCount()
                self.process_events()

        except KeyboardInterrupt:
            self.stop()

    def annotate_frame(self, frame):
        if None not in self.measure_points:
            p1, p2 = self.measure_points
            cv2.line(frame, p1, p2, (255, 255, 0), thickness=1, lineType=cv2.LINE_AA)
        if self.ev_recording.is_set():
            cv2.circle(frame, (150, 150), 75, color=(0, 0, 255), thickness=-1)
            # if self.timing_recording_start is not None:
            delta = time.time() - self.timing_recording_start
            cv2.putText(frame, fmt_time(delta)[:8], (80, 161), fontFace=FONT, fontScale=2, color=(255, 255, 255),
                        thickness=2, lineType=cv2.LINE_AA)

        if self.ev_trial_active.is_set():
            delta = time.time() - self.timing_trial_start
            t_str = fmt_time(delta)
            cv2.putText(frame, f'{t_str[3:5]}min{t_str[6:8]}s', (15, 320), fontFace=FONT, fontScale=4.5,
                        color=(0, 0, 0),
                        thickness=7, lineType=cv2.LINE_AA)
            cv2.putText(frame, f'{t_str[3:5]}min{t_str[6:8]}s', (15, 320), fontFace=FONT, fontScale=4.5,
                        color=(255, 255, 255),
                        thickness=4, lineType=cv2.LINE_AA)

    def process_events(self):
        key = cv2.waitKey(30)

        if key == ord('q'):
            self.stop()

        # Start or stop recording
        elif key == ord('r'):
            self.toggle_recording()

        elif key in [ord('t'), ord('b'), 85, 86]:
            if FORCE_RECORDING_ON_TRIAL and not self.ev_recording.is_set():
                # make sure recording is running when we toggle a trial!
                logging.warning('Force starting recording on trial initiation. Someone forgot to press record?')
                self.toggle_recording(True)

            # Start/stop a trial period
            self.toggle_trial()

        # Stub event to notify of issues for later review.
        elif key == ord('n'):
            self.notes.append(time.time())
            logging.warning('Something happened! Take note!')

        elif key == ord(' ') and PAUSABLE:
            self.paused = not self.paused
            logging.debug('Paused toggled to {}'.format(self.paused))

        # Detect if close button of was pressed.
        # May not be reliable on all platforms/GUI backends
        if cv2.getWindowProperty('Beholder', cv2.WND_PROP_AUTOSIZE) < 1:
            self.stop()

    def toggle_recording(self, target_state=None):
        self.t_phase = cv2.getTickCount()

        # prevent pressing the button too fast
        if self.__last_button_press is not None and (time.time() - self.__last_button_press) < REC_BUTTON_DEBOUNCE:
            logging.warning('Pressed recording button too fast!')
            return

        # gather the new state from current state, else override
        target_state = target_state if target_state is not None else not self.ev_recording.is_set()

        # start recording
        if target_state:
            ts = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time()))
            rec_path = self.output_path / ts

            logging.debug(f'Creating output directory {rec_path}')
            try:
                rec_path.mkdir(exist_ok=False, parents=True)
            except FileExistsError:
                logging.error('The output path already exists! Pressed recording too fast?')
                return

            self.recording_path = rec_path
            self.recording_ts = ts
            self.ev_recording.set()
            self.timing_recording_start = time.time()

        # stop recording
        else:
            self.ev_recording.clear()
            self.recording_path = None
            self.recording_ts = None
            self.timing_recording_start = None

    def toggle_trial(self, target_state=None):
        # gather the new state from current state, else override
        target_state = target_state if target_state is not None else not self.ev_trial_active.is_set()

        # start trial
        if target_state:
            self.ev_trial_active.set()
            logging.info('Trial {}'.format('++++++++ start ++++++++'))
            self.timing_trial_start = time.time()

        # stop trial
        else:
            self.ev_trial_active.clear()
            logging.info('Trial {} Duration: {:.1f}s'.format('++++++++ end  +++++++++',
                                                             time.time() - self.timing_trial_start))
            self.timing_trial_start = None

    def process_mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN and flags:
            pass

        elif event == cv2.EVENT_RBUTTONDOWN:
            self.measure_points = [None, None]

        elif event == cv2.EVENT_LBUTTONDBLCLK:
            self.measure_points[0] = self.measure_points[1]
            self.measure_points[1] = (x, y)

            if None not in self.measure_points:
                p1, p2 = self.measure_points
                distance = euclidean_distance(p1, p2)
                distance_m_floor = distance * self.cfg['scale_floor']
                distance_m_arena = distance * self.cfg['scale_arena']
                dx = abs(p1[0] - p2[0])
                dy = abs(p1[1] - p2[1])
                logging.info(
                    f'({p1}; {p2}) | l: {distance:.1f} px, -arena-: {distance_m_arena:.0f} mm,'
                    ' _floor_: {distance_m_floor:.0f} mm, dx: {dx}, dy: {dy}')

    def stop(self):
        self.ev_stop.set()
        logging.debug('Join request sent!')

        # Shut down Grabbers
        for grabber in self.grabbers:
            if grabber.is_alive():
                grabber.join()
        logging.debug('All Grabbers joined!')

        # Shut down Writers
        for writer in self.writers:
            if writer.is_alive():
                writer.join()
        logging.debug('All Writers joined!')

        if len(self.notes):
            logging.warning('There were {} events marked!'.format(len(self.notes)))


def main():
    parser = argparse.ArgumentParser(description='BeholderPi visualizer and recorder.')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
    parser.add_argument('-o', '--output', help='Location to store output in', default='~/Videos/beholder')
    parser.add_argument('-c', '--config', help='Non-default configuration file to use')

    cli_args = parser.parse_args()

    out_path = Path(cli_args.output).expanduser().resolve()

    if not out_path.exists():
        raise FileNotFoundError(f"Output directory '{out_path}' does not exist!")

    logfile = out_path / "{}_beholder.log".format(
        time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time())))

    if cli_args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')

    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - (%(threadName)-9s) %(message)s')

    fh = logging.FileHandler(str(logfile))
    fhf = logging.Formatter('%(asctime)s : %(levelname)s : [%(threadName)-9s] - %(message)s')
    fh.setFormatter(fhf)
    logging.getLogger('').addHandler(fh)

    # Load configuration yaml file for beholder
    if cli_args.config:
        cfg_path = cli_args.config
    else:
        # Check if a local configuration exists
        cfg_path = pkg_resources.resource_filename(__name__, 'resources/config_beholder_local.yml')
        if Path(cfg_path).exists():
            logging.debug('Using local config')
        # Otherwise we fall back on the default file
        else:
            logging.debug('Found and using local config file')
            cfg_path = pkg_resources.resource_filename(__name__, 'resources/config_beholder_default.yml')

    cfg_path = Path(cfg_path)
    if not cfg_path.exists():
        raise FileNotFoundError(f"Could not load configuration file {cfg_path}")

    # Load the configuration file
    # TODO: Loading should overwrite defaults. Currently an incomplete configuration load will fail.
    with open(cfg_path, 'r') as cfg_f:
        cfg = yaml.load(cfg_f, Loader=yaml.SafeLoader)

    logging.debug('Output destination {}'.format(out_path))
    cfg['out_path'] = out_path

    beholder = Beholder(cfg)
    beholder.loop()


if __name__ == '__main__':
    main()
