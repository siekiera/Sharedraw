from datetime import datetime
from queue import Queue
from socket import *
from threading import Event, Thread

from sharedraw.config import config
from sharedraw.concurrent.threading import TimerThread
from sharedraw.networking.messages import *


__author__ = 'michalek'
logger = logging.getLogger(__name__)


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
        self.is_incoming = False
        self.setDaemon(True)
        self.last_alive = datetime.now()
        logger.debug("Peer created: %s, %s" % sock.getpeername())

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
        logger.info("Packet sent: %s" % data.decode("utf-8"))

    def receive(self):
        """ Odczytuje dane z gniazda
        """
        builder = MessageBuilder()
        while self.enabled and not self.stop_event.is_set():
            try:
                msg = self.sock.recv(65536)
                if not msg:
                    continue
                full_msg = builder.append(msg).fetch()
                if not full_msg:
                    logger.debug("Raw received data: %s" % msg)
                    continue
                data = full_msg.decode("utf-8")
                logger.info('Packet received: %s' % data)
                rcm = from_json(data)
                if not rcm:
                    continue
                if type(rcm) is JoinMessage:
                    if not self.is_registered():
                        # Nowy klient podłączył się do nas i wysłał join
                        # Rejestrujemy klienta
                        self.client_id = rcm.client_id
                        # Sam się zgłosił - w kontrolerze odsyłamy mu ImageMessage
                        rcm.received_from_id = None
                    else:
                        rcm.received_from_id = self.client_id
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
                # elif type(rcm) is QuitMessage:
                #     if rcm.client_id == self.client_id:
                #         # Sam zdecydował się odejść - odłączamy
                #         self.enabled = False
                #         W kontrolerze klient usunięty
                # Ładujemy do kolejki - kontroler obsłuży
                self.queue_to_ui.put(SignedMessage(self.client_id, rcm))
                # Wysłanie do pozostałych klientów w kontrolerze
            except OSError:
                logger.warn("Connection error: %s" % str(sys.exc_info()))
                self.enabled = False
                break
        self.sock.close()

    def run(self):
        """
        Pętla wątku peera
        """
        if not self.is_incoming:
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
        self.ip = gethostbyname(gethostname())
        self.setDaemon(True)

    def run(self):
        """
        Główna pętla wątku, otwiera gniazdo serwera i przyjmuje połączenia
        """
        logger.info("Creating socket...: port: %s" % self.port)
        sock = self.server_sock = socket(AF_INET, SOCK_STREAM)
        # Dzięki tej opcji gniazda nie powinny zostawać otwarte
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind((self.ip, self.port))
        sock.listen(1)
        while self.running:
            try:
                sock.settimeout(1)
                conn, addr = sock.accept()
                sock.settimeout(None)
                peer = Peer(conn, self.stop_event, self.queue_to_ui)
                self.peers.append(peer)
                peer.is_incoming = True
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
        """ Wysyła dane do wszystkich zarejestrowanych klientów
        :param data: dane komunikatu
        :param excluded_client_id: klient, którego należy pominąć przy wysyłaniu
        """
        if not self.peers:
            logger.debug("No peers connected!")
            return
        for peer in self.peers:
            bytedata = data.to_bytes()
            if peer.is_active() and peer.client_id != excluded_client_id:
                self.__send_to_peer(peer, bytedata)

    def send_to_client(self, msg: Message, client_id: str):
        """ Wysyła komunikat do klienta o podanym identyfikatorze
        :param msg: dane komunikat
        :param client_id: identyfikator klienta
        """
        for peer in self.peers:
            if peer.client_id == client_id:
                if peer.is_active():
                    self.__send_to_peer(peer, msg.to_bytes())
                else:
                    logger.warn("Peer %s not active!" % client_id)
                return
        logger.warn("Client with id: %s not found" % client_id)

    def __send_to_peer(self, peer: Peer, bytedata: bytes):
        """ Wysyła dane do danego klienta
        W przypadku błędu komunikacji klient jest usuwany.
        :param peer: klient
        :param bytedata: dane
        """
        try:
            peer.send(bytedata)
        except OSError:
            logger.error("Error during sending to peer: %s. DISCONNECTING" % peer.client_id)
            self.__remove_peer(peer)

    def check_alive(self):
        """ Sprawdza, czy klienci są żywi i wyłącza ich, jeśli nie
        """
        for peer in self.peers:
            if not peer.enabled:
                logger.warn("Peer %s has been disabled, removing" % peer.client_id)
                self.__remove_peer(peer)
                continue
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
        self.queue_to_ui.put(SignedMessage(own_id, InternalQuitMessage(str(peer.client_id))))

    def stop(self):
        """
        Zatrzymuje serwer i klientów
        """
        # Wysyłamy quit do wszystkich
        # self.send(QuitMessage(own_id))
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
        # TODO:: nie wysyłamy KeepAlive - należy za to włączyć tę opcję w gnieździe TCP
        # msg = KeepAliveMessage(own_id)
        # self.peer_pool.send(msg)
        # Sprawdzamy, czy klienty są aktywne - TODO:: może inne zadanie na to?
        self.peer_pool.check_alive()


class MessageBuilder():
    """ Klasa do budowania komunikatów - niektóre klienty wysyłają je w częściach, zatem trzeba poskładać do całości
    """

    def __init__(self):
        self.msg = bytes()
        self.left_par_count = 0
        self.right_par_count = 0

    def append(self, rawdata: bytes):
        """ Dodaje bajty to buildera
        :param rawdata: bajty (część komunikatu)
        :return: instancja buildera
        """
        self.msg += rawdata
        self._parse_pars(rawdata)
        return self

    def fetch(self):
        """ Pobiera komunikat
        Jeśli komunikat jest błędny lub niedokończony zwraca None
        :return: pełny komunikat w postaci bajtów lub None, jeśli się nie da
        """
        if self.left_par_count == self.right_par_count:
            # Komunikat zakończony - zwracamy
            result = self.msg
        elif self.left_par_count > self.right_par_count:
            # Komunikat niedokończony - zwracamy None, zostanie dokończony potem
            logger.debug("Received incomplete message... waiting for the rest")
            return None
        else:
            # Komunikat błędny
            logger.error("Invalid message - contains more right parenthesis than left. Dropping")
            result = None
        self._reset()
        return result

    def _parse_pars(self, rawdata: bytes):
        for byte in rawdata:
            char = chr(byte)
            if char == '{':
                self.left_par_count += 1
            elif char == '}':
                self.right_par_count += 1

    def _reset(self):
        self.msg = bytes()
        self.left_par_count = 0
        self.right_par_count = 0
