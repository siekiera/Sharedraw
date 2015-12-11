import logging
from queue import Queue
from threading import Event, Thread
from socket import *

from sharedraw.ui.messages import Message, from_json


__author__ = 'michalek'
logger = logging.getLogger(__name__)

# TODO:: przenieść


class Peer(Thread):
    """
    Inna maszyna, do której jesteśmy podłączeni
    """

    def __init__(self, sock: SocketType, stop_event: Event, queue_to_ui: Queue):
        super().__init__()
        self.sock = sock
        self.stop_event = stop_event
        self.queue_to_ui = queue_to_ui
        self.setDaemon(True)
        logger.debug("Peer created: %s, %s" % sock.getsockname())

    def send(self, data):
        """
        Wysyła dane do peera
        :param data: dane (jako bajty)
        :return: nic
        """
        self.sock.send(data)
        # FIXME do zastanowienia się, co to w sumie ma być
        logger.info("Packet sent")

    def receive(self):
        """ Odczytuje dane z gniazda
        """
        while not self.stop_event.is_set():
            msg = self.sock.recv(65536)
            if not msg:
                continue
            data = msg.decode("utf-8")
            logger.info('Packet received: %s' % data)
            rcm = from_json(data)
            self.queue_to_ui.put(rcm)
            # conn.close()
        self.sock.close()
        # TODO:: trzeba jeszcze wysłać do pozostałych

    def run(self):
        """
        Pętla wątku peera
        """
        self.receive()


class PeerPool(Thread):
    """
    Pula peerów, do których jesteśmy podłączeni
    """
    peers = {}

    def __init__(self, port: int, stop_event: Event, queue_to_ui: Queue):
        Thread.__init__(self)
        self.port = port
        self.server_sock = None
        self.running = True
        self.stop_event = stop_event
        self.queue_to_ui = queue_to_ui
        self.setDaemon(True)

    def run(self):
        """
        Główna pętla wątku, otwiera gniazdo serwera i przyjmuje połączenia
        """
        logger.info("Tworzę gniazdo...: port: %s" % self.port)
        sock = self.server_sock = socket(AF_INET, SOCK_STREAM)
        # Dzięki tej opcji gniazda nie powinny zostawać otwarte
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind(('localhost', self.port))
        sock.listen(1)
        while self.running:
            try:
                sock.settimeout(1)
                conn, addr = sock.accept()
                sock.settimeout(None)
                peer = Peer(conn, self.stop_event, self.queue_to_ui)
                self.peers[addr] = peer
                peer.start()
            except timeout:
                pass
            except error:
                pass
        sock.close()

    def connect_to(self, ip, port: int):
        """ Nawiązuje połączenie z innym klientem

        :param ip: ip (string)
        :param port: port (int)
        :return: nic
        """
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((ip, port))
        peer = Peer(sock, self.stop_event, self.queue_to_ui)
        self.peers[ip] = peer
        peer.start()

    def send(self, data: Message):
        """ Wysyła dane do wszystkich podłączonych klientów
        :param data: dane komunikatu
        """
        jsondata = data.to_json()
        bytedata = bytes(jsondata, encoding='utf8')
        if not self.peers:
            logger.debug("No peers connected!")
            return
        for key, peer in self.peers.items():
            peer.send(bytedata)

    def stop(self):
        """
        Zatrzymuje serwer i klientów
        """
        self.running = False
        if self.server_sock:
            self.server_sock.close()
        for key, peer in self.peers.items():
            peer.sock.close()