"""Valve abstraction on top of Sequent Microsystems 8-Mosfets board"""

from brainwasher.devices.valves.valve import SolenoidValve as BaseSolenoidValve
from brainwasher.devices.valves.valve import NCValve as BaseNCValve
from brainwasher.devices.valves.valve import ThreeTwoValve as BaseThreeTwoValve

from typing import Union

import lib8mosind

class NCValve(BaseNCValve, BaseSolenoidValve):

    def __init__(self, board_address: int, channel: int):
        super().__init__()
        self.board_address = board_address
        self.channel = channel

    def energize(self):
        lib8mosind.set(self.board_address, self.channel, 1)

    def deenergize(self):
        lib8mosind.set(self.board_address, self.channel, 0)

    def open(self):
        self.energize()

    def close(self):
        self.deenergize()


class ThreeTwoValve(BaseThreeTwoValve, BaseSolenoidValve):

    def __init__(self, board_address: int, channel: int):
        super().__init__()
        self.board_address = board_address
        self.channel = channel

    def energize(self):
        lib8mosind.set(self.board_address, self.channel, 1)

    def deenergize(self):
        lib8mosind.set(self.board_address, self.channel, 0)

    def select_way(self, way: Union[int, str]):
        if way in ['A', 0]:
            energize()
        elif way in ['B', 1]:
            deenergize()
        else:
            raise ValueError("Invalid argument.")
