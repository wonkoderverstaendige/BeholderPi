#!/usr/bin/env python
import argparse
import logging
import time
from pathlib import Path

import cv2
import networkx as nx
import numpy as np

from beholder.util import fmt_time, euclidean_distance

FONT = cv2.FONT_HERSHEY_PLAIN

NODE_KEYS = list(reversed([isle + str(num + 1) for isle in ['I', 'J', 'H', 'E'] for num in range(24)]))

COLOR_NODE_INACTIVE = (255, 255, 255)
COLOR_NODE_ACTIVE = (255, 0, 0)
COLOR_NODE_ACTIVE_SECONDARY = (255, 175, 175)
COLOR_NODE_BG = (0, 0, 0)


# from: https://stackoverflow.com/questions/849211/shortest-distance-between-a-point-and-a-line-segment
def ls_dist(p1, p2, p3):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3

    px = x2 - x1
    py = y2 - y1

    norm = px * px + py * py
    u = ((x3 - x1) * px + (y3 - y1) * py) / float(norm)

    if u > 1:
        u = 1
    elif u < 0:
        u = 0

    x = x1 + u * px
    y = y1 + u * py

    dx = x - x3
    dy = y - y3

    dist = (dx * dx + dy * dy) ** .5

    return dist, (x, y)


class Tracer:
    def __init__(self, video_path, nodes, node_positions, capture_offset=0):
        self.vid_path = video_path
        self.nodes = nodes
        self.edges = list(self.nodes.edges)

        self.capture = cv2.VideoCapture(str(video_path))
        self.capture.set(cv2.CAP_PROP_POS_MSEC, capture_offset * 1000)
        cv2.namedWindow('Tracer', cv2.WINDOW_GUI_NORMAL + cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback('Tracer', self.process_mouse)

        self.paused = False
        self.frame = None
        self.disp_frame = None

        self.active_node = None
        self.selected_node = None
        self.selected_edge = None
        self.clicked_point = None

        self.__dists = np.zeros((len(self.edges), 3))

        self.node_positions = node_positions

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
            self.clicked_point = (x, y)
            self.selected_edge = self.closest_edge(self.clicked_point)
            self.selected_node = self.closest_node(self.clicked_point, self.selected_edge)
            fp = int(self.capture.get(cv2.CAP_PROP_POS_FRAMES))
            logging.info(f'{str.lower(self.selected_node)} at frame #{fp} @{x}, {y}')

        elif event == cv2.EVENT_RBUTTONDOWN:
            self.clicked_point = None
            self.selected_node = None
            self.selected_edge = None

    def closest_node(self, coordinate, edge):
        if edge is None:
            return None

        n1 = self.node_positions[edge[0]]
        n2 = self.node_positions[edge[1]]
        if euclidean_distance(n1, coordinate) > euclidean_distance(n2, coordinate):
            return edge[1]
        else:
            return edge[0]

    def closest_edge(self, coordinate):
        if self.clicked_point is None:
            return None

        for n, e in enumerate(self.edges):
            n1 = self.node_positions[e[0]]
            n2 = self.node_positions[e[1]]
            d, p4 = ls_dist(n1, n2, coordinate)
            self.__dists[n, 0] = d
            self.__dists[n, 1:] = p4

        closest_idx = self.__dists[:, 0].argmin()
        closest_edge = self.edges[closest_idx]
        return closest_edge

    def annotate_frame(self, frame):
        # draw edges
        for edge in self.edges:
            if edge == self.selected_edge:
                self.draw_edge(frame, edge, color=(0, 0, 255), thickness=2)
            else:
                self.draw_edge(frame, edge, color=(128, 128, 0))

        # Draw node labels
        for nn, nc in self.node_positions.items():
            x, y = nc

            if nn == self.selected_node:
                color = COLOR_NODE_ACTIVE
            else:
                color = COLOR_NODE_INACTIVE

            self.annotate_node(frame, nn, x, y, color=color)

        if self.clicked_point is not None:
            v1 = node_positions[self.selected_edge[0]]
            v2 = node_positions[self.selected_edge[1]]
            d, p4 = ls_dist(v1, v2, self.clicked_point)
            cv2.line(frame, self.clicked_point, tuple(map(int, p4)), color=(0, 255, 255), thickness=1)
            cv2.drawMarker(frame, self.clicked_point, color=(0, 255, 255), thickness=3, markerSize=5)

    @staticmethod
    def annotate_node(frame, node, x, y, color=COLOR_NODE_INACTIVE, color_bg=COLOR_NODE_BG):
        cv2.circle(frame, (x, y), 3, (255, 255, 0), -1)
        cv2.putText(frame, str(node), (x + 5, y + 5), fontScale=1.5, fontFace=FONT, color=color_bg, thickness=4,
                    lineType=cv2.LINE_AA)
        cv2.putText(frame, str(node), (x + 5, y + 5), fontScale=1.5, fontFace=FONT, color=color, thickness=2,
                    lineType=cv2.LINE_AA)

    def draw_edge(self, frame, edge, color=(128, 128, 0), thickness=1):
        n1 = self.node_positions[edge[0]]
        n2 = self.node_positions[edge[1]]
        cv2.line(frame, n1, n2, color=color, thickness=thickness)

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
        raise FileNotFoundError('Need to specify node file!!!')

    start_time = 0 if not cli_args.starttime else cli_args.starttime
    if start_time:
        print(f'Reading video from {fmt_time(start_time)} onwards')

    # BUILD THE GRAPH
    # Node positions
    node_positions = {}
    logging.info(f'Reading node list from {node_list_path}')
    with open(node_list_path, 'r') as npf:
        for line in npf:
            nn, x, y = map(str.strip, line.split(','))
            node_positions[nn] = (int(x), int(y))

    flower_graph = {1: [2, 7],
                    2: [1, 3],
                    3: [2, 4, 9],
                    4: [3, 5],
                    5: [4, 11],
                    6: [7, 13],
                    7: [6, 1, 8],
                    8: [7, 9, 15],
                    9: [3, 8, 10],
                    10: [9, 11, 17],
                    11: [5, 10, 12],
                    12: [11, 19],
                    13: [6, 14],
                    14: [13, 15, 20],
                    15: [8, 14, 16],
                    16: [15, 17, 22],
                    17: [10, 16, 18],
                    18: [17, 19, 24],
                    19: [12, 18],
                    20: [14, 21],
                    21: [20, 22],
                    22: [16, 21, 23],
                    23: [22, 24],
                    24: [18, 23]}

    island_prefixes = ['I', 'J', 'H', 'E']

    bridge_edges = [('I24', 'J1'),
                    ('I21', 'H2'),
                    ('J23', 'E4'),
                    ('H24', 'E1'),
                    ('H5', 'J20')]

    graph_prototype = {}
    for isle in island_prefixes:
        for node, edges in flower_graph.items():
            graph_prototype[isle + str(node)] = {isle + str(n) for n in edges}

    mg = nx.Graph(graph_prototype)
    mg.add_edges_from(bridge_edges)

    Tracer(vp, mg, capture_offset=start_time, node_positions=node_positions)
