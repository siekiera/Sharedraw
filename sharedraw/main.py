from getopt import getopt
import logging
from threading import Event
import sys
import threading
from sharedraw.ui.networking import PeerPool
from sharedraw.ui.ui import SharedrawUI

__author__ = 'Michał Toporowski'
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s %(message)s')


def main():
    port = 12345
    opts, args = getopt(sys.argv[1:], "p:")
    for opt, arg in opts:
        if opt == "-p":
            port = int(arg)

    stop_event = Event()
    peer_pool = PeerPool(port, stop_event)
    peer_pool.start()
    sd_ui = SharedrawUI(peer_pool)
    # sender_thread = SenderThread(sd_ui, stop_event, 12345)
    # sender_thread.start()
    # recv_thread = ReceiverThread(stop_event, 12345)
    # recv_thread.start()
    sd_ui.start()
    stop_event.set()
    peer_pool.stop()
    # print(threading.enumerate())

if __name__ == '__main__':
    sys.exit(main())