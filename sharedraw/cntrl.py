from queue import Queue
from threading import Thread, Event

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
        self.sd_ui = SharedrawUI(self.peer_pool)
        self.keep_alive_sender = KeepAliveSender(stop_event, self.peer_pool)
        # Lista klientów
        self.clients = []

    def run(self):
        while not self.stop_event.is_set():
            sm = self.queue_to_ui.get()
            action = {
                # Aktualizacja UI
                PaintMessage: self.sd_ui.paint,
                ImageMessage: self._handle_image_msg,
                # Dołączenie klienta
                JoinMessage: lambda m: self._add_client(m.client_id),
                QuitMessage: lambda m: self._remove_client(m.client_id),
                CleanMessage: lambda m: self.sd_ui.clean()
            }.get(type(sm.message))

            if action:
                action(sm.message)
            # Przesłanie komunikatu do pozostałych klientów
            self.peer_pool.send(sm.message, sm.client_id)

    def _handle_image_msg(self, msg: ImageMessage):
        self._add_client(msg.client_id)
        self.sd_ui.update_image(msg)

    def _add_client(self, client_id: str):
        if client_id not in self.clients:
            self.clients.append(client_id)
        self.sd_ui.update_clients_info(self.clients)

    def _remove_client(self, client_id: str):
        try:
            self.clients.remove(client_id)
        except ValueError:
            logger.info("Value cannot be removed! %s" % client_id)
        self.sd_ui.update_clients_info(self.clients)

