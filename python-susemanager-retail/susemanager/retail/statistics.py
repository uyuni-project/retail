import logging
log = logging.getLogger(__name__)

class Statistics:
    def __init__(self):
        self.counter = {}

    def add_counters(self, names):
        for name in names:
            if name not in self.counter:
                self.counter[name] = 0

    def inc(self, name):
        if name not in self.counter:
            self.counter[name] = 0
        self.counter[name] += 1

    def print_stats(self):
        log.info("Statistics:")
        for name in sorted(self.counter):
            log.info("{:>30}: {}".format(name, self.counter[name]))


statistics = Statistics()

