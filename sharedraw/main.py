from sharedraw.config import config
from sharedraw.cntrl.cntrl import *

__author__ = 'Michał Toporowski'
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)s %(levelname)s %(message)s')


def main():
    config.load()
    stop_event = Event()
    cntrl = Controller(stop_event, config.port)
    cntrl.start()
    cntrl.peer_pool.start()
    cntrl.keep_alive_sender.start()
    cntrl.sd_ui.start()
    stop_event.set()
    cntrl.peer_pool.stop()


if __name__ == '__main__':
    sys.exit(main())
