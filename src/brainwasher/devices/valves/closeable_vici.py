"""Multiposition Valves"""
from vicivalve import VICI
from serial import Serial
from typing import Union

from dataclasses import dataclass
from math import ceil

@dataclass
class Port:
    index: int = None
    open: bool = False


class CloseableVICI(VICI):
    """a rotary shear valve that can be closed by moving to an interstitial
    position *between* two positions, effectively acting like a normal
    `RotaryShearValve` but with twice as many positions."""

    def __init__(self, serial: Serial,
                 port_count: int, port_map: dict = None):
        """
        :param port_count: Number of physical selectable ports (not including
            the outlet) that the valve can select between). This is distinct
            from positions where the valve may have twice as many positions as
            ports.
        :param port_map: dict, keyed by chemical name, of selector ports
        corresponding to each position.
        """
        # VICI range is 1-indexed.
        # double every current position value.
        # map every other port to a "closed" position.
        self.port_count = port_count
        port_map = {} if port_map is None else port_map
        position_map = {c:i*2 for c,i in port_map.items()}
        super().__init__(serial, positions=port_count * 2, position_map=position_map)
        self.current_port = self._get_current_port()

    def _get_current_port(self):
        curr_hw_position = int(self.current_position())
        return Port(index=ceil(float(curr_hw_position)/2),
                    open=(curr_hw_position % 2 != 0))  # open if odd

    def _to_nearest_hw_position(self, port: int, open: bool = True):
        if open:
            return (port * 2 - 1) % (self.port_count * 2)
        return port * 2

    def _check_port_range(self, port):
        if 1 <= port <= self.port_count:
            return
        raise ValueError(f"Requested port {port} is out of range.")

    def move_to_port(self, port: int):
        """Move to the specified position."""
        # Convert position to open position in hardware.
        self._check_port_range(port)
        open_hw_position = self._to_nearest_hw_position(port, open=True)
        super().move_to_position(open_hw_position)
        self.current_port.index = port
        self.current_port.open = True

    def is_open(self):
        return self.current_port.open

    def open(self):
        self.move_to_port(self.current_port.index)

    def close(self):
        closed_hw_position = self._to_nearest_hw_position(self.current_port.index,
                                                       open=False)
        super().move_to_position(closed_hw_position)
        self.current_port.open = False

    def move_clockwise_to_port(self, port: Union[int, str]):
        self._check_port_range(port)
        open_hw_position = self._to_nearest_hw_position(port, open=True)
        super().move_clockwise_to_position(open_hw_position)
        self.current_port.index = port
        self.current_port.open = True

    def move_counterclockwise_to_port(self, port: Union[int, str]):
        self._check_port_range(port)
        open_hw_position = self._to_nearest_hw_position(port, open=True)
        super().move_counterclockwise_to_position(open_hw_position)
        self.current_port.index = port
        self.current_port.open = True



if __name__ == "__main__":

    from serial import Serial
    from time import sleep

    ser = Serial("/dev/ttyUSB0", baudrate=9600)
    vici = LockingVICI(ser, port_count=10)

    print(f"Current port is {vici.current_port}")
    print()
    print("Moving to port 1")
    vici.move_to_port(1)
    print(f"Current port is {vici.current_port}")
    print()
    print("Closing port.")
    vici.close()
    print(f"Current port is {vici.current_port}")

    #vici.move_to_port(10)
    #sleep(1)
    #vici.move_to_port(1)
    #sleep(1)
    #vici.open()
    #vici.close()

    #vici.move_counterclockwise_to_port(1)
    #sleep(1)
    #vici.move_counterclockwise_to_port(10)
    #sleep(1)
