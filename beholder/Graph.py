from beholder.util import euclidean_distance


class MazeNode:
    def __init__(self, name, pos=None, color=None):
        self.name = name
        self.pos = pos
        self.color = color

    def distance(self, coordinate):
        return None if self.pos is None else euclidean_distance(self.pos, coordinate)


class MazeEdge:
    def __init__(self, n1, n2):
        self.n1, self.n2 = sorted([n1, n2])
        self.name = f'{n1.name}_{n2.name}'

    def distance(self, coordinate):
        return 0


class MazeGraph:
    def __init__(self, graph_dict):
        self.dict = graph_dict


if __name__ == '__main__':
    graph = {'E14': ['E15', 'E13'],
             'E13': ['E14', 'E6'],
             'E20': ['E14', 'E19', '21'],
             }

    MazeGraph(graph)
