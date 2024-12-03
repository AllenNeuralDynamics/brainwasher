"""Generic Valve Base Class"""

from typing import Union


class SolenoidValve:
    """Valve base class."""

    def energize(self):
        raise NotImplementedError

    def deenergize(self):
        raise NotImplementedError


class IsolationValve:
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
