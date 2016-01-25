from queue import Queue
from threading import Thread, Event
from sharedraw.cntrl.sync import ClientsTable, OwnershipManager

from sharedraw.networking.messages import *
from sharedraw.networking.networking import PeerPool, KeepAliveSender
from sharedraw.ui.ui import SharedrawUI

logger = logging.getLogger(__name__)


class Controller(Thread):
    """ Kontroler
    """

    def __init__(self, stop_event: Event, port: int):
        super().__init__()
        self.setDaemon(True)
        self.stop_event = stop_event
        self.queue_to_ui = Queue()
        self.peer_pool = PeerPool(port, stop_event, self.queue_to_ui)
        self.keep_alive_sender = KeepAliveSender(stop_event, self.peer_pool)
        # Lista klientów
        self.clients = ClientsTable()
        self.clients.add(own_id)
        self.om = OwnershipManager(self.clients, self.peer_pool)
        self.sd_ui = SharedrawUI(self.peer_pool, self.om)
        self._update_clients_info()

    def run(self):
        while not self.stop_event.is_set():
            sm = self.queue_to_ui.get()
            action = {
                # Aktualizacja UI
                PaintMessage: self.sd_ui.paint,
                ImageMessage: self._handle_image_msg,
                # Dołączenie klienta
                JoinMessage: self._handle_join_msg,
                QuitMessage: lambda m: self._remove_client(m.client_id),
                CleanMessage: lambda m: self.sd_ui.clean(),
                PassTokenMessage: self._handle_pass_token_message,
                RequestTableMessage: self._handle_request_message,
                ResignMessage: self._handle_resign_message
            }.get(type(sm.message))

            if action:
                action(sm.message)
            # Przesłanie komunikatu do pozostałych klientów
            self.peer_pool.send(sm.message, sm.client_id)

    def _handle_image_msg(self, msg: ImageMessage):
        self.clients.update_with_id_list(msg.client_ids, msg.client_id)
        self.clients.locked = msg.locked
        self.clients.token_owner = msg.token_owner
        self._add_client(msg.client_id)
        self.sd_ui.update_image(msg)

    def _handle_join_msg(self, msg: JoinMessage):
        if msg.received_from_id:
            # Przeproxowany klient - dodajemy do listy z informacją, kto wysłał
            self._add_client(msg.client_id, msg.received_from_id)
        else:
            self._add_client(msg.client_id)
            # Odsyłamy ImageMessage, jeśli to klient, który podłączył się do nas
            img_msg = ImageMessage(own_id, self.sd_ui.get_png(), self.clients.get_client_ids(),
                                   self.clients.token_owner, self.clients.locked)
            self.peer_pool.send_to_client(img_msg, msg.client_id)

    def _add_client(self, client_id: str, received_from_id=None):
        self.clients.add(client_id, received_from_id)
        self._update_clients_info()

    def _remove_client(self, client_id: str):
        try:
            self.clients.remove(client_id)
        except ValueError:
            logger.info("Value cannot be removed! %s" % client_id)
        self._update_clients_info()

    def _handle_request_message(self, msg: RequestTableMessage):
        self.om.process_others_request(msg)
        self._update_clients_info()

    def _handle_resign_message(self, msg: ResignMessage):
        self.om.register_others_resign()
        self._update_clients_info()

    def _handle_pass_token_message(self, msg: PassTokenMessage):
        self.om.process_pass_token_msg(msg)
        self._update_clients_info()

    def _update_clients_info(self):
        self.sd_ui.update_clients_info(self.clients)
