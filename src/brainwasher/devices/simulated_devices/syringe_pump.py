"""Simulated Selector"""
import logging




class SimSyringePump:

    def __init__(self, syringe_volume_ul: int, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.syringe_volume_ul = syringe_volume_ul # more of a "capacity."
        self.curr_volume_ul = 0
        self.speed_percent = 100.

    def reset_syringe_position(self):
        pass

    def get_speed_percent(self):
        return self.speed_percent

    def set_speed_percent(self, percent: float):
        self.log.debug(f"Setting plunger speed to {percent}%")
        self.speed_percent = percent

    def get_position_ul(self):
        return self.curr_volume_ul


    def move_absolute_in_percent(self, percent: float, wait: bool = True):
        self.log.debug(f"Moving plunger to {percent}% full scale range")
        self.curr_volume_ul = percent/100. * self.syringe_volume_ul

    def withdraw(self, microliters, wait: bool = True):
        if not wait:
            self.is_busy = True
        return self.aspirate(microliters)

    def aspirate(self, microliters, waite: bool = True):
        self.curr_volume_ul += microliters

    def dispense(self, microliters, wait: bool = True):
        self.curr_volume_ul -= microliters

    def is_busy(self):
        return False
