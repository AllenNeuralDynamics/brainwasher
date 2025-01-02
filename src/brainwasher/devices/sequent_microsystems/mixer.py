"""PWM Mosfet based Mixer"""

from brainwasher.devices.mixer import Mixer
import lib8mosind


class OnOffMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, board_address: int, channel: int, rpm: float):
        super().__init__()
        self.board_address = board_address
        self.channel = channel
        self.rpm = rpm

    def start_mixing(self):
        lib8mosind.set(self.board_address, self.channel, 1)

    def stop_mixing(self):
        lib8mosind.set(self.board_address, self.channel, 0)


class PWMMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, board_address: int, channel: int, max_rpm: float):
        super().__init__()
        self.board_address = board_address
        self.channel = channel
        self.max_rpm = max_rpm
        self.set_mixing_speed(max_rpm)  # Default to max speed.

    def set_mixing_speed(self, rpm: float):
        #duty_cycle = min(rpm/self.max_rpm * 100, 100)  # Set value in percent
        #lib8mosind.set_pwm(self.board_address, self.channel, duty_cycle)
        raise NotImplementedError

    def start_mixing(self):
        raise NotImplementedError

    def stop_mixing(self):
        raise NotImplementedError
