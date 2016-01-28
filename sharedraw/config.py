""" Plik zawierający stałe konfiguracyjne
"""
from datetime import datetime

from getopt import getopt
import random
import string
import sys


class Config:
    port = 5555
    keep_alive_interval = 5
    token_ownership_max_time = 10
    line_max_length = 30

    def load(self):
        opts, args = getopt(sys.argv[1:], "p:")
        for opt, arg in opts:
            if opt == "-p":
                self.port = int(arg)


config = Config()


def get_own_id():
    datepart = datetime.now().strftime("%H%M%S%f")
    randompart = ''.join(
        random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for _ in range(6))
    return 'Mich_' + datepart + randompart


own_id = get_own_id()
