"""Base classes for serial-connected devices."""
from abc import ABC, abstractmethod


class SerialDevice(ABC):
    """Base interface for all serial-connected lab devices."""

    @abstractmethod
    def connect(self) -> None:
        """Open the serial connection to the device."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Close the serial connection and release resources."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        ...

