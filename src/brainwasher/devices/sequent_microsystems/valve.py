"""Valve abstraction on top of Sequent Microsystems 8-Mosfets board"""

from brainwasher.devices.valves.valve import SolenoidValve as BaseSolenoidValve
from brainwasher.devices.valves.valve import NCValve as BaseNCValve
from brainwasher.devices.valves.valve import ThreeTwoValve as BaseThreeTwoValve

from time import sleep
from typing import Union

import lib8mosind

# Add a little dead time between commands because the board ignores
# commands sent faster than this interval.
DEAD_TIME_S = 0.01


class NCValve(BaseNCValve, BaseSolenoidValve):

    def __init__(self, board_address: int, channel: int, name: str = None):
        super().__init__(name=name)
        self.board_address = board_address
        self.channel = channel

    def energize(self):
        super().energize()
        # Warning: using the set command requires adding dead time, or
        # back-to-back commands are ignored
        lib8mosind.set(self.board_address, self.channel, 1)
        sleep(DEAD_TIME_S)

    def deenergize(self):
        super().deenergize()
        # Warning: using the set command requires adding dead time, or
        # back-to-back commands are ignored
        lib8mosind.set(self.board_address, self.channel, 0)
        sleep(DEAD_TIME_S)

    def open(self):
        self.energize()

    def close(self):
        self.deenergize()


class ThreeTwoValve(BaseThreeTwoValve, BaseSolenoidValve):

    def __init__(self, board_address: int, channel: int, name: str = None):
        super().__init__(name=name)
        self.board_address = board_address
        self.channel = channel

    def energize(self):
        super().energize()
        # Warning: using the set command requires adding dead time, or
        # back-to-back commands are ignored
        lib8mosind.set(self.board_address, self.channel, 1)
        sleep(DEAD_TIME_S)

    def deenergize(self):
        super().deenergize()
        lib8mosind.set_pwm(self.board_address, self.channel, 0)
        # Warning: using the set command requires adding dead time, or
        # back-to-back commands are ignored
        lib8mosind.set(self.board_address, self.channel, 0)
        sleep(DEAD_TIME_S)

    def select_way(self, way: Union[int, str]):
        if way in ['A', 0]:
            self.energize()
        elif way in ['B', 1]:
            self.deenergize()
        else:
            raise ValueError("Invalid argument.")
