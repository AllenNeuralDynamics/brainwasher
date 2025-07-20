"""Multiposition Valves"""
import logging
from vicivalve import VICI
from serial import Serial
from typing import Union

from dataclasses import dataclass
from math import ceil

@dataclass
class Port:
    port: Union[int, str] = None
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
        # create a dictionary {'1': 1, '2': 2, ..., 'n': n}
        self._port_map = dict(zip([str(i + 1) for i in range(self.port_count)],
                                  [i + 1 for i in range(self.port_count)]))
        # Add user-specified overrides.
        self._port_map.update(port_map if port_map is not None else {})
        # Convert to VICI range (2x as many positions) to pass to parent class.
        position_map = {c:self._to_nearest_hw_position(i, open=True)
                        for c,i in self._port_map.items()}
        super().__init__(serial, positions=port_count * 2, position_map=position_map)
        self.current_port = self._get_current_port()
        logger_name = self.__class__.__name__ + f".{serial.portstr}"
        self.log = logging.getLogger(logger_name)
        self.log.debug(f"high level port map:            {self._port_map}")
        self.log.debug(f"Underlying VICI representation: {position_map}")

    def _get_current_port(self):
        curr_hw_position = int(self.current_position())
        return Port(port=ceil(float(curr_hw_position)/2),
                    open=(curr_hw_position % 2 != 0))  # open if odd

    def _to_nearest_hw_position(self, port: int, open: bool = True):
        if open:
            return (port * 2 - 1) % (self.port_count * 2)
        return port * 2

    def _check_port_range(self, port: Union[int, str]):
        if str(port) not in self._port_map:
            raise ValueError(f"Requested port {port} does not exist.")

    def move_to_port(self, port: Union[int, str]):
        """Move to the specified position."""
        self._check_port_range(port)
        port_index = self._port_map[str(port)]  # Convert name to int.
        open_hw_position = self._to_nearest_hw_position(port_index, open=True)
        self.logger.debug(f"Opening port: {port}.")
        super().move_to_position(open_hw_position)
        self.current_port.port = port
        self.current_port.open = True

    def is_open(self):
        return self.current_port.open

    def open(self):
        self.move_to_port(self.current_port.port)

    def close(self):
        port_index = self._port_map[str(self.current_port.port)]
        closed_hw_position = self._to_nearest_hw_position(port_index, open=False)
        super().move_to_position(closed_hw_position)
        self.current_port.open = False

    def move_clockwise_to_port(self, port: Union[int, str]):
        self._check_port_range(port)
        port_index = self._port_map[str(port)]  # Convert name to int.
        open_hw_position = self._to_nearest_hw_position(port_index, open=True)
        self.logger.debug(f"Clockwise move to open port: {port}.")
        super().move_clockwise_to_position(open_hw_position)
        self.current_port.port = port
        self.current_port.open = True

    def move_counterclockwise_to_port(self, port: Union[int, str]):
        self._check_port_range(port)
        port_index = self._port_map[str(port)]  # Convert name to int.
        open_hw_position = self._to_nearest_hw_position(port_index, open=True)
        self.logger.debug(f"Counterclockwise move to open port: {port}.")
        super().move_counterclockwise_to_position(open_hw_position)
        self.current_port.port = port
        self.current_port.open = True



if __name__ == "__main__":

    from serial import Serial
    from time import sleep
    logging.basicConfig(level=logging.DEBUG)

    port_map = {'water': 1, 'juice': 2, 'soda_pop': 3}

    ser = Serial("/dev/ttyUSB0", baudrate=9600)
    vici = CloseableVICI(ser, port_count=10, port_map=port_map)

    ports = ['water', 'soda_pop', '2', '10']
    for port in ports:
        print(f"Moving to port: {port}.")
        vici.move_to_port(port)
        sleep(1)
        print("Closing port.")
        vici.close()
        sleep(1)
        print("Opening port.")
        vici.open()
        print()
        sleep(1)

    #vici.move_counterclockwise_to_port(1)
    #sleep(1)
    #vici.move_counterclockwise_to_port(10)
    #sleep(1)
