#!/usr/bin/env python3

import socket
import time

PORT = 18000
HOST = '131.174.140.26'

RECONNECT_WAIT = 3
SEND_INTERVAL = 3

def my_ip():
    return (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0] + '\n'

def hostname():
    return socket.gethostname()

while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        print('Connecting...')
        try:
            s.connect((HOST, PORT))
        except (ConnectionRefusedError, OSError) as e:
            print('Connection failed!', e)
        else:
            while True:
                info = '{}: {}'.format(hostname(), my_ip())
                print('Sending', info)
                try:
                    s.sendall(str.encode(info))
                    time.sleep(SEND_INTERVAL)
                except BrokenPipeError:
                    s.close()
                    break
    time.sleep(RECONNECT_WAIT)
                    
