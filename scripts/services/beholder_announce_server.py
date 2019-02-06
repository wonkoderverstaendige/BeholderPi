#!/usr/bin/env python3

"""Awaits discovery messages from the eyes.

Based on https://docs.python.org/3/library/socketserver.html#socketserver-tcpserver-example

The 'protocol' is extremely weak as of now. But all we need is to discover the IPs of new nodes. Once discovered,
ansible will be able to take care of the rest.

To not require a fixed server location, the eyes will broadcast a UDP based message. That should work in the
local network as well as the uni LAN.
"""
# TODO: Thread continuously updating the list of known nodes, based on a timeout. Assuming nodes send out
# their discovery messages every 3 seconds or so, use that as a heartbeat?

import socketserver

TYPE = 'UDP'
HOST = ''
PORT = 50101

Clients = {}


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


def update(ip, hostname, addr):
    if None in [ip, hostname, addr]:
        return

    if ip != addr:
        print(ip, addr)
        raise LookupError('Reported and sent IPs do not match')

    if ip not in Clients:
        print("New client: {} @ {}".format(hostname, ip))
        Clients[ip] = hostname


class MyTCPHandler(socketserver.BaseRequestHandler):
    """
    Request handler class for server

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        data = self.request.recv(1024).strip()

        client_ip, client_hostname = extract(data)
        update(client_ip, client_hostname, self.client_address[0])


class MyUDPHandler(socketserver.BaseRequestHandler):
    """
    This class works similar to the TCP handler class, except that
    self.request consists of a pair of data and client socket, and since
    there is no connection the client address must be given explicitly
    when sending data back via sendto().
    """

    def handle(self):
        data = self.request[0].strip()
        udp_socket = self.request[1]

        client_hostname, client_ip = extract(data)
        update(client_ip, client_hostname, self.client_address[0])

        #
        # print("{} wrote:".format(self.client_address[0]))
        # print(data)
        # udp_socket.sendto(data.upper(), self.client_address)


if __name__ == "__main__":
    if TYPE == 'TCP':
        cls_server = socketserver.TCPServer
        cls_handler = MyTCPHandler

    elif TYPE == 'UDP':
        cls_server = socketserver.UDPServer
        cls_handler = MyUDPHandler

    else:
        raise NotImplementedError

    with cls_server((HOST, PORT), cls_handler) as server:
        server.serve_forever()
