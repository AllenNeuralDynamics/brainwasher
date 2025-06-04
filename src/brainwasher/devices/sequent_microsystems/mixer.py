"""PWM Mosfet based Mixer"""

from brainwasher.devices.mixer import Mixer
import lib8mosind


class OnOffMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, board_address: int, channel: int,
                 max_rpm: float, name: str = None):
        super().__init__(max_rpm=max_rpm, name=name)
        self.board_address = board_address
        self.channel = channel

    def start_mixing(self):
        super().start_mixing()
        lib8mosind.set(self.board_address, self.channel, 1)

    def stop_mixing(self):
        super().stop_mixing()
        lib8mosind.set(self.board_address, self.channel, 0)


class PWMMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, board_address: int, channel: int, max_rpm: float,
                 invert: bool = False, name: str = None):
        super().__init__(max_rpm=max_rpm, name=name)
        self.board_address = board_address
        self.channel = channel
        self.invert = invert
        self.duty_cycle = 0
        self.set_mixing_speed(max_rpm)  # Default to max speed.
        self.stop_mixing()

    def set_mixing_speed_percent(self, percent):
        percent = min(percent, 100)  # Set value in percent
        self.duty_cycle = percent

    def set_mixing_speed(self, rpm: float):
        super().set_mixing_speed(rpm)
        duty_cycle = min(rpm/self.max_rpm * 100, 100)  # Set value in percent
        self.duty_cycle = duty_cycle

    def start_mixing(self):
        inverted = "inverted " if self.invert else ""
        self.log.debug(f"Starting {inverted}mixer at {self.duty_cycle}% duty_cycle.")
        duty_cycle = self.duty_cycle if not self.invert else 100 - self.duty_cycle
        lib8mosind.set_pwm(self.board_address, self.channel, round(duty_cycle))

    def stop_mixing(self):
        super().stop_mixing()
        duty_cycle = 0 if not self.invert else 100
        lib8mosind.set_pwm(self.board_address, self.channel, duty_cycle)
