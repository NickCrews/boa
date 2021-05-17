import time

import numpy.random

import scale


class MockScale(scale.Scale):
    """Useful for generating random noise for testing GUI if an actual scale isn't present"""

    SAMPLE_PERIOD = 1.0 / 80

    def __init__(self):
        self.baudrate = 9600
        self._is_open = False

    def __str__(self):
        return "Mock Scale"

    def open(self):
        self._is_open = True
        self.last = time.time()

    def is_open(self):
        return self._is_open

    def read(self):
        now = time.time()
        readings = []
        for timestamp in self.frange(self.last, now, self.SAMPLE_PERIOD):
            val = int(numpy.random.normal() * 100)
            readings.append((timestamp, val))
        self.last = now
        return readings

    def close(self):
        self._is_open = False

    @staticmethod
    def frange(start, stop=None, inc=None):
        """A range() method for floats"""
        if stop is None:
            stop = start
            start = 0.0
        if inc is None:
            inc = 1.0
        i = 1
        result = start

        def should_continue(current, cutoff):
            if inc > 0:
                return current < cutoff
            else:
                return current > cutoff

        while should_continue(result, stop):
            yield result
            result = start + i * inc
            i += 1


class MockScaleSearcher(scale.ScaleSearcher):

    _singleton_scale = MockScale()

    @classmethod
    def available_scales(cls):
        return [cls._singleton_scale]
