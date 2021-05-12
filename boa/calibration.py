import contextlib
import sys
import warnings

import numpy as np


class Calibration:
    """Represents a set of (raw reading, real weight) pairs the linear relationship in between them."""

    # 1N = .1019kg = .2248lbs
    CONVERSIONS = {"N": 1.0, "kg": 0.101971621298, "lbs": 0.2248089431}

    class Fit:
        def __init__(self, m=1, b=0):
            self.m = m
            self.b = b
            # The conversion funtion with slope m and y-intercept b
            self._f = np.poly1d((m, b))

        def __str__(self):
            sign = "+" if self.b >= 0 else "-"
            return "{:.3} x {} {:.3}".format(self.m, sign, abs(self.b))

        def measured2real(self, inp, toUnits="N"):
            return Calibration.convertBetween(self._f(inp), "N", toUnits)

        def real2measured(self, inp, fromUnits="N"):
            newtons = Calibration.convertBetween(inp, fromUnits, "N")
            m2 = 1.0 / self.m
            b2 = -self.b / self.m
            f = np.poly1d((m2, b2))
            return f(newtons)

        def inUnits(self, units):
            m2 = Calibration.convertBetween(self.m, "N", units)
            b2 = Calibration.convertBetween(self.b, "N", units)
            return Calibration.Fit(m2, b2)

    def __init__(self, pts=None, units="N"):
        self.pts = []
        self.fit = None
        if pts:
            for p in pts:
                self.addPoint(p, units=units)

    def __repr__(self):
        if self.fit is None:
            return "Unfit Calibration for points " + str(self.pts)
        else:
            return str(self.fit) + " Calibration for points " + str(self.pts)

    def __len__(self):
        return len(self.pts)

    def removePoint(self, pt):
        try:
            self.pts.remove(pt)
            self.fit = self.fitLine(self.pts)
        except:
            # pt wasnt in list. whatever
            pass

    def addPoint(self, pt, units="N"):
        measured, real = pt
        # maybe the point was given in different units. Convert back to Newtons before adding it.
        newreal = self.convertBetween(real, units, "N")
        pt = measured, newreal
        if pt not in self.pts:
            self.pts.append(pt)
            self.fit = self.fitLine(self.pts)

    def convertedTo(self, units):
        return Calibration(pts=self.pts, units=units)

    def hasFit(self):
        return self.fit is not None

    @classmethod
    def convertBetween(cls, x, fromUnits, toUnits):
        a = cls.CONVERSIONS[str(toUnits)]
        b = cls.CONVERSIONS[str(fromUnits)]
        c = a / b
        return x * c

    @staticmethod
    def fitLine(pts):
        if len(pts) < 2:
            return None
        a = np.array(pts)
        x = a[:, 0]
        y = a[:, 1]
        # Calling np.polyfit with bad data (eg with infinite slope)
        # raises all sorts of alarm bells. We manage to deal with:
        # - np.RankWarning warning
        # - RuntimeWarning warning
        # - np.linalg.LinAlgError exception
        # But I can't figure out how to supress some error:
        #  ** On entry to DLASCLS parameter number  4 had an illegal value
        # It's printed to stdout, but monkeypatching sys.stdout doesn't work,
        # the library that prints it must already have a handle on sys.stdout?
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=np.RankWarning)
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            try:
                m, b = np.polyfit(x, y, 1)
            except np.linalg.LinAlgError:
                return None
        return Calibration.Fit(m, b)
