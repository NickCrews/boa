# ForceSensorController

For my senior project for the physics department, I designed and made from scratch a force sensor that can measure the forces generated from typical rock climbing falls. An applied force causes a *strain gauge* to stretch, which changes its electrical resistance. A *Wheatstone Bridge* transforms this resistance change into a change in voltage, which is amplified and converted to a digital signal using the HX711 chip on the Sparkfun Load Cell Breakout Board. An Arduino microcontroller reads from the HX711 chip, and then streams the readings via bluetooth (the sensor needs to be mounted at the top of a climbing gym) to a computer for recording and analyisis.

A poster on the project can be found at [goo.gl/9RLajr](goo.gl/9RLajr), videos of testing the sensor with climbing falls can be found at [goo.gl/XtKXJ1](goo.gl/XtKXJ1), and my powerpoint that I presented to the physics department for my senior seminar can be found at [goo.gl/1Zyqgk](goo.gl/1Zyqgk).

This repository includes the code to run the Arduino, as well as a python program to view, analyze, save, and load data from the sensor, as well as calibrate the sensor.

![screenshot](https://github.com/NickCrews/ForceSensorController/blob/master/results/Screenshot%20from%202018-01-21%2006-59-46.png)

# Requirements
- python 2 or 3 (use 2 if you want to use bluetooth)
- numpy
- pyQT
- pyqtgraph (extension of pyqt used for the plots)\
- bluetooth (if you want it, otherwise can do USB)


# Use
`python loadcellcontrol.py`
OR
`python3 loadcellcontrol.py`

Note that python 2 is required to use the python bluetooth library, and thus be able to connect to the arduino wirelessly.
Try loading up finalCalibration.csv from the Calibrations menu and then one of the recordings from the REcordings menu. Use the AutoRange button to zoom the plot to fit the data.

# File Structure
- arduino/ contains the simple arduino code to stream readings from the HX711
- calibrations/ contains .csv files of saved calibrations. Entries are pairs of the form (measured value from scale, real weight in newtons)
- recordings/ contains .csv files of saved recordings. Entries are in pairs of the form (timestamp in seconds since the epoch (output of time.time()), measured value from scale)
- results/ contains some screenshots of good calibrations and a good drop-test
- wheatstoneBridgeCircuit.txt can be used at http://www.falstad.com/circuit/ to view a simulation of the Wheatstone Bridge
- LoadCellControl.ui is a file created by QT Creator that describes the visual/spatial structure of the GUI. I used QT Creator to make this.
- basicgui.py is compiled automatically from LoadCellControl.ui and is the basic gui code that can be run from pyqt. Don't modify it, it is automatically overwritten.
- gui.py builds upon basicgui.py to flesh out the functionality of the GUI
- scale.py contains the code to actually connect to the arduino via bluetooth or usb cable and read from it.
- loadcellcontrol.py is the main module. It ties all the components together.
