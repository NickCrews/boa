from pathlib import Path
import time
import warnings

import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui, uic

from .calibration import Calibration

# dynamically generate the gui skeleton file from the ui file
this_directory = Path(__file__).parent
with open(this_directory / "basicgui.py", "w") as pyfile:
    uic.compileUi(this_directory / "LoadCellControl.ui", pyfile)
from . import basicgui


class GUI(basicgui.Ui_GUI, QtCore.QObject):
    """Interface for displaying data and calibrations,
    and for performing actions such as changing scale settings,
    loading/saving calibrations, and logging data"""

    sigScaleChanged = QtCore.pyqtSignal(str)
    sigBaudrateChanged = QtCore.pyqtSignal(int)
    sigSampleRateChanged = QtCore.pyqtSignal(float)
    sigSaveCal = QtCore.pyqtSignal(str)
    sigOpenCal = QtCore.pyqtSignal(str)
    sigSaveRec = QtCore.pyqtSignal(str, float, float)
    sigOpenRec = QtCore.pyqtSignal(str)
    sigSampleAdded = QtCore.pyqtSignal(float, float, str)
    sigSamplesRemoved = QtCore.pyqtSignal(list)
    sigExportRange = QtCore.pyqtSignal(float, float)
    sigClear = QtCore.pyqtSignal()

    def __init__(self, app):
        QtCore.QObject.__init__(self)
        self.app = app
        self.mainwindow = QtGui.QMainWindow()
        self.setupUi(self.mainwindow)
        self._setupMenubar()

        # instance variables
        self.calibration = None
        self.units = "N"
        # used for displaying the average readings for the last
        # historyTime in seconds
        self.historyTime = 1
        self.lastFewReadings = []
        self.avgVal = None

        # set up parts of display
        # The scrolling plot, the calibrationtab consisting of both the table and graph of
        # calibration points, and the spin box for selecting sample rate,
        # which has to be weird since it goes 1-80 but then also .5,.2, and .1 Hz as well
        self.plot = Plot(self.plotWidget, self.autoscrollCheckBox.isChecked())
        self.ct = CalibrationTab(self.sampleTable, self.calibrationPlot, self.units)
        self.srsb = CustomSampleRateSpinBox(self.sampleRateSpinBox)

        # slots and signals
        self.plot.sigLineChanged.connect(self.measuredValueSpinBox.setValue)
        self.autoscrollCheckBox.stateChanged.connect(self.plot.setAutoscroll)
        self.measuredValueSpinBox.valueChanged.connect(self.plot.line.setValue)
        self.autoRangeButton.clicked.connect(self.plot.autoRange)
        self.clearPlotsButton.clicked.connect(self.clear)
        self.removeSampleButton.clicked.connect(self._removeSamples)

        def f():
            self.sigScaleChanged.emit(self.scalesComboBox.currentText())

        self.scalesComboBox.currentIndexChanged.connect(f)

        def f(x):
            self.sigSampleRateChanged.emit(x)

        self.srsb.sigValueChanged.connect(f)

        def f():
            self.sigBaudrateChanged.emit(int(self.baudrateComboBox.currentText()))

        self.baudrateComboBox.currentIndexChanged.connect(f)

        def f():
            self.sigSampleAdded.emit(
                self.measuredValueSpinBox.value(),
                self.realValueSpinBox.value(),
                self.units,
            )

        self.addSampleButton.clicked.connect(f)

        self.mainwindow.show()

    def addReading(self, reading):
        # The plot itself is where the array of data is stored
        self.plot.add(*reading)

        # Make the LCD 7-segment display show the current weight (using a running average)
        # clear out any old readings and add this new one
        timestamp, val = reading
        cutoffTime = timestamp - self.historyTime
        self.lastFewReadings = [
            (t, v) for t, v in self.lastFewReadings if t > cutoffTime
        ]
        self.lastFewReadings.append(reading)
        # show the average reading
        vals = [v for t, v in self.lastFewReadings]
        avgVal = sum(vals) / len(vals)
        if self.calibration and self.calibration.hasFit():
            inNewtons = self.calibration.fit.measured2real(avgVal)
            avgVal = Calibration.convertBetween(inNewtons, "N", self.units)
        self.setAvgVal(avgVal)

    def setAvgVal(self, avgVal):
        self.avgVal = avgVal
        self.currentReadingLCD.display(self.avgVal)

    def setScaleList(self, scales):
        """Update the list of available scales

        scales:list of str-The name of each scale
        This is a little tricky because we can't clear and then repopulate the combobox,
        or the current selection would be lost"""
        scb = self.scalesComboBox
        # remove any scales from combobox that aren't in scale list
        # The first two items in combobox are "Select and scale..." and "Random Generator." Ignore them.
        for i in range(2, len(scb)):
            if scb.itemText(i) not in scales:
                # if current scale is removed then default back to selecting index 0
                if i == scb.currentIndex():
                    scb.setCurrentIndex(0)
                scb.removeItem(i)

        # append any NEW scales
        alreadyThere = [scb.itemText(i) for i in range(len(scb))]
        for s in scales:
            if s not in alreadyThere:
                scb.addItem(s)

    def getSampleRate(self):
        return self.srsb.value()

    def getBaudrate(self):
        return int(self.baudrateComboBox.currentText())

    def setTitle(self, title):
        self.mainwindow.setWindowTitle(title)

    def setCalibration(self, cal):
        self.calibration = cal
        self.plot.setFit(cal.fit)
        self.ct.setCalibration(cal)
        if self.calibration:
            if self.calibration.hasFit():
                self.currentReadingLabel.setText(
                    "Current reading ({})".format(self.units)
                )
            else:
                self.currentReadingLabel.setText("Current reading (raw)")

    @QtCore.pyqtSlot()
    def clear(self):
        """Clear all the recorded data from the plots"""
        self.plot.clear()
        self.sigClear.emit()

    def _setupMenubar(self):
        """Make it so when we select units or click to open or save
        a recording or calibration, the right thing happens."""
        self.menuBar.setNativeMenuBar(False)
        ag = QtGui.QActionGroup(self.mainwindow)
        ag.addAction(self.actionN)
        ag.addAction(self.actionKg)
        ag.addAction(self.actionLbs)
        ag.triggered.connect(self._unitsChanged)

        self.actionOpenCal.triggered.connect(self._openCalibration)
        self.actionSaveCalAs.triggered.connect(self._saveCalibration)
        self.actionOpenRec.triggered.connect(self._openRecording)
        self.actionSaveRecAs.triggered.connect(self._saveRecording)

    @QtCore.pyqtSlot(QtGui.QAction)
    def _unitsChanged(self, act):
        """Called when one of the buttons in the menu (a QAction) is triggered"""
        self.units = act.text()
        self.plot.setUnits(self.units)
        self.ct.setUnits(self.units)
        txt = "Real Weight ({})".format(self.units)
        self.realValueLabel.setText(txt)
        if self.calibration:
            if self.calibration.hasFit():
                self.currentReadingLabel.setText(
                    "Current reading ({})".format(self.units)
                )
            else:
                self.currentReadingLabel.setText("Current reading (raw)")

    @QtCore.pyqtSlot()
    def _addSample(self):
        measured = float(self.measuredValueSpinBox.value())
        real = float(self.realValueSpinBox.value())
        self.sigSampleAdded.emit(measured, real, self.units)

    @QtCore.pyqtSlot()
    def _removeSamples(self):
        pts = self.ct.selectedPoints
        self.sigSamplesRemoved.emit(pts)

    @QtCore.pyqtSlot()
    def _openCalibration(self):
        filename = self._getOpenFile("Open Calibration...", "calibrations")
        if not filename:
            return
        if self._areYouSure():
            self.sigOpenCal.emit(filename)

    @QtCore.pyqtSlot()
    def _saveCalibration(self):
        filename = self._getSaveFile("Save Calibration As...", "calibrations")
        if not filename:
            return
        if self._areYouSure():
            self.sigSaveCal.emit(filename)

    @QtCore.pyqtSlot()
    def _openRecording(self):
        filename = self._getOpenFile("Open Recording...", "recordings")
        if not filename:
            # user cancelled
            return
        if self._areYouSure():
            self.sigOpenRec.emit(filename)

    @QtCore.pyqtSlot()
    def _saveRecording(self):
        filename = self._getSaveFile("Save Recording As...", "recordings")
        if not filename:
            # user cancelled
            return
        if self._areYouSure():
            lo, hi = self.plot.getRange()
            self.sigSaveRec.emit(filename, lo, hi)

    def _areYouSure(self):
        dlg = QtGui.QMessageBox(self.mainwindow)
        dlg.setText("There is no undo button.")
        dlg.setInformativeText("Are you sure that you want to continue?")
        dlg.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        dlg.setDefaultButton(QtGui.QMessageBox.No)
        dlg.setModal(False)
        return dlg.exec_() == QtGui.QMessageBox.Yes

    def _getSaveFile(self, title, directory):
        """Return the filename that the user selects to save to, or '' if cancelled"""
        # we CANT do this nice static method since it's blocking
        # filename = QtGui.QFileDialog.getSaveFileName(
        #            self.mainwindow, 'Save File', '', 'CSV files (*.csv)')
        dlg = QtGui.QFileDialog(self.mainwindow)
        dlg.setWindowTitle(title)
        dlg.setDirectory(directory)
        dlg.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        dlg.setFileMode(QtGui.QFileDialog.AnyFile)
        dlg.setNameFilter("CSV files (*.csv)")
        dlg.setModal(True)
        if dlg.exec_():
            filename = dlg.selectedFiles()[0]
            if filename[-4:] != ".csv":
                filename += ".csv"
            return filename
        # user cancelled
        return ""

    def _getOpenFile(self, title, directory):
        """Open a file dialog for choosing either
        calibration or recording data
        we CANT do this nice static method since it's blocking
        filename = QtGui.QFileDialog.getOpemFileName(
                   self.mainwindow, 'Open File', '', 'CSV files (*.csv)')"""
        dlg = QtGui.QFileDialog(self.mainwindow)
        dlg.setWindowTitle(title)
        dlg.setDirectory(directory)
        dlg.setFileMode(QtGui.QFileDialog.ExistingFile)
        dlg.setNameFilter("CSV Files (*.csv)")
        dlg.setModal(False)
        if dlg.exec_():
            filename = dlg.selectedFiles()[0]
            return filename
        # user cancelled
        return ""


class Wrapper:
    """A class for objects that will wrap around already
    instantiated objects of another class. We are wrapping
    and not subclassing them since they are handed to us
    already instantiated. Some whacky monkeypatching metaprogramming grossness."""

    def __init__(self, wrapped):
        self._wrapped = wrapped

    def __getattr__(self, attr):
        return getattr(self._wrapped, attr)

    def __setattr__(self, attr, val):
        if attr == "_wrapped":
            object.__setattr__(self, attr, val)
        else:
            return setattr(self._wrapped, attr, val)


class CustomSampleRateSpinBox(Wrapper, QtCore.QObject):
    """Take the normal spinbox which contains interger values 1-80,
    and throw on the values .1, .2, .5 at the beginning"""

    sigValueChanged = QtCore.pyqtSignal(float)
    vals = [0.1, 0.2, 0.5]

    def __init__(self, sb):
        Wrapper.__init__(self, sb)
        QtCore.QObject.__init__(self)
        self.setMinimum(self.vals[0])
        self.__old = self.value()
        self.__i = -1
        self.valueChanged.connect(self.adjust)

    def adjust(self):
        """Called whenever the value is adjusted either up or down"""
        new = self.value()
        old = self.__old
        v = self.vals
        self._wrapped.blockSignals(True)
        if new > v[-1] and old > v[-1]:
            # in the normal range of values [1.-80.]
            pass
        elif new < v[-1] and old > v[-1]:
            # we just transitioned from regular values into our custom values
            self.setValue(self.vals[-1])
            self.__i = len(v) - 1
        elif new < old:
            # started in custom values, tried to decrement
            self.__i = max(0, self.__i - 1)
            self.setValue(v[self.__i])
        else:
            # must have tried to increment
            self.__i += 1
            # did we just jump out of custom vals into normal vals [1-80]?
            if self.__i >= len(v):
                self.setValue(1)
                self.__i = -1
            else:
                self.setValue(v[self.__i])
        self._wrapped.blockSignals(False)
        self.__old = self.value()
        self.sigValueChanged.emit(self.value())


class Plot(Wrapper, QtCore.QObject):
    """A wrapper class for the plots in our gui"""

    # We store the data points in a series of numpy arrays.
    # How big should these arrays be and how many of them?
    chunkSize = 100
    maxChunks = 500

    # The draggable horizontal line (used for calibration and measurement) is moved
    sigLineChanged = QtCore.pyqtSignal(float)

    class TimeAxisItem(pg.AxisItem):
        """Custom little class to better label the times on the x-axis of the plot"""

        def __init__(self):
            super().__init__(orientation="bottom")
            self.setLabel(text="Time", units="")
            self.enableAutoSIPrefix(False)

        @classmethod
        def time2millis(cls, value):
            sec = time.strftime("%X", time.localtime(value))
            millis = str(value - int(value))[1:5]
            AMPM = sec[-3:]
            REST = sec[:-3]
            return REST + millis + AMPM

        def tickStrings(self, values, scale, spacing):
            """Generate the string labels given a list of time values.

            Depending on how zoomed in we are, give different resolutions."""
            DAY_LENGTH = 60 * 60 * 24
            SECOND_LENGTH = 1
            if spacing > DAY_LENGTH:
                return [time.strftime("%x", time.localtime(value)) for value in values]
            elif spacing > SECOND_LENGTH:
                return [time.strftime("%X", time.localtime(value)) for value in values]
            else:
                return [self.time2millis(value) for value in values]

    def __init__(self, plot, doAutoscroll, units="N"):
        Wrapper.__init__(self, plot)
        QtCore.QObject.__init__(self)
        self._curves = []
        self._current = np.empty((self.chunkSize + 1, 2))
        self._ptr = 0
        self.units = units
        self.fit = None
        self.doAutoscroll = doAutoscroll

        self.disableAutoRange()
        self.hideButtons()
        self.setLabel("left", "raw")

        self.setDownsampling(mode="peak")
        self.rightAxisViewBox = pg.ViewBox()
        self.plotItem.scene().addItem(self.rightAxisViewBox)
        self.getAxis("right").linkToView(self.rightAxisViewBox)
        self.sigYRangeChanged.connect(self.redraw)

        self.line = pg.InfiniteLine(angle=0, movable=True)
        self.addItem(self.line, ignoreBounds=True)
        self.line.sigPositionChanged.connect(
            lambda: self.sigLineChanged.emit(self.line.value())
        )

        self.timeAxis = Plot.TimeAxisItem()
        self.addTimeAxis(self.timeAxis)
        self.showGrid(y=True, x=True)

        self.redraw()

    def addTimeAxis(self, axis):
        pi = self.getPlotItem()
        pi.layout.removeItem(self.getAxis("bottom"))

        pos = (3, 1)
        axis.linkToView(self.getViewBox())

        pi.axes["bottom"] = {"item": axis, "pos": pos}
        pi.layout.addItem(axis, *pos)

        # make it so that we can drag around the plot
        axis.setZValue(-1000)
        axis.setFlag(axis.ItemNegativeZStacksBehindParent)

    def add(self, timestamp, val):
        """Add one data point to the plot.


        The Plot object stores data in a list of plot items
        """
        i = self._ptr % self.chunkSize
        if i == 0:
            curve = self.plot()
            self._curves.append(curve)
            last = self._current[-1]
            self._current = np.empty((self.chunkSize + 1, 2))
            if len(self._curves) > 1:
                self._current[0] = last
            else:
                self._current[0] = [timestamp, val]
            while len(self._curves) > self.maxChunks:
                c = self._curves.pop(0)
                self.removeItem(c)
        else:
            curve = self._curves[-1]
        self._current[i + 1] = [timestamp, val]
        curve.setData(x=self._current[: i + 2, 0], y=self._current[: i + 2, 1])
        self._ptr += 1

        if self.doAutoscroll:
            oldViewRange = self.getViewBox().viewRange()[0]
            span = oldViewRange[1] - oldViewRange[0]
            mostRecentTime = self._curves[-1].xData[-1]
            self.setXRange(mostRecentTime - span, mostRecentTime, padding=0)

    def clear(self):
        for c in self._curves:
            self.removeItem(c)
        self._curves = []
        self._current = np.empty((self.chunkSize + 1, 2))
        self._ptr = 0

    def setUnits(self, units):
        self.units = units
        self.redraw()

    def setFit(self, fit):
        """Set the conversion function between raw units and real units"""
        self.fit = fit
        self.redraw()

    def setAutoscroll(self, val):
        self.doAutoscroll = val

    def redraw(self):
        if self.fit is None:
            self.hideAxis("right")
            self.getAxis("left").setGrid(127)
        else:
            self.showAxis("right")
            self.setLabel("right", units=self.units)
            self.getAxis("left").setGrid(False)
            lo, hi = self.viewRange()[1]
            lo = self.fit.measured2real(lo, self.units)
            hi = self.fit.measured2real(hi, self.units)
            if self.fit.m < 0:
                self.rightAxisViewBox.invertY(True)
            else:
                self.rightAxisViewBox.invertY(False)
            self.rightAxisViewBox.setYRange(lo, hi, padding=0)

    def getRange(self):
        return self.viewRange()[0]


class CalibrationTab:
    """Includes a way of displaying a calibration
    as a table and a plot. The add/remove button
    functionality is dealt with elsewhere"""

    def __init__(self, table, plot, units):
        self.units = units
        self.calibration = None
        self.selectedPoints = []
        self.plot = CalibrationPlot(plot, units)
        self.table = CalibrationTable(table, units)
        self.plot.sigPointsSelected.connect(self._selectedPointsChanged)
        self.table.sigPointsSelected.connect(self._selectedPointsChanged)

    def setCalibration(self, cal):
        self.calibration = cal
        self.table.setPoints(cal.pts)
        self.plot.setData(cal.pts)
        self.plot.setFit(cal.fit)

    def setUnits(self, units):
        self.units = units
        self.table.setUnits(units)
        self.plot.setUnits(units)

    def _selectedPointsChanged(self, pts):
        self.selectedPoints = pts
        self.table.highlightPoints(pts)
        self.plot.highlightPoints(pts)


def rnd_pt(pt):
    x, y = pt
    return (int(round(x)), int(round(y)))


class CalibrationTable(Wrapper, QtCore.QObject):
    sigPointsSelected = QtCore.pyqtSignal(list)

    def __init__(self, table, units):
        Wrapper.__init__(self, table)
        QtCore.QObject.__init__(self)
        self.units = units
        self.pts = []
        self.itemSelectionChanged.connect(self._rowsSelected)

    def setPoints(self, pts):
        self.pts = pts
        self._update()

    def setUnits(self, units):
        self.units = units
        self._update()

    def _update(self):
        self.setRowCount(len(self.pts))
        for i, (measured, real) in enumerate(self.pts):
            converted = Calibration.convertBetween(real, "N", self.units)
            a, b = QtGui.QTableWidgetItem(str(measured)), QtGui.QTableWidgetItem(
                str(converted)
            )
            self.setItem(i, 0, a)
            self.setItem(i, 1, b)

    def _rowsSelected(self):
        ranges = self.selectedRanges()
        if len(ranges) == 0:
            return []
        rows = []
        for ran in ranges:
            for i in range(ran.bottomRow(), ran.topRow() + 1):
                rows.append(i)

        self.sigPointsSelected.emit([self.pts[r] for r in rows])

    def highlightPoints(self, pts):
        self.clearSelection()
        self.blockSignals(True)
        # Given a point (rounded), where in our list is it?
        rounded_to_index = {rnd_pt(pt): i for i, pt in enumerate(self.pts)}
        for pt in pts:
            rounded = rnd_pt(pt)
            index = rounded_to_index[rounded]
            sr = QtGui.QTableWidgetSelectionRange(index, 0, index, 1)
            self.setRangeSelected(sr, True)

        self.blockSignals(False)


class CalibrationPlot(Wrapper, QtCore.QObject):
    """A Scatter plot of all the sample data points,
    plus a line of best fit overlayed"""

    sigPointsSelected = QtCore.pyqtSignal(list)

    def __init__(self, plot, units):
        Wrapper.__init__(self, plot)
        QtCore.QObject.__init__(self)
        self.line = pg.InfiniteLine(angle=0, movable=False)
        self.scatter = pg.ScatterPlotItem()
        self.pts = []
        self.highlighted = []
        self.fit = None
        self.units = units
        self.leftAxisViewBox = pg.ViewBox()
        self.plotItem.scene().addItem(self.leftAxisViewBox)
        self.getAxis("left").linkToView(self.leftAxisViewBox)
        self.showAxis("left")
        self.sigYRangeChanged.connect(self._viewBoxChanged)
        self.leftAxisViewBox.sigYRangeChanged.connect(self._leftAxisChanged)
        self.setLabel("bottom", "Measured Value")
        self.enableAutoRange()
        self.addItem(self.scatter)
        self.addItem(self.line)
        self.setFit(self.fit)
        self.setUnits(self.units)
        self.showGrid(x=True, y=True)

        def f(rect):
            self.leftAxisViewBox.setGeometry(rect)

        self.getPlotItem().vb.scene().sceneRectChanged.connect(f)
        self.scatter.sigClicked.connect(self._clicked)
        return

    def setData(self, pts):
        self.pts = [rnd_pt(p) for p in pts]
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=Warning)
            self.scatter.setData(pos=self.pts)

    def setUnits(self, units):
        self.units = units
        self.setLabel("left", "Real Weight", units=self.units)
        self._viewBoxChanged()
        if self.fit:
            self.setTitle(self.fit.inUnits(self.units))

    def setFit(self, fit):
        self.fit = fit
        if fit is None:
            self.setTitle("No Fit")
            self.line.setVisible(False)
        else:
            self.setTitle(fit.inUnits(self.units))
            degrees = np.arctan(fit.m) * 180 / np.pi
            onepoint = (0, fit.b)
            self.line.setAngle(degrees)
            self.line.setValue(onepoint)
            self.line.setVisible(True)
        self.autoRange()
        return

    def _leftAxisChanged(self):
        lo, hi = self.leftAxisViewBox.viewRange()[1]
        lo = Calibration.convertBetween(lo, self.units, "N")
        hi = Calibration.convertBetween(hi, self.units, "N")
        self.blockSignals(True)
        self.setYRange(lo, hi, padding=0)
        self.blockSignals(False)

    def _viewBoxChanged(self):
        lo, hi = self.viewRange()[1]
        lo = Calibration.convertBetween(lo, "N", self.units)
        hi = Calibration.convertBetween(hi, "N", self.units)
        # self.leftAxisViewBox.blockSignals(True)
        self.leftAxisViewBox.setYRange(lo, hi, padding=0)
        # self.leftAxisViewBox.blockSignals(False)

    def _clicked(self, _, pointItems):
        """Callback method which is called
        whenever some points on the scatterplot are clicked"""
        coords = [(p.pos().x(), p.pos().y()) for p in pointItems]
        self.sigPointsSelected.emit(coords)

    def highlightPoints(self, coords):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=Warning)

            # Un-highlight everything
            for p in self.highlighted:
                p.resetPen()
            self.highlighted = []

            # Map from a points rounded location back to the point
            m = {}
            for p in self.scatter.points():
                xy = p.pos().x(), p.pos().y()
                rounded = rnd_pt(xy)
                m[rounded] = p

            for c in coords:
                p = m[rnd_pt(c)]
                p.setPen("b", width=2)
                self.highlighted.append(p)
