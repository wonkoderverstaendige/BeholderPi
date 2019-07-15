from math import sqrt

import numpy as np


def fmt_time(t):
    """Format a number of seconds into a human readable time string of HH:MM:SS.FFF
    """
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return "{h:02.0f}:{m:02.0f}:{s:06.3f}".format(h=h, m=m, s=s)


def buf_to_numpy(buf, shape, count=-1, offset=0):
    """Return numpy object from a raw buffer, e.g. multiprocessing Array
    """
    return np.frombuffer(buf.get_obj(), dtype=np.ubyte, count=count, offset=offset).reshape(shape)


def euclidean_distance(p1, p2):
    """Calculate the euclidean distance between two points.
    """
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
