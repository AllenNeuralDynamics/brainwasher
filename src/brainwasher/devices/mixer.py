"""Generic Base Class Mixer"""
import logging


class Mixer:

    def __init__(self, max_rpm: float, min_rpm: float = 0, name: str = None):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.percent_range = (0, 100)
        self.rpm_range = (min_rpm, max_rpm)
        self.rpm = 0
        self.set_mixing_speed(max_rpm)

    def percent_to_rpm(self, percent: float):
        return ((percent - self.percent_range[0])
                / (self.percent_range[1] - self.percent_range[0])
                * (self.rpm_range[1] - self.rpm_range[0])
                + self.rpm_range[0])

    def rpm_to_percent(self, rpm: float):
        return ((rpm - self.rpm_range[0])
                / (self.rpm_range[1] - self.rpm_range[0])
                * (self.percent_range[1] - self.percent_range[0])
                + self.percent_range[0])

    def set_mixing_speed_percent(self, percent: float):
        # Clamp percent
        if percent < self.percent_range[0]:
            percent = self.percent_range[0]
            self.log.error("Clamping requested speed to {percent}%.")
        if rpm > self.rpm_range[1]:
            percent = self.percent_range[1]
            self.log.error("Clamping requested speed to {percent}%.")
        rpm = self.percent_to_rpm(percent)
        self.log.debug(f"Setting mixing speed to {percent:.3f}%")
        try:  # Suppress redundant debug message.
            old_log_level = self.log.level
            self.log.level(logging.INFO)
            self.set_mixing_speed(rpm)
        finally:
            self.log.setLevel(old_log_level)

    def set_mixing_speed(self, rpm: float):
        # Clamp rpm.
        if rpm < self.rpm_range[0]:
            self.rpm = self.rpm_range[0]
            self.log.error(f"Clamping requested speed to {self.rpm} [rpm].")
            percent = self.percent_range[0]
        if rpm > self.rpm_range[1]:
            self.rpm = self.rpm_range[1]
            self.log.error("Clamping requested speed to {self.rpm} [rpm].")
            percent = self.percent_range[1]
        self.log.debug(f"Setting mixing speed to {rpm:.3f}[rpm]")
        self._set_mixing_speed(rpm)

    def _set_mixing_speed(rpm: float):
        raise NotImplementedError

    def start_mixing(self):
        self.log.debug("Starting mixer.")
        self._start_mixing()

    def _start_mixing(self):
        raise NotImplementedError

    def stop_mixing(self):
        self.log.debug("Stopping mixer.")
        self._stop_mixing()

    def _stop_mixing(self):
        raise NotImplementedError


class PWMMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, max_rpm: float,
                 min_rpm: float = 0,
                 frequency_hz: float = 20000,
                 min_duty_cycle_percent: float = 0,
                 max_duty_cycle_percent: float = 100,
                 name: str = None):
        """Init. Note that some configurations have a minimum (nonzero) signal
        value that corresponds to a minimum rpm and a maximum signal value
        different from 100% that corresponds to the maximum rpm.
        """
        super().__init__(min_rpm=min_rpm, max_rpm=max_rpm, name=name)
        self.percent_range = (min_duty_cycle_percent, max_duty_cycle_percent)
