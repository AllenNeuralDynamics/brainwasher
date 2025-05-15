"""Simulated Selector"""
import logging

from brainwasher.devices.pressure_sensor import PressureSensor


class SimPressureSensor(PressureSensor):

    def __init__(self, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)

    def get_pressure_psig(self):
        return 0

    def get_pressure_psia(self):
        return 14.7
