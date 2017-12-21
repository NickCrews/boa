# ForceSensorController

For my senior project for the physics department, I designed and made from scratch a force sensor that can measure the forces generated from typical rock climbing falls. An applied force causes a *strain gauge* to stretch, which changes its electrical resistance. A *Wheatstone Bridge* transforms this resistance change into a change in voltage, which is amplified and converted to a digital signal using the HX711 chip on the Sparkfun Load Cell Breakout Board. An Arduino microcontroller reads from the HX711 chip, and then streams the readings via bluetooth (the sensor needs to be mounted at the top of a climbing gym) to a computer for recording and analyisis.

This repository includes the code to run the Arduino, as well as a python program to view, analyze, save, and load data from the sensor, as well as calibrate the sensor.
