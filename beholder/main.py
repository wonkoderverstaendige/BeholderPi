#!/usr/bin/env python3

import pkg_resources

import argparse
import ctypes
import logging
import multiprocessing as mp
from queue import Queue
from collections import deque
import threading
import yaml
from math import sqrt
import time
from pathlib import Path

import numpy as np
import zmq
import cv2

from beholder.util import buf_to_numpy, fmt_time
from beholder.grabber import Grabber
from beholder.writer import Writer
from beholder.defaults import *

SHARED_ARR = None
FONT = cv2.FONT_HERSHEY_PLAIN

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')


def euclidean_distance(p1, p2):
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


class Beholder:
    def __init__(self, cfg):
        threading.current_thread().name = 'Beholder'

        # Control events
        self.ev_stop = threading.Event()
        self.ev_recording = threading.Event()
        self.ev_tracking = threading.Event()
        self.ev_trial_active = threading.Event()
        self.t_phase = cv2.getTickCount()
        self.timing_trial_start = None
        self.timing_recording_start = None

        self._loop_times = deque(maxlen=N_FRAMES_FPS_LOG)
        self.__last_display = time.time()

        self.cfg = cfg
        self.sources = self.cfg['sources']

        self.n_rows = self.cfg['n_rows']
        self.n_cols = ceil(len(self.cfg['sources']) / self.n_rows)
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
                                 transpose=n >= 6) for n in range(len(self.sources))]
        # Video storage writers
        self.writers = [Writer(cfg=cfg,
                               in_queue=self.write_queues[n],
                               ev_alive=self.ev_stop,
                               ev_recording=self.ev_recording,
                               ev_trial_active=self.ev_trial_active,
                               idx=n) for n in range(len(self.sources))]

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
            cv2.circle(frame, (100, 100), 75, color=(0, 0, 255), thickness=-1)
            # if self.timing_recording_start is not None:
            delta = time.time() - self.timing_recording_start
            cv2.putText(frame, fmt_time(delta)[:10], (35, 105), fontFace=FONT, fontScale=1.5, color=(255, 255, 255),
                        thickness=2, lineType=cv2.LINE_AA)

        if self.ev_trial_active.is_set():
            delta = time.time() - self.timing_trial_start
            cv2.putText(frame, 'Trial: '+fmt_time(delta)[3:10], (15, 220), fontFace=FONT, fontScale=3, color=(0, 0, 0),
                        thickness=4, lineType=cv2.LINE_AA)
            cv2.putText(frame, 'Trial: '+fmt_time(delta)[3:10], (15, 220), fontFace=FONT, fontScale=3, color=(255, 255, 255),
                        thickness=2, lineType=cv2.LINE_AA)

    def process_events(self):
        key = cv2.waitKey(30)

        if key == ord('q'):
            self.stop()

        # Start or stop recording
        elif key == ord('r'):
            self.toggle_recording()

        elif key in [ord('t'), ord('.'), 85, 86]:
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

        # Detect if close button of was pressed.
        # May not be reliable on all platforms/GUI backends
        if cv2.getWindowProperty('Beholder', cv2.WND_PROP_AUTOSIZE) < 1:
            self.stop()

    def toggle_recording(self, target_state=None):
        self.t_phase = cv2.getTickCount()

        # gather the new state from current state, else override
        target_state = target_state if target_state is not None else not self.ev_recording.is_set()

        if target_state:
            self.ev_recording.set()
            self.timing_recording_start = time.time()
        else:
            self.ev_recording.clear()
            self.timing_recording_start = None

    def toggle_trial(self, target_state=None):
        # gather the new state from current state, else override
        target_state = target_state if target_state is not None else not self.ev_trial_active.is_set()

        if target_state:
            self.ev_trial_active.set()
            logging.info('Trial {}'.format('++++++++ start ++++++++'))
            self.timing_trial_start = time.time()
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
                distance_m_floor = distance * cfg['scale_floor']
                distance_m_arena = distance * cfg['scale_arena']
                dx = abs(p1[0] - p2[0])
                dy = abs(p1[1] - p2[1])
                logging.info(
                    f'({p1}; {p2}) | l: {distance:.1f} px, -arena-: {distance_m_arena:.0f} mm, _floor_: {distance_m_floor:.0f} mm, dx: {dx}, dy: {dy}')

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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BeholderPi visualizer and recorder.')

    parser.add_argument('--crop_x', help='Crop in x-axis (slice off the sides).', type=int)
    parser.add_argument('--crop_y', help='Crop in y-axis (slice off the sides).', type=int)
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')

    cli_args = parser.parse_args()

    logfile = "img/{}_beholder.log".format(
        time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time())))

    if cli_args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')

    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - (%(threadName)-9s) %(message)s')

    fh = logging.FileHandler(str(logfile))
    fhf = logging.Formatter('%(asctime)s : %(levelname)s : [%(threadName)-9s] - %(message)s')
    fh.setFormatter(fhf)
    logging.getLogger('').addHandler(fh)

    # Load configuration
    cfg_path = pkg_resources.resource_filename(__name__, 'resources/config_beholder_default.yml')
    with open(cfg_path, 'r') as cfg_f:
        cfg = yaml.load(cfg_f)

    if cli_args.crop_x is not None:
        cfg['frame_crop_x'] = cli_args.crop_x
    if cli_args.crop_y is not None:
        cfg['frame_crop_y'] = cli_args.crop_y

    beholder = Beholder(cfg)
    beholder.loop()
