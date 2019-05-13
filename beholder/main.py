#!/usr/bin/env python3

import pkg_resources

import ctypes
import logging
import multiprocessing as mp
from queue import Queue
from collections import deque
import threading
import yaml
from math import sqrt

import numpy as np
import zmq
import cv2

from beholder.util import buf_to_numpy
from beholder.grabber import Grabber
from beholder.writer import Writer
from beholder.defaults import *

SHARED_ARR = None

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - (%(threadName)-9s) %(message)s')


def euclidean_distance(p1, p2):
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


class Beholder:
    def __init__(self, cfg, shared_arr):
        threading.current_thread().name = 'Beholder'

        # Control events
        self.ev_stop = threading.Event()
        self.ev_recording = threading.Event()
        self.ev_tracking = threading.Event()
        self.ev_trial_active = threading.Event()
        self.t_phase = cv2.getTickCount()

        self._loop_times = deque(maxlen=N_FRAMES_FPS_LOG)

        self.cfg = cfg
        self.sources = self.cfg['sources']

        self.n_rows = self.cfg['n_rows']
        self.n_cols = ceil(len(self.cfg['sources']) / self.n_rows)
        self.cfg['n_cols'] = self.n_cols

        self.arr_shape = (cfg['frame_height'] * self.n_rows, cfg['frame_width'] * self.n_cols, cfg['frame_colors'])

        self.zmq_context = zmq.Context()

        # Shared array population
        with shared_arr.get_lock():
            self._shared_arr = shared_arr
            logging.debug('Beholder shared array: {}'.format(self._shared_arr))
            self.frame = buf_to_numpy(self._shared_arr, shape=self.arr_shape)

        self.disp_frame = np.zeros(self.frame.shape, dtype=np.uint8)

        self.measure_points = [None, None]

        # self.paused_frame = np.zeros_like(self.frame)

        # Frame queues for video file output
        self.write_queues = [Queue(maxsize=150) for _ in range(len(self.sources))]

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
                    #     self.disp_frame[:] = self.frame

                self.annotate_frame()
                cv2.imshow('Beholder', self.frame)  # instead of self.disp_frame

                elapsed = ((cv2.getTickCount() - t0) / cv2.getTickFrequency()) * 1000
                self._loop_times.appendleft(elapsed)

                t0 = cv2.getTickCount()
                self.process_events()

        except KeyboardInterrupt:
            self.stop()

    def annotate_frame(self):
        if None not in self.measure_points:
            p1, p2 = self.measure_points
            cv2.line(self.frame, p1, p2, (255, 255, 0), thickness=1, lineType=cv2.LINE_AA)

    def process_events(self):
        key = cv2.waitKey(30)

        if key == ord('q'):
            self.stop()

        # Start or stop recording
        elif key == ord('r'):
            self.t_phase = cv2.getTickCount()
            if not self.ev_recording.is_set():
                self.ev_recording.set()
            else:
                self.ev_recording.clear()

        # Detect if close button of was pressed.
        # May not be reliable on all platforms/GUI backends
        if cv2.getWindowProperty('Beholder', cv2.WND_PROP_AUTOSIZE) < 1:
            self.stop()

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
                distance_m = distance * 4.29
                dx = abs(p1[0] - p2[0])
                dy = abs(p1[1] - p2[1])
                # two_m_cal = 0 if distance == 0 else 2000 / distance
                logging.info(
                    f'({p1}; {p2}) | l: {distance:.1f} px, {distance_m:.0f} mm, dx: {dx}, dy: {dy}')  #  | [@2m profile: {two_m_cal:.2f} mm/px]

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


if __name__ == '__main__':
    # Load configuration
    cfg_path = pkg_resources.resource_filename(__name__, 'resources/config_beholder_default.yml')
    with open(cfg_path, 'r') as cfg_f:
        cfg = yaml.load(cfg_f)

    # Construct the shared array to fit all frames
    num_bytes = cfg['frame_width'] * (cfg['frame_height'] + FRAME_METADATA_H) * cfg['frame_colors'] * len(
        cfg['sources'])

    SHARED_ARR = mp.Array(ctypes.c_ubyte, num_bytes)

    beholder = Beholder(cfg=cfg, shared_arr=SHARED_ARR)
    beholder.loop()
