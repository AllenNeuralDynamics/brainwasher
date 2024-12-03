"""Liquid Detection Sensor abstraction on top of Sequent Microsystems 16-input board"""

from brainwasher.devices.liquid_presence_detection import BubbleDetectionSensor as BaseBubbleDetectionSensor

import lib16inpind


class BubbleDetectionSensor(BaseBubbleDetectionSensor):

    def __init__(self, board_address: int, channel: int):
        self.board_address = board_address
        self.channel = channel

    def tripped(self):
        return (lib16inpind.readCh(self.board_address, self.channel) == 1)

    def untripped(self):
        return (lib16inpind.readCh(self.board_address, self.channel) == 0)

