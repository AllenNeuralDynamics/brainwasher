"""Simulated Selector"""
import logging
from typing import Union


class SimSelector:

    def __init__(self, positions: int, position_map: dict = None, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.nominal_position_count = positions
        self.position_count = positions
        self._position_dict = position_map

    def move_to_position(self, position: Union[int, str]):
        self.log.debug(f"Moving to position: {position}")


class SimCloseableSelector(SimSelector):

    def open(self):
        self.log.debug("Opening flow.")

    def close(self):
        self.log.debug("Closing flow.")

    def move_to_port(self, port: Union[int, str]):
        self.log.debug(f"Moving to port: {port}")