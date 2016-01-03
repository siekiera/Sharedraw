""" Plik zawierający stałe konfiguracyjne
"""

from getopt import getopt
import sys


class Config:
    port = 12345
    keep_alive_interval = 3
    keep_alive_timeout = 10

    def load(self):
        opts, args = getopt(sys.argv[1:], "p:")
        for opt, arg in opts:
            if opt == "-p":
                self.port = int(arg)

config = Config()
