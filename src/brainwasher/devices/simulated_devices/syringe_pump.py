"""Simulated Selector"""
import logging


class SimSyringePump:

    def __init__(self, syringe_volume_ul: int, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.syringe_volume_ul = syringe_volume_ul
        self.speed_percent = 100.


    def reset_syringe_position(self):
        pass

    def get_speed_percent(self):
        return self.speed_percent

    def set_speed_percent(self, percent: float):
        self.speed_percent = percent

    def get_position_steps(self):
        return 0

    def move_absolute_in_percent(self, percent: float):
        pass
