"""Generic Base Class Mixer"""
import logging


class Mixer:

    def __init__(self, max_rpm: float, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.max_rpm = max_rpm

    def set_mixing_speed(self, rpm: float):
        self.log.debug("Setting mixing speed to {rpm}[rpm]")

    def set_mixing_speed_percent(self, percent: float):
        self.log.debug(f"Setting mixing speed to {percent:.3f}%")

    def start_mixing(self):
        self.log.debug("Starting mixer.")

    def stop_mixing(self):
        self.log.debug("Stopping mixer.")
