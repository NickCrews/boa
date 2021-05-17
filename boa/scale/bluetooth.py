import atexit
import logging
import multiprocessing
import time

import scale


class BluetoothScaleSearcher(scale.ScaleSearcher):
    """Abstract class used to search for available bluetooth scales.

    The actual search is blocking, and takes a few seconds, so that is done in a different process"""

    availableScales = []
    _amSearchingFlag = multiprocessing.Event()
    Q = multiprocessing.Queue()

    SCALE_NAME = "HC-05"

    @classmethod
    def available_scales(cls):
        # prune dead scales
        cls.availableScales = [s for s in cls.availableScales if s.is_open()]
        # add new Scales
        while not cls.Q.empty():
            addr, name = cls.Q.get()
            cls.availableScales.append(BluetoothScale(addr, name))

        cls._search(cls.availableScales)

        return cls.availableScales

    @classmethod
    def _search(cls, already_opened_scales):

        if cls._amSearchingFlag.is_set():
            return
        cls._amSearchingFlag.set()

        def runner():
            openAddresses = [s.address for s in already_opened_scales]
            try:
                logging.debug("starting scan for bluetooth scales")
                nearby_devices = bt.discover_devices(
                    lookup_names=True, flush_cache=True
                )
                for addr, name in nearby_devices:
                    logging.debug("found a device %s - %s", addr, name)
                    if name == cls.SCALE_NAME and addr not in openAddresses:
                        cls.Q.put((addr, name))
            except bt.BluetoothError as e:
                logging.error(e)
            finally:
                cls._amSearchingFlag.clear()

        p = multiprocessing.Process(target=runner, daemon=True)
        p.start()


class BluetoothScale(scale.Scale):

    MAX_BUFFERED_READINGS = 10000

    def __init__(self, address, name):
        self.address = address
        self.name = name

        self.readingsQ = multiprocessing.Queue(self.MAX_BUFFERED_READINGS)
        self.quitFlag = multiprocessing.Event()
        self.reader = BluetoothReader(self.address, self.readingsQ, self.quitFlag)

    def __repr__(self):
        status = "open" if self.is_open() else "closed"
        return (
            status
            + " Bluetooth Scale at address "
            + self.address
            + " with name "
            + self.name
        )

    def __str__(self):
        return "Bluetooth Scale " + self.name

    def open(self):
        self.reader.start()

    def close(self):
        self.quitFlag.set()

    def is_open(self):
        return self.reader.is_alive()

    def read(self):
        readings = []
        while not self.readingsQ.empty():
            readings.append(self.readingsQ.get())
        return readings


class BluetoothReader(multiprocessing.Process):

    PORT = 1
    TIMEOUT = 10
    MAX_PACKET_SIZE = 10

    def __init__(self, address, readingQ, quitFlag):
        super().__init__()
        self.daemon = True

        self._address = address
        self._sock = None
        atexit.register(self._close)

        self.readingQ = readingQ
        self.quitFlag = quitFlag

    def run(self):
        self._sock = bt.BluetoothSocket(bt.RFCOMM)
        self._sock.connect((self._address, self.PORT))
        self._sock.settimeout(self.TIMEOUT)
        while not self.quitFlag.is_set():
            try:
                rawReading = self._readline()
                reading = int(rawReading)
                now = time.time()
                self.readingQ.put((now, reading))
            except IOError as e:
                logging.error(e)
                break
            except ValueError as e:
                logging.error(e)

        self._close()

    def _readline(self):
        result = ""
        for i in range(self.MAX_PACKET_SIZE):
            byte = self._sock.recv(1)
            result += byte
            if result.endswith("\r\n"):
                return result[:-2]
        raise IOError(
            "lost connection with bluetooth scale at address %s"
            % str(self._sock.getsockname())
        )

    def _close(self):
        if self._sock:
            self._sock.close()
