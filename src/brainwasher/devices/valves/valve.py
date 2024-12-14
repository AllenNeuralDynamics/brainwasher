"""Generic Valve Base Class"""
import logging

from typing import Union


class Valve:

    def __init__(self, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)

class SolenoidValve(Valve):
    """Valve base class."""

    def energize(self):
        self.log.debug("Energizing.")

    def deenergize(self):
        self.log.debug("De-energizing.")


class IsolationValve(Valve):
    """isolation valve base class."""

    def open(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class NCValve(IsolationValve):
    pass


class NOValve(IsolationValve):
    pass


class ThreeTwoValve:
    """3/2 valve base class."""

    def select_way(self, way: Union[int, str]):
        """Select way 'A' (0) or 'B' (1)."""
        raise NotImplementedError
