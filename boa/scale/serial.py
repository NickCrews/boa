import atexit
import logging
import multiprocessing
import time

import serial
from serial.tools.list_ports import comports

import scale


class SerialScale(scale.Scale):
    """A scale which is connected via USB serial cable"""

    MAX_BUFFERED_READINGS = 10000

    def __init__(self, port, baudrate=9600):

        self.port = port
        self._baudrate = baudrate

        self.readingsQ = multiprocessing.Queue(self.MAX_BUFFERED_READINGS)
        self.commandQ = multiprocessing.Queue()
        self.reader = SerialReader(port, baudrate, self.readingsQ, self.commandQ)

    def __repr__(self):
        status = "open" if self.is_open() else "closed"
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

    def is_open(self):
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
        self._open_port()
        self._wait_for_link()
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

    def _open_port(self):
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

    def _wait_for_link(self):
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


class SerialScaleSearcher(scale.ScaleSearcher):
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
