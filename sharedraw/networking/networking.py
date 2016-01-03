import random
import string
from datetime import datetime
from queue import Queue
from socket import *
from threading import Event, Thread

from sharedraw.networking.messages import *

__author__ = 'michalek'
logger = logging.getLogger(__name__)

# TODO:: przenieść


def get_own_id():
    datepart = datetime.now().strftime("%H%M%S%f")
    randompart = ''.join(
        random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for _ in range(6))
    return datepart + randompart


own_id = get_own_id()


class Peer(Thread):
    """
    Inna maszyna, do której jesteśmy podłączeni
    """

    def __init__(self, sock: SocketType, stop_event: Event, queue_to_ui: Queue):
        super().__init__()
        self.client_id = None
        self.sock = sock
        self.stop_event = stop_event
        self.queue_to_ui = queue_to_ui
        self.setDaemon(True)
        logger.debug("Peer created: %s, %s" % sock.getsockname())

    def is_registered(self):
        """ Zwraca, czy peer potwiedził swoje przyłączenie tj. wysłał komunikat "joined"
        :return:
        """
        return self.client_id is not None

    def send(self, data):
        """
        Wysyła dane do peera
        :param data: dane (jako bajty)
        :return: nic
        """
        self.sock.send(data)
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
            if type(rcm) is JoinMessage:
                # Rejestrujemy klienta
                self.client_id = rcm.client_id
                # TODO:: odsyłamy mu ImageMessage
            elif type(rcm) is ImageMessage:
                # Drugi klient potwiedził podłączenie i przesłał nam obrazek
                # Rejestrujemy
                self.client_id = rcm.client_id
                # TODO:: aktualizujemy obrazek w UI
            else:
                # Ładujemy do kolejki - kontroler obsłuży
                self.queue_to_ui.put(rcm)
                # TODO:: trzeba jeszcze wysłać do pozostałych
        self.sock.close()

    def run(self):
        """
        Pętla wątku peera
        """
        # Wysyłamy wiadomość "join"
        msg = JoinMessage(own_id)
        jsondata = msg.to_json()
        bytedata = bytes(jsondata, encoding='utf8')
        self.send(bytedata)

        # Wchodzimy w tryb odbierania
        self.receive()


class PeerPool(Thread):
    """
    Pula peerów, do których jesteśmy podłączeni
    """
    peers = []

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
                self.peers.append(peer)
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
        self.peers.append(peer)
        peer.start()

    def send(self, data: Message, excluded_client_id=None):
        """ Wysyła dane do wszystkich zarejestrowanych klientów klientów
        :param data: dane komunikatu
        :param excluded_client_id: klient, którego należy pominąć przy wysyłaniu
        """
        jsondata = data.to_json()
        bytedata = bytes(jsondata, encoding='utf8')
        if not self.peers:
            logger.debug("No peers connected!")
            return
        for peer in self.peers:
            if peer.is_registered() and peer.client_id != excluded_client_id:
                peer.send(bytedata)

    def stop(self):
        """
        Zatrzymuje serwer i klientów
        """
        self.running = False
        if self.server_sock:
            self.server_sock.close()
        for peer in self.peers:
            peer.sock.close()