from getopt import getopt
import logging
import sys

from sharedraw.cntrl import *


__author__ = 'Michał Toporowski'
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s %(message)s')


def main():
    port = 12345
    opts, args = getopt(sys.argv[1:], "p:")
    for opt, arg in opts:
        if opt == "-p":
            port = int(arg)

    stop_event = Event()
    cntrl = Controller(stop_event, port)
    # peer_pool = PeerPool(port, stop_event)
    cntrl.start()
    cntrl.peer_pool.start()
    # sd_ui = SharedrawUI(peer_pool)
    cntrl.sd_ui.start()
    stop_event.set()
    cntrl.peer_pool.stop()


if __name__ == '__main__':
    sys.exit(main())