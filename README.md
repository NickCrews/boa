# Boa

Python GUI (plus some arduino code) to control a homemade force sensor. (Python + forces = Boa, as in Boa Constrictor)

For my undergrad senior project for the physics department, I designed and made from scratch a force sensor that can measure the forces generated from typical rock climbing falls. An applied force causes a _strain gauge_ to stretch, which changes its electrical resistance. A _Wheatstone Bridge_ transforms this resistance change into a change in voltage, which is amplified and converted to a digital signal using the HX711 chip on the Sparkfun Load Cell Breakout Board. An Arduino microcontroller reads from the HX711 chip, and then streams the readings via bluetooth (the sensor needs to be mounted at the top of a climbing gym) to a computer for recording and analyisis.

For more background info, you can find:

- [A poster](https://drive.google.com/file/d/1qqtx6bhoNgbEWu2q_2E9M_DIvXQDxh1o/view?usp=sharing) that gives a good overview of the project.
- [The powerpoint](https://goo.gl/1Zyqgk) that I presented to the physics department for my senior seminar. A bit more in depth than the poster.
- [Videos](https://goo.gl/XtKXJ1) of testing the sensor with climbing falls.

This repository includes the code to run the Arduino, as well as a python program to view, analyze, save, and load data from the sensor, as well as calibrate the sensor.

![screenshot](https://github.com/NickCrews/boa/blob/master/results/Screenshot%20from%202018-01-21%2006-59-46.png)

# Requirements

- python3
- MacOS (extensively tested), Linux (At least it worked 2 years ago), or Windows (Theoretically should work, never tested though)

# Use

First, clone this code. Then, start and enter a virtual environment
(here we call it `.venv3`) so
that the dependencies we install don't mess up any of your globally
installed libraries. Finally, install the requirements into our venv.

```sh
$ git clone https://github.com/NickCrews/boa.git
$ cd boa
$ python3 -m venv .venv3
$ source .venv3/bin/activate
(.venv3)$ pip install -U pip
(.venv3)$ pip install -r requirements.txt
```

Now your environment is set up. You can launch the Python GUI with

```sh
(.venv3)$ python3 boa/boa.py
```

Try loading up finalCalibration.csv from the Calibrations menu and then one of the recordings from the Recordings menu. Use the AutoRange button to zoom the plot to fit the data.

# File Structure

- [/arduino/](/arduino/) contains the simple arduino code to stream readings from the HX711
- [/calibrations/](/calibrations/) contains `.csv` files of saved calibrations. Entries are pairs of the form (measured value from scale, real weight in newtons)
- [/recordings/](/recordings/) contains `.csv` files of saved recordings. Entries are in pairs of the form (timestamp in seconds since the epoch (output of `time.time()`), measured value from scale)
- [/results/](/results/) contains some screenshots of good calibrations and a good drop-test
- [/wheatstoneBridgeCircuit.txt](/wheatstoneBridgeCircuit.txt) can be used at http://www.falstad.com/circuit/ to view a simulation of the Wheatstone Bridge
- [/boa/](/boa/) contains Python source code for the controller GUI.
  - LoadCellControl.ui is a file created by QT Creator that describes the visual/spatial structure of the GUI. I used QT Creator to make this.
  - basicgui.py is compiled automatically from LoadCellControl.ui and is the basic gui code that can be run from pyqt. Don't modify it, it is automatically overwritten.
  - gui.py builds upon basicgui.py to flesh out the functionality of the GUI
  - scale.py contains the code to actually connect to the arduino via bluetooth or usb cable and read from it.
  - loadcellcontrol.py is the main module. It ties all the components together.
