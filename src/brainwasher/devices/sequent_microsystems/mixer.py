"""PWM Mosfet based Mixer"""

from brainwasher.devices.mixer import Mixer
import lib8mosind


class OnOffMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, board_address: int, channel: int,
                 rpm: float, name: str = None):
        super().__init__(name=name)
        self.board_address = board_address
        self.channel = channel
        self.rpm = rpm

    def start_mixing(self):
        super().start_mixing()
        lib8mosind.set(self.board_address, self.channel, 1)

    def stop_mixing(self):
        super().stop_mixing()
        lib8mosind.set(self.board_address, self.channel, 0)


class PWMMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, board_address: int, channel: int, max_rpm: float,
                 name: str = None):
        super().__init__(name=name)
        self.board_address = board_address
        self.channel = channel
        self.duty_cycle = 0
        self.max_rpm = max_rpm
        self.set_mixing_speed(max_rpm)  # Default to max speed.

    def set_mixing_speed_percent(self, percent):
        percent = min(percent, 100)  # Set value in percent
        self.duty_cycle = percent

    def set_mixing_speed(self, rpm: float):
        super().set_mixing_speed(rpm)
        duty_cycle = min(rpm/self.max_rpm * 100, 100)  # Set value in percent
        self.duty_cycle = duty_cycle

    def start_mixing(self):
        super().start_mixing()
        lib8mosind.set_pwm(self.board_address, self.channel, self.duty_cycle)

    def stop_mixing(self):
        super().stop_mixing()
        lib8mosind.set_pwm(self.board_address, self.channel, 0)
