import random
import string
from datetime import datetime
from queue import Queue
from socket import *
from threading import Event, Thread

from sharedraw.config import config
from sharedraw.concurrent.threading import TimerThread
from sharedraw.networking.messages import *

__author__ = 'michalek'
logger = logging.getLogger(__name__)


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
        self.enabled = True
        self.setDaemon(True)
        self.last_alive = datetime.now()
        logger.debug("Peer created: %s, %s" % sock.getsockname())

    def is_active(self):
        """ Zwraca klient jest aktywny tj. może się komunikować
        :return: wartość logiczna
        """
        return self.enabled and self.is_registered()

    def is_registered(self):
        """ Zwraca, czy peer potwiedził swoje przyłączenie tj. wysłał komunikat "joined"
        :return: wartość logiczna
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
        while self.enabled and not self.stop_event.is_set():
            msg = self.sock.recv(65536)
            if not msg:
                continue
            data = msg.decode("utf-8")
            logger.info('Packet received: %s' % data)
            rcm = from_json(data)
            if type(rcm) is JoinMessage:
                if not self.is_registered():
                    # Nowy klient podłączył się do nas i wysłał join
                    # Rejestrujemy klienta
                    self.client_id = rcm.client_id
                    # TODO:: odsyłamy mu ImageMessage
                # else: inny klient rozpropagował nam join
            elif type(rcm) is ImageMessage:
                # Drugi klient potwiedził podłączenie i przesłał nam obrazek
                # Rejestrujemy
                self.client_id = rcm.client_id
                # Aktualizujemy obrazek w UI - w ramach kontrolera
            elif type(rcm) is KeepAliveMessage:
                # KeepAlive - aktualizujemy datę
                self.last_alive = datetime.now()
                # Nieprzesyłany dalej
                continue
            elif type(rcm) is QuitMessage:
                if rcm.client_id == self.client_id:
                    # Sam zdecydował się odejść - odłączamy
                    self.enabled = False
                # W kontrolerze klient usunięty
            # Ładujemy do kolejki - kontroler obsłuży
            self.queue_to_ui.put(SignedMessage(self.client_id, rcm))
            # Wysłanie do pozostałych klientów w kontrolerze
        self.sock.close()

    def run(self):
        """
        Pętla wątku peera
        """
        # Wysyłamy wiadomość "join"
        msg = JoinMessage(own_id)
        self.send(msg.to_bytes())

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
        if not self.peers:
            logger.debug("No peers connected!")
            return
        for peer in self.peers:
            bytedata = data.to_bytes()
            if peer.is_active() and peer.client_id != excluded_client_id:
                try:
                    peer.send(bytedata)
                except ConnectionError:
                    logger.error("Error during sending to peer: %s. DISCONNECTING" % peer.client_id)
                    self.__remove_peer(peer)

    def check_alive(self):
        """ Sprawdza, czy klienci są żywi i wyłącza ich, jeśli nie
        """
        for peer in self.peers:
            since_last_alive = datetime.now() - peer.last_alive
            if since_last_alive.total_seconds() > config.keep_alive_timeout:
                logger.warn("Timeout exceeded: peer %s was last alive %s ago. DISCONNECTING" % (
                    peer.client_id, since_last_alive))
                self.__remove_peer(peer)

    def __remove_peer(self, peer: Peer):
        """ Odłącza wybranego klienta
        :param peer: klient
        """
        peer.enabled = False
        self.peers.remove(peer)
        # Wysyłamy do kontrolera info o usunięciu - zostanie rozpropagowane
        self.queue_to_ui.put(SignedMessage(own_id, QuitMessage(str(peer.client_id))))

    def stop(self):
        """
        Zatrzymuje serwer i klientów
        """
        # Wysyłamy quit do wszystkich
        self.send(QuitMessage(own_id))
        # Zamykamy wszystko
        self.running = False
        if self.server_sock:
            self.server_sock.close()
        for peer in self.peers:
            peer.sock.close()


class KeepAliveSender(TimerThread):
    """ Wątek wysyłający co zadany interwał komunikat typu KeepAlive
    """

    def __init__(self, stopped, peer_pool: PeerPool):
        super().__init__(stopped, config.keep_alive_interval)
        self.peer_pool = peer_pool

    def execute(self):
        msg = KeepAliveMessage(own_id)
        self.peer_pool.send(msg)
        # Sprawdzamy, czy klienty są aktywne - TODO:: może inne zadanie na to?
        self.peer_pool.check_alive()