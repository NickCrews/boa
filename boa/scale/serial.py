import logging
import queue
import time

import serial
import serial.threaded
from serial.tools.list_ports import comports

import scale


class SerialScale(scale.Scale):
    """A scale accessible via a serial port."""

    def __init__(self, port, baudrate=9600):
        # Create (but don't open yet) our Serial port instance
        self.serial = serial.Serial()
        self.serial.port = port
        self.serial.baudrate = baudrate

        self._open = False
        self._readingsQ = queue.Queue()

    class Reader(serial.threaded.ReaderThread):
        def __init__(self, scale):
            self.serial = scale.serial

            class Handler(serial.threaded.LineReader):
                def __init__(self, scale):
                    super().__init__()
                    self.scale = scale

                def handle_line(self, line: str):
                    try:
                        value = int(line.strip())
                    except ValueError as e:
                        logging.error(e)
                        return
                    reading = (time.time(), value)
                    self.scale._readingsQ.put(reading)

                def connection_lost(self, exc):
                    if exc:
                        logging.error(exc)

            def handler_factory():
                return Handler(scale)

            super().__init__(self.serial, handler_factory)

        def run(self):
            self.serial.open()
            super().run()

    def open(self):
        logging.debug("Opening %s", self)
        self.reader = type(self).Reader(self)
        self.reader.start()

    def __str__(self):
        return f"Serial Scale at {self.serial.port}"

    def is_open(self):
        return self.reader.is_alive()

    def close(self):
        logging.debug("Closing %s", self)
        self.reader.close()

    def read(self):
        readings = []
        while not self._readingsQ.empty():
            readings.append(self._readingsQ.get())
        return readings

    @property
    def baudrate(self):
        return self.serial.baudrate

    @baudrate.setter
    def baudrate(self, newval):
        logging.debug("%s baudrate set to %s", self, newval)
        self.serial.baudrate = newval


class SerialScaleSearcher(scale.ScaleSearcher):
    """Searches for scales connected via USB or Bluetooth serial connection.

    This search is pretty fast so we don't have to do it in a different process
    """

    used_scales = []

    @classmethod
    def available_scales(cls):
        available_ports = set(port.device for port in comports())
        used_ports = set(scale.serial.port for scale in cls.used_scales)

        to_remove = used_ports - available_ports
        to_add = available_ports - used_ports

        cls.used_scales = [
            scale for scale in cls.used_scales if scale.serial.port not in to_remove
        ]
        cls.used_scales += [SerialScale(port) for port in to_add]

        return cls.used_scales
