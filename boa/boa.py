import csv
from math import fabs
from collections import deque
import signal

import numpy as np
from pyqtgraph.Qt import QtCore, QtGui
import pyqtgraph as pg

import gui
import scale
from calibration import Calibration


class Boa(QtCore.QObject):
    """The main application, consisting of model and GUI

    Reads from scale if selected, opens and saves recordings and calibrations"""

    def __init__(self):
        super().__init__()

        # init our app and gui
        self.app = QtGui.QApplication([])
        self.gui = gui.GUI(self.app)

        # set up our instance variables
        self.length = 100000
        self.data = deque([], self.length)
        self.numSamplesLastReading = 0
        self.scaleSearchers = [
            scale.SerialScaleSearcher,
            scale.PhonyScaleSearcher,
        ]
        self.scales = []
        self.scale = None
        self.calibration = Calibration()
        self.sampleRate = self.gui.getSampleRate()
        self.baudrate = self.gui.getBaudrate()

        # set up signals and slots from the GUI
        self.gui.sigScaleChanged.connect(self.useScale)
        self.gui.sigSampleRateChanged.connect(self.setSampleRate)
        self.gui.sigBaudrateChanged.connect(self.setBaudrate)

        self.gui.sigSampleAdded.connect(self.addSample)
        self.gui.sigSamplesRemoved.connect(self.removeSamples)

        self.gui.sigOpenCal.connect(self.openCalibration)
        self.gui.sigSaveCal.connect(self.saveCalibration)
        self.gui.sigOpenRec.connect(self.openRecording)
        self.gui.sigSaveRec.connect(self.saveRecording)

        # set up timers
        # Make it so we update the list of available scales every second
        self.scaleUpdateTimer = pg.QtCore.QTimer()
        self.scaleUpdateTimer.timeout.connect(self.updateAvailableScales)
        self.scaleUpdateTimer.start(1000)

        # make it so we repaint the GUI every 30th of a second
        # readFromScale() is buffered, so we will still get the full 80Hz samplerate
        self.repaintWindowTimer = pg.QtCore.QTimer()
        self.repaintWindowTimer.timeout.connect(self.readFromScale)
        self.repaintWindowTimer.start(1000 / 30.0)

        # Make it so ctrl-C signal from terminal actually quits the app
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # start up the app!
        self.app.exec_()

    def readFromScale(self):
        """Read all of the last readings from the scale, downsample them to our sampleRate, and add them"""
        if self.scale:
            self.addReadings(self.scale.read())

    def clear(self):
        self.numSamplesLastReading = 0
        self.data.clear()
        self.gui.clear()

    @staticmethod
    def _round(x, base, prec=100):
        """Round to an arbitrary base (eg multiples of 3) to a precision of a certain number of decimal places"""
        return round(base * round(float(x) / base), prec)

    @classmethod
    def _downSampleReadings(cls, readings, sampleInterval):
        """Takes a list of of form [(time, val), ...] and round all times to multiples of sampleRate,
        averaging all readings from the same time. Returns list of form [(roundedtime, val, numsamplesperroundedtimereading),...]

        ex: [(1, 4), (3, 6), (4, 8)] -> [(0, 4, 1), (5, 7, 2)] for sampleRate = 5"""
        # make a dict holding mapping from rounded times to a list of values for that roundedTime
        d = {}
        for time, val in readings:
            roundedTime = cls._round(time, sampleInterval)
            if roundedTime in d:
                d[roundedTime].append(val)
            else:
                d[roundedTime] = [val]

        def avg(vals):
            return sum(vals) / len(vals)

        result = [(rt, avg(vals), len(vals)) for rt, vals in d.items()]
        result.sort(key=lambda t: t[0])
        return result

    def addReading(self, reading):
        self.addReadings([reading])

    def addReadings(self, readings):
        """Add a list of (time, value) pairs to our saved list"""
        if len(readings) < 1:
            return
        # Say our samplerate is 10Hz. We want all our readings to be
        # at the even time interval of .1 seconds
        # Therefore we need to interpolate and downsample our data to mesh with this
        sampleInterval = 1.0 / self.sampleRate
        downsampled = self._downSampleReadings(readings, sampleInterval)
        # Now we have to merge the list of new samples with the list of old samples
        # look at time, value, and numsamples of first reading
        t, v, n = downsampled[0]
        if len(self.data) > 0:
            lastTime, lastVal = self.data[-1]
            # The first sample within our new list might overlap
            # with the last sample within the old data
            if fabs(t - lastTime) < sampleInterval:
                # we need to merge last entry of old data with first entry of new data
                nslr = self.numSamplesLastReading
                avgVal = (lastVal * nslr + v * n) / (nslr + n)
                newestTime = max(t, lastTime)
                # Modify the last entry from old data and forget the first entry from new readings
                self.data[-1] = (newestTime, avgVal)
                newPoints = downsampled[1:]
                self.numSamplesLastReading = nslr + n
            else:
                # we dont need to merge
                newPoints = downsampled
                t, v, self.numSamplesLastReading = downsampled[-1]
        else:
            # we dont need to merge
            newPoints = downsampled
            t, v, self.numSamplesLastReading = downsampled[-1]

        # cool, so now lets add these
        timesAndVals = [(t, v) for t, v, n in newPoints]
        self.data.extend(timesAndVals)
        for pt in timesAndVals:
            self.gui.addReading(pt)

    @QtCore.pyqtSlot(str, float, float)
    def saveRecording(self, filename, startTime, stopTime):
        if len(self.data) < 1:
            return
        # find all the data points between startTime and stopTime
        arr = np.array(self.data)
        times = arr[:, 0]
        ilo, ihi = np.searchsorted(times, [startTime, stopTime])
        if ilo == ihi:
            return
        inRange = arr[ilo:ihi]
        # write those data points to file
        with open(filename, "w") as out:
            csv_out = csv.writer(out)
            csv_out.writerow(["time", "raw reading"])
            for row in inRange:
                csv_out.writerow(row)

    @QtCore.pyqtSlot(str)
    def openRecording(self, filename):
        with open(filename, "r") as f:
            self.clear()
            r = csv.reader(f)
            pts = []
            for row in r:
                try:
                    time, value = row
                    pt = (float(time), float(value))
                    pts.append(pt)
                except:
                    # must not have been able to read that row. oh well!
                    pass
            self.addReadings(pts)

    @QtCore.pyqtSlot(str)
    def openCalibration(self, filename):
        with open(filename, "r") as f:
            r = csv.reader(f)
            pts = []
            for row in r:
                try:
                    measured, real = row
                    pt = (float(measured), float(real))
                    pts.append(pt)
                except:
                    # must not have been able to read that row. oh well!
                    pass
            self.calibration = Calibration(pts=pts)
            self.gui.setCalibration(self.calibration)

    @QtCore.pyqtSlot(str)
    def saveCalibration(self, filename):
        # is our calibration empty? ignore it.
        if len(self.calibration) == 0:
            return
        with open(filename, "w") as out:
            csv_out = csv.writer(out)
            csv_out.writerow(["measured", "real"])
            for row in self.calibration.pts:
                csv_out.writerow(row)

    def addScale(self, s):
        if isinstance(s, scale.SerialScale):
            s.baudrate = self.baudrate
        self.scales.append(s)
        self.gui.setScaleList([str(s) for s in self.scales])

    def removeScale(self, s):
        self.scales.remove(s)
        self.gui.setScaleList([str(s) for s in self.scales])

    @QtCore.pyqtSlot(str)
    def useScale(self, name):
        if name == "Select...":
            self.scale = None
            return

        for s in self.scales:
            if name == str(s):
                if self.scale:
                    self.scale.close()
                self.scale = s
                self.scale.open()
                # clear thold stuff
                self.scale.read()
                return

    def updateAvailableScales(self):
        available = []
        for searcher in self.scaleSearchers:
            available += searcher.available_scales()
        # print('available scales are', available)
        # clear dead ones
        for s in self.scales:
            if s not in available:
                self.removeScale(s)
        # add new ones
        for s in available:
            if s not in self.scales:
                self.addScale(s)

    @QtCore.pyqtSlot(float)
    def setSampleRate(self, sr):
        self.sampleRate = sr

    @QtCore.pyqtSlot(int)
    def setBaudrate(self, br):
        self.baudrate = br
        for s in self.scales:
            if isinstance(s, scale.SerialScale):
                s.baudrate = br

    @QtCore.pyqtSlot(float, float, str)
    def addSample(self, measured, real, units):
        self.calibration.addPoint((measured, real), units=units)
        self.gui.setCalibration(self.calibration)

    @QtCore.pyqtSlot(list)
    def removeSamples(self, pts):
        for p in pts:
            self.calibration.removePoint(p)
        self.gui.setCalibration(self.calibration)


if __name__ == "__main__":
    boa = Boa()
