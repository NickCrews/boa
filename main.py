import logging

from boa.app import App
from boa.scale import serial, mock

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    boa = App()
    boa.openCalibration("calibrations/finalCalibration.csv")
    boa.scaleSearchers = [serial.SerialScaleSearcher, mock.MockScaleSearcher]
    boa.start()
