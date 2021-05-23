import logging

from boa.app import App

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    boa = App()
    boa.openCalibration("calibrations/finalCalibration.csv")
    boa.start()
