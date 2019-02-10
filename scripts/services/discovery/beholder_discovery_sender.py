#!/usr/bin/env python3

"""Send IP and hostname information. As a broadcast message via UDP, or TCP to a known host IP."""
import socket
import time
import sys
import json

if len(sys.argv) > 1:
    HOST = sys.argv[1]
else:
    HOST = '10.0.0.11'

TCP_PORT = 18000
UDP_PORT = 50101

RECONNECT_WAIT = 3
SEND_INTERVAL = 3

TYPE = 'UDP'


def my_ip():
    # NB: This causes issue when the hostname is not configured properly
    # return (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [
    #     [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
    #      [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0] + '\n'

    # This still works
    return (([[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
               [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]


def my_hostname():
    return socket.gethostname()


def gather_info():
    info = {'ip': my_ip(),
            'hostname': my_hostname(),
            'mac': '00:00:00:00:00:00',
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
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            info_json = json.dumps(gather_info())
            print('Sending', info_json)
            s.sendto(str.encode(info_json), ('<broadcast>', UDP_PORT))
            time.sleep(SEND_INTERVAL)


if __name__ == '__main__':
    if TYPE == 'TCP':
        serve_tcp()

    elif TYPE == 'UDP':
        serve_udp()

    else:
        raise NotImplementedError
