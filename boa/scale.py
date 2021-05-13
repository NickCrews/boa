import atexit
import logging
import multiprocessing
import time

import bluetooth as bt
import numpy.random as rand
import serial
from serial.tools.list_ports import comports


class Scale:
    """Abstract base class for a scale."""

    def __init__(self):
        raise NotImplementedError("Cannot instantiate the abstract class Scale")

    def open(self):
        """Must be called before calls to read(). Can be called multiple times."""
        pass

    def isOpen(self):
        """Retuns whether the Scale is open or not."""
        raise NotImplementedError("isOpen() must be overriden in subclasses")

    def close(self):
        """Perform any needed cleanup. Can be called multiple times, at any time."""
        pass

    def read(self):
        """Return an iterable of (time.time(), value) tuples. Value is an int."""
        return []


class ScaleSearcher:
    """Base class for a service that provides Scales as data sources.

    Since Scales are system-wide resources, there should only be one of each
    Scale, and therefore there should only be a single ScaleSearcher to
    manage all of them. Therefore make a ScaleSearcher a global singleton by
    preventing instantiation. Use it as a class, eg ``ScaleSearcher.available_scales()``
    """

    def __new__(cls, *args, **kwargs):
        raise NotImplementedError(
            "Cannot create {} instance, just use it as a class".format(cls)
        )

    @classmethod
    def available_scales(cls):
        """Returns an iterable of `Scale` objects."""
        return []


class SerialScaleSearcher(ScaleSearcher):
    """Abstract class used to searching for scales connected via USB serial cable.

    This search is pretty fast so we don't have to do it in a different process"""

    availableScales = []


class SerialScaleSearcher(ScaleSearcher):
    """Searches for scales connected via USB or Bluetooth serial connection.

    This search is pretty fast so we don't have to do it in a different process
    """

    used_scales = []

    @classmethod
    def available_scales(cls):
        available_ports = set(port.device for port in comports())
        used_ports = set(scale.port for scale in cls.used_scales)

        to_remove = used_ports - available_ports
        to_add = available_ports - used_ports

        cls.used_scales = [
            scale for scale in cls.used_scales if scale.port not in to_remove
        ]
        cls.used_scales += [SerialScale(port) for port in to_add]

        return cls.used_scales


class BluetoothScaleSearcher(ScaleSearcher):
    """Abstract class used to search for available bluetooth scales.

    The actual search is blocking, and takes a few seconds, so that is done in a different process"""

    availableScales = []
    _amSearchingFlag = multiprocessing.Event()
    Q = multiprocessing.Queue()

    SCALE_NAME = "HC-05"

    @classmethod
    def available_scales(cls):
        # prune dead scales
        cls.availableScales = [s for s in cls.availableScales if s.isOpen()]
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


class SerialScale(Scale):
    """A scale which is connected via USB serial cable"""

    MAX_BUFFERED_READINGS = 10000

    def __init__(self, port, baudrate=9600):

        self.port = port
        self._baudrate = baudrate

        self.readingsQ = multiprocessing.Queue(self.MAX_BUFFERED_READINGS)
        self.commandQ = multiprocessing.Queue()
        self.reader = SerialReader(port, baudrate, self.readingsQ, self.commandQ)

    def __repr__(self):
        status = "open" if self.isOpen() else "closed"
        return (
            status
            + " Serial Scale at port "
            + self.port
            + " with baudrate "
            + str(self.baudrate)
        )

    def open(self):
        self.reader.start()

    def __str__(self):
        return "Serial Scale at " + self.port

    def isOpen(self):
        return self.reader.is_alive()

    def close(self):
        # poison pill
        self.commandQ.put(None)

    @property
    def baudrate(self):
        return self._baudrate

    @baudrate.setter
    def baudrate(self, newval):
        self._baudrate = newval
        self.commandQ.put({"attr": "baudrate", "val": newval})

    def read(self):
        readings = []
        while not self.readingsQ.empty():
            readings.append(self.readingsQ.get())
        return readings


class SerialReader(multiprocessing.Process):
    """Used by SerialScale to read from the scale smoothly in a different process"""

    # in seconds
    LINK_TIMEOUT = 5
    READ_TIMEOUT = 1

    MAX_PACKET_SIZE = 20

    def __init__(self, portname, baudrate, readingsQ, commandQ):
        super().__init__()
        self.daemon = True

        self.portname = portname
        self._baudrate = baudrate
        self.readingsQ = readingsQ
        self.commandQ = commandQ

        self._ser = None
        atexit.register(self.close)

    def run(self):
        self._openPort()
        self._waitForLink()
        last = time.time()
        while self._ser.is_open:
            # check for updates from outside this thread
            if not self.commandQ.empty():
                cmd = self.commandQ.get()
                if cmd is None:
                    # poison pill, exit this process
                    break
                else:
                    setattr(self, cmd["attr"], cmd["val"])
            # read a line or timeout and return empty string
            line = self._readline()
            if line:
                try:
                    reading = int(line)
                except:
                    # must have had trouble parsing. probably the baudrate is wrong, but we can ignore it
                    continue

                # Throw out the oldeast reading if the Q is full
                while self.readingsQ.full():
                    self.readingsQ.get()
                pair = (time.time(), reading)
                self.readingsQ.put(pair)
            else:
                # we didn't read anything, must have timeout out
                logging.error("didn't read anything")
                break
        self.close()

    def _readline(self):
        chars = []
        for i in range(self.MAX_PACKET_SIZE):
            try:
                c = self._ser.read(1)
            except serial.SerialException as e:
                # probably some I/O problem such as disconnected USB serial
                return None
            if not c:
                # timed out on read of individual byte
                return None
            chars.append(c)
            # check last two characters
            if chars[-2:] == [b"\r", b"\n"]:
                # looks promising...
                try:
                    strs = [c.decode() for c in chars[:-2]]
                    result = "".join(strs)
                    return result
                except:
                    # problem parsing, must be some other problem
                    return "error"
            else:
                # got end of line or there's a problem with baudrate so we never get eol
                return None

    def _openPort(self):
        # try to open the serial port
        try:
            self._ser = serial.Serial(self.portname, baudrate=self.baudrate)
        except serial.SerialException as e:
            raise e
        except ValueError as e:
            raise e
        if not self._ser.is_open:
            raise serial.SerialException(
                "couldn't open the port {port_name}".format(port_name=self._ser.name)
            )
        self._ser.timeout = self.READ_TIMEOUT
        logging.info("successfully opened serial port %s", self.portname)

    def _waitForLink(self):
        """The Arduino reboots when it initiates a USB serial connection, so wait for it to resume streaming readings"""
        start_time = time.time()
        while True:
            time.sleep(0.1)
            if self._ser.in_waiting:
                # We got a reading! Hurray!
                break
            if time.time() - start_time > self.LINK_TIMEOUT:
                # Something went wrong the arduino took too long
                self._ser.close()
                break

    def close(self):
        if self._ser:
            self._ser.close()

    @property
    def baudrate(self):
        return self._baudrate

    @baudrate.setter
    def baudrate(self, newval):
        self._baudrate = newval
        if self._ser:
            self._ser.baudrate = newval


class BluetoothScale(Scale):

    MAX_BUFFERED_READINGS = 10000

    def __init__(self, address, name):
        self.address = address
        self.name = name

        self.readingsQ = multiprocessing.Queue(self.MAX_BUFFERED_READINGS)
        self.quitFlag = multiprocessing.Event()
        self.reader = BluetoothReader(self.address, self.readingsQ, self.quitFlag)

    def __repr__(self):
        status = "open" if self.isOpen() else "closed"
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

    def isOpen(self):
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


class PhonyScale(Scale):
    """Useful for generating random noise for testing GUI if an actual scale isn't present"""

    SAMPLE_PERIOD = 1.0 / 80

    def __init__(self):
        self.baudrate = 9600

    def __str__(self):
        return "Phony Scale"

    def open(self):
        self.last = time.time()

    def isOpen():
        return True

    def read(self):
        now = time.time()
        readings = []
        for timestamp in self.frange(self.last, now, self.SAMPLE_PERIOD):
            val = int(rand.normal() * 100)
            readings.append((timestamp, val))
        self.last = now
        return readings

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

        def shouldContinue(current, cutoff):
            if inc > 0:
                return current < cutoff
            else:
                return current > cutoff

        while shouldContinue(result, stop):
            yield result
            result = start + i * inc
            i += 1


class PhonyScaleSearcher(ScaleSearcher):

    _singleton_scale = PhonyScale()

    @classmethod
    def available_scales(cls):
        return [cls._singleton_scale]
