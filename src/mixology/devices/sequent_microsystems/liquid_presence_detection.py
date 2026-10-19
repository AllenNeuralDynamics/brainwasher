"""Liquid Detection Sensor abstraction on top of Sequent Microsystems 16-input board"""

import lib16inpind

from mixology.devices.liquid_presence_detection import (
    BubbleDetectionSensor as BaseBubbleDetectionSensor,
)


class BubbleDetectionSensor(BaseBubbleDetectionSensor):
    def __init__(self, board_address: int, channel: int):
        super().__init__()
        self.board_address = board_address
        self.channel = channel

    def tripped(self):
        raw_value = lib16inpind.readCh(self.board_address, self.channel)
        return raw_value == 1

    def untripped(self):
        raw_value = lib16inpind.readCh(self.board_address, self.channel)
        return raw_value == 0
