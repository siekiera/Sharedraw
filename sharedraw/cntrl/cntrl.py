from queue import Queue
from threading import Thread, Event
from sharedraw.cntrl.sync import ClientsTable, OwnershipManager

from sharedraw.networking.messages import *
from sharedraw.networking.networking import PeerPool, ClientStatusMonitor
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
        self.status_monitor = ClientStatusMonitor(stop_event, self.peer_pool)
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
                PaintMessage: self.sd_ui.paint,
                ImageMessage: self._handle_image_msg,
                JoinMessage: self._handle_join_msg,
                QuitMessage: self._remove_remote_client,
                CleanMessage: lambda m: self.sd_ui.clean(),
                PassTokenMessage: self._handle_pass_token_message,
                RequestTableMessage: self._handle_request_message,
                ResignMessage: self._handle_resign_message,
                InternalReloadMessage: lambda m: self._update_clients_info(),
                InternalQuitMessage: self._remove_neighbour_client
            }.get(type(sm.message))

            if action:
                action(sm.message)

            if not isinstance(sm.message, InternalMessage):
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

    def _remove_remote_client(self, msg: QuitMessage):
        self.clients.remove_remote(msg.client_ids, msg.detected_by)
        self._update_clients_info()

    def _remove_neighbour_client(self, msg: InternalQuitMessage):
        # Usuwamy klienta i wszystkich z jego podsieci
        removed_ids = self.clients.remove(msg.client_id)
        # Generujemy Quit i wysyłamy do pozostałych
        quit_msg = QuitMessage(removed_ids, own_id)
        self.peer_pool.send(quit_msg)
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
