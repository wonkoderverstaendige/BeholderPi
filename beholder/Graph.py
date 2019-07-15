from beholder.util import euclidean_distance
import networkx as nx
import cv2
import numpy as np


# from: https://stackoverflow.com/questions/849211/shortest-distance-between-a-point-and-a-line-segment
def ls_dist(p1, p2, p3):
    p1 = np.asarray(p1)
    p2 = np.asarray(p2)
    p3 = np.asarray(p3)

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

# class MazeNode:
#     def __init__(self, name, pos=None, color=None):
#         self.name = name
#         self.pos = pos
#         self.color = color
#
#     def distance(self, coordinate):
#         return None if self.pos is None else euclidean_distance(self.pos, coordinate)
#
#
# class MazeEdge:
#     def __init__(self, n1, n2):
#         self.n1, self.n2 = sorted([n1, n2])
#         self.name = f'{n1.name}_{n2.name}'
#
#     def distance(self, coordinate):
#         return 0


class MazeGraph:
    def __init__(self, graph_dict=None):
        self.dict = {} if graph_dict is None else graph_dict

    def vertices(self):
        return list(self.dict.keys())

    def add_vertex(self, v):
        if v not in self.dict:
            self.dict[v] = []

    def edges(self):
        edges = []
        for v1 in self.dict:
            for v2 in self.dict[v1]:
                edge_candidate = {v1, v2}
                if edge_candidate not in edges:
                    edges.append(edge_candidate)
        return edges

    def add_edge(self, edge):
        v1, v2 = edge
        self.dict[v1].append(v2)
        self.dict[v2].append(v1)


if __name__ == '__main__':
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
                    ('H24', 'E1')]

    graph_prototype = {}
    for isle in island_prefixes:
        for node, edges in flower_graph.items():
            graph_prototype[isle + str(node)] = {isle + str(n) for n in edges}

    node_positions = {}
    with open('H:/Dropbox/ronny/Notebooks/compvis/RatHexMaze/node_list_juraj.corrected.csv', 'r') as npf:
        for line in npf:
            nn, x, y = map(str.strip, line.split(','))
            node_positions[nn] = (int(x), int(y))

    mg = nx.Graph(graph_prototype)
    mg.add_edges_from(bridge_edges)

    edge_list = list(mg.edges)
    distances = np.zeros((len(edge_list), 3))

    img = cv2.imread('H:/Dropbox/ronny/Notebooks/compvis/RatHexMaze/img/fullmaze_stitched.png')
    test_p = (100, 100)

    while True:
        # draw base maze
        for n, edge in enumerate(edge_list):
            n1 = node_positions[edge[0]]
            n2 = node_positions[edge[1]]
            nps = np.asarray([n1, n2])

            d, p4 = ls_dist(n1, n2, test_p)
            distances[n, 0] = d
            distances[n, 1:] = p4

            cv2.line(img, n1, n2, color=(128, 128, 0))

        closest_idx = distances[:, 0].argmin()
        closest_edge = edge_list[closest_idx]

        v1 = node_positions[closest_edge[0]]
        v2 = node_positions[closest_edge[1]]
        cv2.line(img, v1, v2, color=(0, 0, 255), thickness=3)

        cv2.drawMarker(img, test_p, color=(0, 0, 255), thickness=5)

        cv2.imshow('graph', img)
        key = cv2.waitKey(30)
        if key > 1:
            break

