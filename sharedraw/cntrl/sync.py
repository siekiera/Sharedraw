import logging

logger = logging.getLogger(__name__)


class ClientsTable:
    def __init__(self):
        self.clients = []

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

    def __find_client(self, client_id: str):
        return next((c for c in self.clients if c.id == client_id), None)


class Client:
    def __init__(self, client_id: str, received_from_id=None):
        self.id = client_id
        self.granted = 0
        self.requested = 0
        self.received_from_id = received_from_id