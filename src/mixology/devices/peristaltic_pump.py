
from abc import ABC, abstractmethod
from typing import List


class PumpDevice():
    """Interface for peristaltic pump devices."""

    @abstractmethod
    def initialize(self) -> None:
        """Connect, configure, and verify the pump."""
        ...

    @abstractmethod
    def pump_volume(self, volume_ml: float, rate_ml_per_min: float) -> None:
        """Dispense a specified volume at a given flow rate.

        Args:
            volume_ml: Volume to pump in mL.
            rate_ml_per_min: Flow rate in mL/min.
        """
        ...

    @abstractmethod
    def start(self) -> None:
        """Start the pump."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the pump."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Return True if the pump is currently running."""
        ...

    @abstractmethod
    def set_flow_rate(self, ml_per_min: float) -> bool:
        """Set the pump flow rate.

        Args:
            ml_per_min: Target flow rate in mL/min.

        Returns:
            True if the rate was set successfully.
        """
        ...

    @abstractmethod
    def get_speed(self) -> float:
        """Return the current pump speed in mL/min."""
        ...