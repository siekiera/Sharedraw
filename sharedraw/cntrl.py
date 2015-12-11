from queue import Queue
from threading import Thread, Event
from sharedraw.ui.networking import PeerPool
from sharedraw.ui.ui import SharedrawUI


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

    def run(self):
        while not self.stop_event.is_set():
            message = self.queue_to_ui.get()
            self.sd_ui.update(message)


