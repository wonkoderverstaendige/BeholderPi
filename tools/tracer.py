#!/usr/bin/env python
import argparse
import logging
import time
from pathlib import Path

import cv2

from beholder.util import fmt_time, euclidean_distance

FONT = cv2.FONT_HERSHEY_PLAIN

NODE_KEYS = list(reversed([isle + str(num + 1) for isle in ['I', 'J', 'H', 'E'] for num in range(24)]))

COLOR_NODE_INACTIVE = (255, 255, 255)
COLOR_NODE_ACTIVE = (255, 0, 0)
COLOR_NODE_ACTIVE_SECONDARY = (255, 175, 175)
COLOR_NODE_BG = (0, 0, 0)


class Tracer:
    def __init__(self, video_path, nodes, capture_offset=0):
        self.vid_path = video_path
        self.nodes = nodes

        self.capture = cv2.VideoCapture(str(video_path))
        self.capture.set(cv2.CAP_PROP_POS_MSEC, capture_offset * 1000)
        cv2.namedWindow('Tracer', cv2.WINDOW_GUI_NORMAL + cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback("Tracer", self.process_mouse)

        self.paused = False
        self.frame = None
        self.disp_frame = None

        self.active_node = None
        self.selected_node = None
        self.secondary_selected_node = None

        self.loop()

    def loop(self):
        while True:
            if not self.paused:
                rt, self.frame = self.capture.read()
                if not rt:
                    self.paused = True

            if self.frame is not None:
                self.disp_frame = self.frame.copy()
                self.annotate_frame(self.disp_frame)
                cv2.imshow('Tracer', self.disp_frame)

            key = cv2.waitKey(30)
            if key == 27 or key == ord('q'):
                break

            elif key == ord('s'):
                self.save_nodes()

            elif key == ord(' '):
                self.paused = not self.paused

    def process_mouse(self, event, x, y, flag, params):
        """Mouse event handling"""
        # TODO: This needs a lot of expansion
        # TODO: Shift+LClick adds first node not in the dictionary yet at clicked position
        # TODO: Shift+RClick removes the last added node
        if event == cv2.EVENT_LBUTTONDOWN and flag == (cv2.EVENT_FLAG_SHIFTKEY + cv2.EVENT_FLAG_LBUTTON):
            nn = NODE_KEYS.pop()
            self.nodes[nn] = (x, y)
            fp = int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
            logging.info(f'Click on frame #{fp} @{x}, {y}  [{flag}] {nn}')

        elif event == cv2.EVENT_FLAG_LBUTTON:
            self.closest_node((x, y))

        elif event == cv2.EVENT_RBUTTONDOWN:
            self.active_node = None
            self.secondary_selected_node = None

    def closest_node(self, coordinate):
        distances = [euclidean_distance(coordinate, node_position) for node_position in self.nodes.values()]
        node_distances = sorted(zip(distances, self.nodes.keys()))
        closest = node_distances[0]
        sec_closest = node_distances[1]

        self.selected_node = closest[1]
        self.secondary_selected_node = sec_closest[1]

        print(f'Node: {closest[1]} towards {sec_closest[1]} ({closest[0]:.0f}px from {coordinate})')

    def annotate_frame(self, frame):
        for nn, nc in self.nodes.items():
            x = nc[0]
            y = nc[1]

            if nn == self.selected_node:
                color = COLOR_NODE_ACTIVE
            elif nn == self.secondary_selected_node:
                color = COLOR_NODE_ACTIVE_SECONDARY
            else:
                color = COLOR_NODE_INACTIVE

            self.annotate_node(frame, nn, x, y, color=color)

    @staticmethod
    def annotate_node(frame, node, x, y, color=COLOR_NODE_INACTIVE, color_bg=COLOR_NODE_BG):
        cv2.circle(frame, (x, y), 5, (255, 255, 0), -1)
        cv2.putText(frame, str(node), (x + 5, y + 5), fontScale=2., fontFace=FONT, color=color_bg, thickness=4,
                    lineType=cv2.LINE_AA)
        cv2.putText(frame, str(node), (x + 5, y + 5), fontScale=2., fontFace=FONT, color=color, thickness=2,
                    lineType=cv2.LINE_AA)

    def save_nodes(self, fname='node_list.csv'):
        with open(fname, 'w') as nf:
            for node_name, coordinates in self.nodes.items():
                nf.write(f'{node_name}, {coordinates[0]}, {coordinates[1]}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser('RatHexMaze manual Path Tracer')
    parser.add_argument('path', help='Path to video')
    parser.add_argument('-d', '--debug', action='store_true', help='Debug mode')
    parser.add_argument('-n', '--nodes', help='Path to node list file')
    parser.add_argument('-t', '--starttime', type=float, help='Start video from time (in second)')

    cli_args = parser.parse_args()
    vp = Path(cli_args.path).resolve()

    logfile = vp.parent / "{}_overlay.log".format(
        time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime(time.time())))

    if cli_args.debug:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(message)s')

    else:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

    fh = logging.FileHandler(str(logfile))
    fhf = logging.Formatter('%(asctime)s : %(levelname)s : %(message)s')
    fh.setFormatter(fhf)
    logging.getLogger('').addHandler(fh)

    if not vp.exists():
        raise FileNotFoundError(f"Can't find {vp}")

    if cli_args.nodes is not None:
        node_list_path = Path(cli_args.nodes).expanduser().resolve()
        if not node_list_path.exists():
            raise FileNotFoundError(f"Can't find node list file '{str(node_list_path)}'")
    else:
        node_list_path = None

    node_dict = {}
    if node_list_path is not None:
        logging.info(f'Reading node list from {node_list_path}')
        with open(str(node_list_path)) as f:
            for line in f:
                (name, valx, valy) = line.split(',')
                valx = int(valx)
                valy = int(valy)
                node_dict[name] = valx, valy

    start_time = 0 if not cli_args.starttime else cli_args.starttime
    if start_time:
        print(f'Reading video from {fmt_time(start_time)} onwards')

    Tracer(vp, node_dict, start_time)
