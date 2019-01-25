import numpy as np


def fmt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return "{h:02.0f}:{m:02.0f}:{s:06.3f}".format(h=h, m=m, s=s)


def buf_to_numpy(buf, shape, count=-1, offset=0):
    """Return numpy object from a raw buffer, e.g. multiprocessing Array"""
    return np.frombuffer(buf.get_obj(), dtype=np.ubyte, count=count, offset=offset).reshape(shape)
