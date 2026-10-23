"""Simulated Selector"""

import logging
from typing import Union, Dict

from mixology.devices.selector.selector import Selector
from mixology.devices.serial_device import SerialDevice


class SimSelector:
    def __init__(self, positions: int, position_map: dict = None, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.nominal_position_count = positions
        self.position_count = positions
        self._position_dict = position_map

    def move_to_position(self, position: Union[int, str]):
        self.log.debug(f"Moving to position: {position}")


class SimSerialSelector(Selector, SerialDevice):
    def __init__(self, name: str, port: str = "COM6", baudrate: int = 9600, position_map: Dict[str, int] = None):
        self.log = logging.getLogger(f"{self.__class__.__name__}.{name}")
        self.port = port
        self.baudrate = baudrate
        self.port_map = position_map or {}
        self._connected = False

    def connect(self) -> None:
        self.log.debug("Connecting to simulated serial selector.")
        self._connected = True

    def disconnect(self) -> None:
        self.log.debug("Disconnecting from simulated serial selector.")
        self._connected = False

    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        return self._connected

    def move_to_position(self, position: Union[int, str]):
        if not self.is_connected():
            raise RuntimeError("Simulated selector is not connected.")
        self.log.debug(f"Moving to position: {position}")


class SimCloseableSelector(SimSelector):
    def __init__(self, port_count: int, port_map: dict = None, name: str = None):
        self.port_count = port_count
        self.port_map = port_map
        super().__init__(positions=port_count, position_map=port_map, name=name)

    def open(self):
        self.log.debug("Opening flow.")

    def close(self):
        self.log.debug("Closing flow.")

    def move_to_port(self, port: Union[int, str]):
        self.log.debug(f"Moving to port: {port}")
