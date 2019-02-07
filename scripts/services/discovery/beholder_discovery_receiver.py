#!/usr/bin/env python3

"""Awaits discovery messages from the eyes.

Based on https://docs.python.org/3/library/socketserver.html#socketserver-tcpserver-example

The 'protocol' is extremely weak as of now. But all we need is to discover the IPs of new nodes. Once discovered,
ansible will be able to take care of the rest.

To not require a fixed server location, the eyes will broadcast a UDP based message. That should work in the
local network as well as the uni LAN.
"""
import socketserver
import threading
from queue import Queue, Empty
import curses
import time
import signal

TYPE = 'UDP'
HOST = ''
PORT = 50101

LIFESIGN_LAG = 5
LIFESIGN_TIMEOUT = 10


_STOP = threading.Event()

Clients = {}
packet_queue = Queue()


def update(stdscr, ev_stop):
    curses.curs_set(0)
    curses.start_color()
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    stdscr.nodelay(1)

    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK)

    FRAME_TOP = ' ┌' + '─' * 17 + '┬' + '─' * 18 + '┬' + '─' * 15 + '┐\n'
    FRAME_HEADER = ' │ {: ^15s} │ {: ^16s} │ {: ^13s} │\n'.format("Hostname", "IP", "STATUS")
    FRAME_TOP_LOW = ' ├' + '─' * 17 + '┼' + '─' * 18 + '┼' + '─' * 15 + '┤\n'
    FRAME_ROW = ' │ {: <15s} │ {: <16s} │ '
    FRAME_BOTTOM = ' └' + '─' * 17 + '┴' + '─' * 18 + '┴' + '─' * 15 + '┘\n'

    while not ev_stop.is_set():
        # Process user input
        try:
            c = stdscr.getkey()
            if c == 'q':
                ev_stop.set()
                break

        except curses.error:
            pass

        # Process new packets
        while True:
            try:
                packet = packet_queue.get(timeout=.1)
            except Empty:
                break

            if None in packet:
                continue

            ip, hostname, addr, ts = packet
            if ip != addr:
                raise LookupError('Reported and sent IPs do not match: {} vs {}'.format(ip, addr))

            Clients[ip] = (hostname, ts)

        # Show current clients
        if stdscr is not None:
            stdscr.clear()
            stdscr.addstr(FRAME_TOP, curses.color_pair(1))
            stdscr.addstr(FRAME_HEADER, curses.color_pair(1))
            stdscr.addstr(FRAME_TOP_LOW, curses.color_pair(1))

            for client, (hostname, ts) in Clients.items():
                delta = (time.time() - ts)
                cp = 2
                if delta > LIFESIGN_LAG:
                    cp = 3
                if delta > LIFESIGN_TIMEOUT:
                    cp = 4

                stdscr.addstr(FRAME_ROW.format(hostname, client), curses.color_pair(1))
                al_str = '{: <5s} ({: <3.1f}s)'.format("ALIVE" if delta < LIFESIGN_TIMEOUT else "LOST", delta)
                stdscr.addstr(al_str, curses.color_pair(cp))
                stdscr.addstr(' ' * (14 - len(al_str)) + '│\n', curses.color_pair(1))

            stdscr.addstr(FRAME_BOTTOM, curses.color_pair(1))
            stdscr.refresh()

        time.sleep(.5)


def extract(data):
    data_str = bytes.decode(data)
    try:
        if ':' in data_str:
            ip, host = data_str.split(':')
            return ip.strip(), host.strip()

    except ValueError:
        print('Data invalid')

    print('returning None')
    return None, None


class MyTCPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        client_ip, client_hostname = extract(self.request.recv(1024).strip())
        packet = (client_ip, client_hostname, self.client_address[0], time.time(),)
        packet_queue.put(packet)


class MyUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        client_hostname, client_ip = extract(self.request[0].strip())
        packet = (client_ip, client_hostname, self.client_address[0], time.time(),)
        packet_queue.put(packet)


def main(stdscr):
    # Server
    if TYPE == 'TCP':
        cls_server = socketserver.TCPServer
        cls_handler = MyTCPHandler

    elif TYPE == 'UDP':
        cls_server = socketserver.UDPServer
        cls_handler = MyUDPHandler

    else:
        raise NotImplementedError

    with cls_server((HOST, PORT), cls_handler) as server:
        st = threading.Thread(target=server.serve_forever)
        # st.daemon = True
        st.start()

        # Reporter thread
        rt = threading.Thread(target=update, args=(stdscr, _STOP, ))
        # rt.daemon = True
        rt.start()

        while not _STOP.is_set():
            time.sleep(.1)

        server.shutdown()
        st.join()
        rt.join()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    finally:
        curses.curs_set(1)

    # print list on exit, for easy access
    for client, values in Clients.items():
        print(values[0], client, time.time() - values[1])
