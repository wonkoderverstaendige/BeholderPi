#!/usr/bin/env python3
import argparse
import logging
import threading
from datetime import datetime as dt
from pathlib import Path
import struct
import zmq
import socket
import time


def get_local_ip():
    local_ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [
        [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
         [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
    return local_ip


class ZMQ_Output:
    """Streams video frames via ZMQ."""

    def __init__(self, source, zmq_ctx, zmq_port, zmq_topic):
        self.source_path = source
        self.zmq_topic = zmq_topic.encode()

        self.socket = zmq_ctx.socket(zmq.PUB)
        self.target = 'tcp://*:{port:d}'.format(port=zmq_port)
        logging.debug('Binding stream at {}'.format(self.target))
        self.socket.bind(self.target)

        self.last_write = dt.utcnow().timestamp()
        self.hostname = socket.gethostname()
        self.__hostname_8 = self.hostname[:8].encode()

        self.frame_index = -1

    def write(self, buf):
        """Handle a new frame."""
        callback_clock = dt.utcnow()
        callback_clock_ts = callback_clock.timestamp()
        callback_gpu_ts = time.monotonic()

        frame_index = self.frame_index
        frame_gpu_ts = time.monotonic()

        metadata = self.__hostname_8 + struct.pack('qqqd', frame_index, frame_gpu_ts, callback_gpu_ts,
                                                   callback_clock_ts)
        message = [self.zmq_topic, metadata, buf]

        self.socket.send_multipart(message)
        self.last_write = callback_clock_ts

def main():
    hostname = socket.gethostname()
    logging.info('Starting host {} @ {} with topic {}'.format(hostname, get_local_ip(), zmq_topic))