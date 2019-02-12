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
import json
from math import fabs

TYPE = 'UDP'
HOST = ''
PORT = 50101

LIFESIGN_LAG = 5
LIFESIGN_TIMEOUT = 10


_STOP = threading.Event()

Clients = {}
packet_queue = Queue()


def update_loop(stdscr, ev_stop, client_dict):
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
    curses.init_pair(5, curses.COLOR_MAGENTA, curses.COLOR_BLACK)

    status_color_map = {'alive': 2,
                        'delay': 3,
                        'lost': 4,
                        'fault': 5}

    # frame_top = ' ┌' + '─' * 17 + '┬' + '─' * 18 + '┬' + '─' * 15 + '┐\n'
    # table_header = ' │ {: ^15s} │ {: ^16s} │ {: ^13s} │\n'.format("Hostname", "IP", "STATUS")
    # frame_top_lower = ' ├' + '─' * 17 + '┼' + '─' * 18 + '┼' + '─' * 15 + '┤\n'
    # table_row = ' │ {: <15s} │ {: <16s} │ '
    # frame_bottom = ' └' + '─' * 17 + '┴' + '─' * 18 + '┴' + '─' * 15 + '┘\n'

    columns = [('hostname', 'Hostname', 17),
               ('src_ip', 'Source IP', 18),
               # ('mac', 'MAC', 19),
               ('tzdelta', 'Delta', 8),
               ('last_seen', 'Seen', 7),
               ('status', 'Status', 10)]

    frame_top = ' ┌' + '┬'.join(['─' * c[2] for c in columns]) + '┐\n'
    header_template = ' │' + '│'.join(['{: ^'+str(c[2])+'s}' for c in columns]) + '│\n'
    table_header = header_template.format(*[c[1] for c in columns])

    frame_top_lower = ' ├' + '┼'.join(['─' * c[2] for c in columns]) + '┤\n'
    frame_bottom = ' └' + '┴'.join(['─' * c[2] for c in columns]) + '┘\n'

    while not ev_stop.is_set():
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
        #
        # # Process new packets
        # while True:
        #     try:
        #         packet = packet_queue.get(timeout=.1)
        #     except Empty:
        #         break
        #
        #     if None in packet:
        #         continue
        #
        #     client_dict[packet['src_ip']] = packet

        # Show current clients
        if stdscr is not None:
            stdscr.clear()
            stdscr.addstr(frame_top, curses.color_pair(1))
            stdscr.addstr(table_header, curses.color_pair(1))
            stdscr.addstr(frame_top_lower, curses.color_pair(1))

            for src_ip in sorted(client_dict):
                host = client_dict[src_ip]

                delta = (time.time() - host['arrival'])
                if host['data'] == 'invalid':
                    hostname = ''
                    status = 'FAULT'
                else:
                    hostname = host['hostname']
                    if delta < LIFESIGN_TIMEOUT:
                        status = 'ALIVE'
                    elif delta < LIFESIGN_LAG:
                        status = 'DELAY'
                    else:
                        status = 'LOST'

                stdscr.addstr(' ', curses.color_pair(1))
                for col in columns:
                    if col[0] == 'status':
                        stdscr.addstr('│ ', curses.color_pair(1))
                        status_color = status_color_map[status.lower()]
                        al_str = '{: <5s}'.format(status)
                        stdscr.addstr(al_str, curses.color_pair(status_color))
                        stdscr.addstr(' ' * (col[2] - 1 - len(al_str)) + '│\n', curses.color_pair(1))
                    else:
                        value = ''
                        cp = 1
                        if col[0] == 'mac' and col[0] in host:
                            value = host['mac']
                        elif col[0] == 'hostname':
                            value = hostname
                        elif col[0] == 'src_ip':
                            value = src_ip
                        elif col[0] == 'tzdelta':
                            if 'localtime' in host:
                                t_diff = host['arrival'] - host['localtime']
                                if fabs(t_diff) < 1/1000:
                                    cp = 2
                                elif fabs(t_diff) < 3/1000:
                                    cp = 3
                                else:
                                    cp = 4
                                value = t_str(t_diff, ms=True)

                        elif col[0] == 'last_seen':
                            value = t_str(delta)

                        stdscr.addstr('│ ', curses.color_pair(1))
                        cell = '{: <' + str(col[2] - 1) + 's}'
                        stdscr.addstr(cell.format(str(value)), curses.color_pair(cp))

            stdscr.addstr(frame_bottom, curses.color_pair(1))
            stdscr.refresh()

        time.sleep(.5)


def process_packet(data):
    try:
        data_dict = json.loads(bytes.decode(data))
        data_dict['data'] = 'valid'
    except json.JSONDecodeError:
        data_dict = {'data': 'invalid'}

    # Add arrival timestamp
    data_dict['arrival'] = time.time()
    return data_dict


def t_str(s, precision='2.1', ms=False):
    """Turn time delta in seconds into short string across time scales."""
    # TODO: Handle negative differences!
    fmt_str = '{: >' + precision + 'f}'
    if s < 1 and ms:
        return '{: >3.1f}'.format(s*1000) + ' ms'

    if s < 60:
        return fmt_str.format(s) + ' s'

    m = s / 60
    if m < 60:
        return fmt_str.format(m) + ' m'

    h = m / 60
    if h < 24:
        return fmt_str.format(h) + ' h'

    d = h / 24
    if d < 30:
        return fmt_str.format(d) + ' d'

    return 'Inf'


class MyTCPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        packet = process_packet(self.request.recv(1024).strip())
        if packet is not None:
            # packet_queue.put(packet)
            Clients[self.client_address[0]] = packet


class MyUDPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        packet = process_packet(self.request[0].strip())
        if packet is not None:
            # packet_queue.put(packet)
            Clients[self.client_address[0]] = packet


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
        rt = threading.Thread(target=update_loop, args=(stdscr, _STOP, Clients,))
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

    # # print list on exit, for easy access
    # for client, values in Clients.items():
    #     print(values[0], client, time.time() - values[1])
    print(Clients)
