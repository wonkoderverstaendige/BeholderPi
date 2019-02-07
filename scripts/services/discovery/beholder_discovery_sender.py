#!/usr/bin/env python3

"""Send IP and hostname information. As a broadcast message via UDP, or TCP to a known host IP."""
import socket
import time
import sys

if len(sys.argv) > 1:
    HOST = sys.argv[1]
else:
    HOST = '131.174.140.26'


PORT = 18000

RECONNECT_WAIT = 3
SEND_INTERVAL = 3

TYPE = 'UDP'


def my_ip():
    # return (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [
    #     [(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
    #      [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0] + '\n'
    return (([[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in
         [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0] + '\n'


def my_hostname():
    return socket.gethostname()


def serve_tcp():
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print('Connecting to {}:{}'.format(HOST, PORT))
            try:
                s.connect((HOST, PORT))
            except (ConnectionRefusedError, OSError) as e:
                print('Connection failed!', e)
            else:
                while True:
                    info = '{}:{}'.format(my_hostname(), my_ip())
                    print('Sending', info)
                    try:
                        s.sendall(str.encode(info))
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
            info = '{}:{}'.format(my_hostname(), my_ip())
            print('Sending', info)
            s.sendto(str.encode(info), ('<broadcast>', 50101))
            time.sleep(SEND_INTERVAL)


if __name__ == '__main__':
    if TYPE == 'TCP':
        serve_tcp()

    elif TYPE == 'UDP':
        serve_udp()

    else:
        raise NotImplementedError
