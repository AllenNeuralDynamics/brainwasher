import logging
import serial
from typing import Optional, Union, Dict
from mixology.devices.serial_device import SerialDevice
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class Selector(ABC):
    """Base interface for all serial-connected selector devices."""

    @abstractmethod
    def move_to_position(self, position: Union[int, str]) -> None:
        """Move the selector to the specified position."""
        ...
        

class SerialSelectorConfig(BaseModel):
    """Configuration for a single serial-connected selector unit."""
    selector_name: str = Field(..., description="A unique name for the selector.")
    port: str = Field(..., description="The serial COM port for the selector.")
    baudrate: int = Field(..., description="The baudrate for the serial connection.")


class SerialSelector(Selector, SerialDevice):
    """Represents a single selector valve that communicates over a serial port."""

    def __init__(self, name: str, port: str, baudrate: int, position_map: Dict[str, int] = None):
        """Initialize the SerialSelector with a name, serial port, and optional position map.
            name: A unique name for the selector.
            port: The serial COM port to which the selector is connected.
            position_map: Optional dictionary mapping reagent names to port numbers.
        """
        self.config = SerialSelectorConfig(selector_name=name, port=port, baudrate=baudrate)
        self.log = logging.getLogger(f"{self.__class__.__name__}.{self.config.selector_name}")
        self._connection: Optional[serial.Serial] = None
        self.port_map = position_map or {}

    def connect(self) -> None:
        """Open the serial connection to the device."""
        self.log.info(f"Connecting to selector on {self.config.port}")
        try:
            self._connection = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baudrate,
                parity=serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                timeout=1,
            )
            self.log.info(f"Connected to selector on {self.config.port}")
        except serial.SerialException as e:
            self.log.error(f"Failed to connect to selector on {self.config.port}: {e}")
            raise

    def disconnect(self) -> None:
        """Close the serial connection and release resources."""
        if self._connection and self._connection.is_open:
            self._connection.close()
            self.log.info(f"Disconnected from selector on {self.config.port}")

    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        return self._connection and self._connection.is_open

    def move_to_position(self, position: Union[int, str]) -> None:
        """Send a move command to this selector device."""
        if not self.is_connected():
            raise RuntimeError("Selector is not connected.")

        if isinstance(position, str):
            if position not in self.port_map:
                raise ValueError(f"Reagent '{position}' not found in port map.")
            port_number = self.port_map[position]
        else:
            port_number = int(position)

        valve_address = 1  # Default for Elveflow devices
        command = f"/{valve_address}B{port_number}R\r"
        self.log.debug(f"Sending command to {self.config.port}: {repr(command)}")
        self._connection.write(command.encode())

