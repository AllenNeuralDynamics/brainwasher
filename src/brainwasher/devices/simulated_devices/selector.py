"""Simulated Selector"""
import logging
from vicivalve import VICI

from typing import Union


class SimSelector:

    def __init__(self, positions: int, position_map: dict = None, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)


    def move_to_position(self, position: Union[int, str]):
        # FIXME: we should figure out how to use _lookup_position
        #   Possibly inherit from VICIValve Selector and stub out certain features.
        self.log.debug(f"Moving to position: {position}")
