#!/usr/bin/env python3

"""Send IP and hostname information. As a broadcast message via UDP, or TCP to a known host IP."""
import socket
import time
import sys
import json
import uuid

if len(sys.argv) > 1:
    HOST = sys.argv[1]
else:
    HOST = '10.0.0.11'

TCP_PORT = 18000
UDP_PORT = 50101

RECONNECT_WAIT = 3
SEND_INTERVAL = 1

TYPE = 'UDP'


def get_ip():
    return (([[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
               [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]


def get_hostname():
    return socket.gethostname()


def get_mac():
    mac = str(hex(uuid.getnode()))[2:]
    return ":".join([mac[i:i+2] for i in range(0, len(mac), 2)])


def gather_info():
    info = {'ip': get_ip(),
            'hostname': get_hostname(),
            'mac': get_mac(),
            'localtime': time.time()
            }
    return info


def serve_tcp():
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print('Connecting to {}:{}'.format(HOST, TCP_PORT))
            try:
                s.connect((HOST, TCP_PORT))
            except (ConnectionRefusedError, OSError) as e:
                print('Connection failed!', e)
            else:
                while True:
                    info_json = json.dumps(gather_info())
                    print('Sending', info_json)
                    try:
                        s.sendall(str.encode(info_json))
                        time.sleep(SEND_INTERVAL)
                    except (BrokenPipeError, ConnectionResetError) as e:
                        print('Connection closed:', e)
                        s.close()
                        break
        time.sleep(RECONNECT_WAIT)


def serve_udp():
    # TODO: Needs error checking and reconnect on connection change
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            info_json = json.dumps(gather_info())
            s.sendto(str.encode(info_json), ('<broadcast>', UDP_PORT))
            time.sleep(SEND_INTERVAL)


if __name__ == '__main__':
    if TYPE == 'TCP':
        serve_tcp()

    elif TYPE == 'UDP':
        serve_udp()

    else:
        raise NotImplementedError
