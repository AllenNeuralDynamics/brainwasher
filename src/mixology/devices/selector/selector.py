import logging
import math
import time
from typing import Optional
from mixology.devices.serial_device import SerialDevice
from mixology.devices.simulated_devices.selector import SimSelector
import serial
from pydantic import BaseModel, Field


class SerialSelectorConfig(BaseModel):
    """Configuration for a single serial-connected selector unit."""
    selector_name: str = Field(..., description="A unique name for the selector.")
    port: str = Field(..., description="The serial COM port for the selector.")


class SerialSelector(SerialDevice):
    """Represents a single selector valve that communicates over a serial port."""

    def __init__(self, name: str, port: str):
        self.config = SerialSelectorConfig(selector_name=name, port=port)
        self.log = logging.getLogger(f"{self.__class__.__name__}.{self.config.selector_name}")
        self._connection: Optional[serial.Serial] = None

    def connect(self) -> None:
        """Open the serial connection to the device."""
        self.log.info(f"Connecting to selector on {self.config.port}")
        try:
            self._connection = serial.Serial(
                port=self.config.port,
                baudrate=9600,
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

    def move(self, position: int) -> None:
        """Send a move command to this selector device."""
        if not self.is_connected():
            raise RuntimeError("Selector is not connected.")
        valve_address = 1  # Default for Elveflow devices
        command = f"/{valve_address}B{position}R\r"
        self.log.debug(f"Sending command to {self.config.port}: {repr(command)}")
        self._connection.write(command.encode())
