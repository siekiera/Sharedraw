from threading import Thread, Event

__author__ = 'michalek'


class TimerThread(Thread):
    """A thread, which runs a task (execute method) every interval seconds"""

    def __init__(self, stopped: Event, interval: float):
        Thread.__init__(self)
        self.stopped = stopped
        self.interval = interval

    def run(self):
        while not self.stopped.wait(self.interval):
            self.execute()

    def execute(self):
        pass
