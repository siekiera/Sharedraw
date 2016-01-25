import logging
from threading import Timer

from sharedraw.config import own_id, config
from sharedraw.networking.messages import RequestTableMessage, PassTokenMessage, RicartTableRow, ResignMessage
from sharedraw.networking.networking import PeerPool

logger = logging.getLogger(__name__)


class LogicalClock:
    """ Klasa reprezentująca zegar logiczny. Dostępne 2 operacje - zwiększenie i max
    """

    def __init__(self):
        self.__time = 0

    def increase(self):
        """ Jednostkowa operacja zwiększenia czasu logicznego
        :return: wynikowy czas
        """
        self.__time += 1
        return self.__time

    def join(self, other_time: int):
        """ Operacja połączenia czasu logicznego tego zegara z innym
        :param other_time: czas logiczny innego zegara
        :return: wynikowy czas logiczny
        """
        if other_time > self.__time:
            self.__time = other_time
        self.increase()
        return self.__time

    def get(self):
        return self.__time


class ClientsTable:
    """ Klasa trzymająca dane klientów obecnych w systemie rozproszonym
    """

    def __init__(self):
        self.clients = []
        # Domyślnie sami posiadamy; jeśli się do kogoś podłączymy - tracimy
        self.token_owner = own_id
        self.locked = None

    def add(self, client_id: str, received_from_id=None):
        if not self.__find_client(client_id):
            self.clients.append(Client(client_id, received_from_id))

    def remove(self, client_id: str):
        c = self.__find_client(client_id)
        if not c:
            logger.error("Cannot remove client with id: %s - not present in list" % client_id)
        # Usuwamy klienta
        self.clients.remove(c)
        logger.debug("Removed client: %s" % client_id)
        # Usuwamy wszystkich otrzymanych od niego
        for child in filter(lambda ch: ch.received_from_id == client_id, self.clients):
            self.clients.remove(child)
            logger.debug("Removed child %s received from %s" % (child.id, client_id))

    def get_client_ids(self):
        return list(map(lambda c: c.id, self.clients))

    def update_with_id_list(self, client_ids: [], received_from_id: str):
        for client_id in client_ids:
            if client_id != received_from_id:
                self.add(client_id, received_from_id)

    def find_self(self):
        return self.__find_client(own_id)

    def to_ricart(self):
        return list(map(Client.get_rtr, self.clients))

    def update_with_ricart(self, ricart_table: []):
        for rtr in ricart_table:
            client = self.__find_client(rtr.id)
            if not client:
                # Nie powinno się zdarzyć
                logger.warn('Client with id %s from Ricart Table not present in clients table!' % rtr.id)
                return
            # Aktualizujemy
            client.granted = rtr.g
            client.requested = rtr.r

    def __getitem__(self, client_id):
        return self.__find_client(client_id)

    def __find_client(self, client_id: str):
        return next((c for c in self.clients if c.id == client_id), None)


class Client:
    def __init__(self, client_id: str, received_from_id=None):
        self.id = client_id
        self.granted = 0
        self.requested = 0
        self.received_from_id = received_from_id

    def get_rtr(self):
        return RicartTableRow(self.id, self.granted, self.requested)


class OwnershipManager:
    """ Klasa zarządzająca przejmowaniem tablicy na własność
    """

    def __init__(self, clients: ClientsTable, peer_pool: PeerPool):
        self.__clients = clients
        self.__clock = LogicalClock()
        self.__peer_pool = peer_pool

    def claim_ownership(self):
        """ Żąda przejęcia tablicy na własność
        Jeśli jesteśmy w posiadaniu tokena, przejmuje tablicę i wysyła PassTokenMessage
        Jeśli nie - wysyła RequestTableMessage
        :return: wynikowa lista klientów
        """
        has_token = self.__has_token()
        if has_token:
            # Mamy token - przejmujemy i informujemy
            self.__clients.token_owner = own_id
            self.__clients.locked = True
            c = self.__clients.find_self()
            c.granted = c.requested = self.__clock.increase()
            msg = PassTokenMessage(own_id, self.__clients.to_ricart())
            self.__register_token_ownership()
        else:
            # Nie mamy tokena - generujemy żądanie
            msg = RequestTableMessage(own_id, self.__clock.increase())
        self.__peer_pool.send(msg)
        return self.__clients

    def resign(self):
        """ Rezygnuje z posiadania tokena.
        Jeśli jakieś inne klienty czekają na token - przekazuje, jeśli nie - wysyła resign
        :return: aktualna tablica klientów
        """
        # Na wszelki wypadek
        if self.__has_token():
            self.__clients.locked = False
            # Jeśli jakiś inny klient chce token, to przekazujemy
            next_owner = self.__pass_token()
            if not next_owner:
                # Jeśli nikt nie chciał, to wysyłamy resign
                msg = ResignMessage(own_id)
                self.__peer_pool.send(msg)
        return self.__clients

    def process_pass_token_msg(self, msg: PassTokenMessage):
        """ Przetwarza komunikat PassToken
        :param msg: komunikat
        :return: True, jeśli token dotarł do nas, False, jeśli do innego klienta
        """
        self.__clients.token_owner = msg.dest_client_id
        self.__clients.locked = True
        self.__clients.update_with_ricart(msg.ricart_table)
        # Jeśli dostaliśmy sami robimy register
        has_token = msg.dest_client_id == own_id
        if has_token:
            self.__register_token_ownership()
        return has_token

    def register_others_resign(self):
        """ Rejestruje rezygnację innego klienta z locka
        :return: nic
        """
        self.__clients.locked = False

    def process_others_request(self, msg: RequestTableMessage):
        """ Przetwarza żądanie przejęcia tablicy od innego klienta
        :param msg: RequestTableMessage
        :return: nic
        """
        if self.__has_token():
            # Obsługujemy żądanie wg algorytmu Ricarta-Agrawala - aktualizujemy czas żądająćego
            client = self.__clients[msg.client_id]
            if client:
                client.requested = msg.logical_time
                # Jeśli nie jest zablokowany, to od razu przekazujemy
                if not self.__clients.locked:
                    self.resign()
                # else: czekamy na resign lub koniec czasu
            else:
                logger.warn('Client not found: %s' % msg.client_id)
        else:
            logger.debug('Client %s requested ownership, but I don\'t have the token.' % msg.client_id)

    def __pass_token(self):
        """ Operacja przekazania tokena innemu klientowi zgodnie z algorytmem Ricarta-Agrawala
        :return: id klienta, któremu przekazaliśmy token
        """
        # Znajdujemy klienta zgodnie z algorytmem
        client = self.__find_next_token_owner()
        if client:
            self.__clients.token_owner = client.id
            self.__clients.locked = True
            # Wpisujemy swój czas granted
            self.__clients.find_self().granted = self.__clock.get()
            # Generujemy komunikat przekazania
            msg = PassTokenMessage(client.id, self.__clients.to_ricart())
            self.__peer_pool.send(msg)
            return client.id
        else:
            return None

    def __has_token(self):
        """ Sprawdza, czy obecny klient ma token
        :return: wartość logiczna
        """
        return self.__clients.token_owner == own_id

    def __find_next_token_owner(self):
        """ Znajduje klienta, któremu zostanie przekazany token
        :return: obiekt klienta
        """
        # Iterujemy w prawo od siebie
        own_idx = next((i for i, c in enumerate(self.__clients.clients) if c.id == own_id), None)
        size = len(self.__clients.clients)
        iterator = map(lambda i: self.__clients.clients[(i + own_idx) % size], range(1, size))
        # Znajdujemy pierwszego klienta na prawo, dla którego R > G
        return next(filter(lambda c: c.requested > c.granted, iterator), None)

    def __register_token_ownership(self):
        # Odpalamy timer, który po określonym czasie zrezygnuje z tokena
        Timer(config.token_ownership_max_time, self.__token_time_elapsed).start()

    def __token_time_elapsed(self):
        logger.debug('Token ownership time elapsed!')
        self.resign()
