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

TYPE = 'UDP'
HOST = ''
PORT = 50101

LIFESIGN_LAG = 5
LIFESIGN_TIMEOUT = 10


_STOP = threading.Event()

Clients = {}
packet_queue = Queue()


def update(stdscr, ev_stop, client_dict):
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

    frame_top = ' ┌' + '─' * 17 + '┬' + '─' * 18 + '┬' + '─' * 15 + '┐\n'
    table_header = ' │ {: ^15s} │ {: ^16s} │ {: ^13s} │\n'.format("Hostname", "IP", "STATUS")
    frame_top_lower = ' ├' + '─' * 17 + '┼' + '─' * 18 + '┼' + '─' * 15 + '┤\n'
    table_row = ' │ {: <15s} │ {: <16s} │ '
    frame_bottom = ' └' + '─' * 17 + '┴' + '─' * 18 + '┴' + '─' * 15 + '┘\n'

    while not ev_stop.is_set():
        reset = False
        # Process user input
        try:
            c = stdscr.getkey()
            if c == 'q':
                ev_stop.set()
                break
            if c == 'r':
                client_dict.clear()

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

            client_dict[ip] = (hostname, ts)

        # Show current clients
        if stdscr is not None:
            stdscr.clear()
            stdscr.addstr(frame_top, curses.color_pair(1))
            stdscr.addstr(table_header, curses.color_pair(1))
            stdscr.addstr(frame_top_lower, curses.color_pair(1))

            for cl in sorted(client_dict.keys()):
                (hostname, ts) = client_dict[cl]
                delta = (time.time() - ts)
                cp = 2
                if delta > LIFESIGN_LAG:
                    cp = 3
                if delta > LIFESIGN_TIMEOUT:
                    cp = 4

                stdscr.addstr(table_row.format(hostname, cl), curses.color_pair(1))
                al_str = '{: <5s} ({})'.format("ALIVE" if delta < LIFESIGN_TIMEOUT else "LOST", t_str(delta))
                stdscr.addstr(al_str, curses.color_pair(cp))
                stdscr.addstr(' ' * (14 - len(al_str)) + '│\n', curses.color_pair(1))

            stdscr.addstr(frame_bottom, curses.color_pair(1))
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


def t_str(s):
    """Turn time delta in seconds into short string across time scales."""
    if s < 60:
        return '{: >2.1f}s'.format(s)

    m = s / 60
    if m < 60:
        return '{: >2.1f}m'.format(m)

    h = m / 60
    if h < 24:
        return '{: >2.1f}h'.format(h)

    d = h / 24
    if d < 30:
        return '{: >2.1f}d'.format(d)

    return 'Inf'


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
        rt = threading.Thread(target=update, args=(stdscr, _STOP, Clients, ))
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
