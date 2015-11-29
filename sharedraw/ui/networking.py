import base64
import logging
from threading import Event, Thread
from socket import *

from sharedraw.concurrent.threading import TimerThread
from sharedraw.ui.messages import Message


__author__ = 'michalek'
logger = logging.getLogger(__name__)

# TODO:: przenieść


class Peer(Thread):
    def __init__(self, sock: SocketType, stop_event: Event):
        super().__init__()
        self.sock = sock
        self.stop_event = stop_event
        logger.debug("Peer created: %s, %s" % sock.getsockname())

    def send(self, data):
        self.sock.send(data)
        # FIXME do zastanowienia się, co to w sumie ma być
        logger.info("Packet sent")

    def receive(self):
        while not self.stop_event.is_set():
            msg = self.sock.recv(1024)
            if not msg:
                continue
            logger.info('Packet received: %s' % msg[0])
            # conn.close()
        self.sock.close()

    def run(self):
        self.receive()


class PeerPool(Thread):
    peers = {}

    def __init__(self, port: int, stop_event: Event):
        Thread.__init__(self)
        self.port = port
        self.server_sock = None
        self.running = True
        self.stop_event = stop_event

    def run(self):
        logger.info("Tworzę gniazdo...: port: %s" % self.port)
        sock = self.server_sock = socket(AF_INET, SOCK_STREAM)
        sock.bind(('localhost', self.port))
        sock.listen(1)
        while self.running:
            try:
                sock.settimeout(1)
                conn, addr = sock.accept()
                sock.settimeout(None)
                peer = Peer(conn, self.stop_event)
                self.peers[addr] = peer
                peer.start()
            except timeout:
                pass
            except error:
                pass
        sock.close()

    def connect_to(self, ip, port: int):
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((ip, port))
        peer = Peer(sock, self.stop_event)
        self.peers[ip] = peer
        peer.start()

    def send(self, data: Message):
        jsondata = data.to_json()
        bytedata = bytes(jsondata, encoding='utf8')
        if not self.peers:
            logger.debug("No peers connected!")
            return
        for key, peer in self.peers.items():
            peer.send(bytedata)

    def stop(self):
        self.running = False
        if self.server_sock:
            # s = socket(AF_INET, SOCK_STREAM)
            # s.connect(('localhost', self.port))
            # s.close()
            self.server_sock.close()
        for key, peer in self.peers.items():
            peer.sock.close()

#
# class SenderThread(TimerThread):
#     def __init__(self, ui: SharedrawUI, stopped: Event, port: int):
#         TimerThread.__init__(self, stopped, 3.0)
#         self.ui = ui
#         self.stopped = stopped
#         self.port = port
#         self.socket = socket(AF_INET, SOCK_STREAM)
#         self.socket.connect((TCP_IP, port))
#
#     def execute(self):
#         b64img = base64.b64encode(self.ui.get_png())
#         self.socket.sendto(b64img)
#         logger.info("Packet broadcasted.")
#
#
# class ReceiverThread(Thread):
#     def __init__(self, stopped: Event, port: int):
#         Thread.__init__(self)
#         self.stopped = stopped
#         self.port = port
#         # self.socket.setblocking(False)
#
#     def run(self):
#         sock = socket(AF_INET, SOCK_STREAM)
#         sock.bind((TCP_IP, self.port))
#         sock.listen(1)
#         # sock.settimeout(1)
#         while not self.stopped.is_set():
#             try:
#                 conn, addr = sock.accept()
#                 msg = conn.recv(1024)
#                 if not msg:
#                     continue
#                 logger.info('Packet received: %s' % msg[0])
#                 conn.close()
#             except socket.timeout:
#                 pass