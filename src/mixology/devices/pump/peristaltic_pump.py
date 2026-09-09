
# mixology.devices.peristaltic_pump (Base Device)
from abc import ABC, abstractmethod
from typing import List


class PumpDevice():
    """Interface for peristaltic pump devices."""

    def __init__(self, name: str = ""):
        self.name = name

    @abstractmethod
    def initialize(self) -> None:
        """Connect, configure, and verify the pump."""
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
    def set_flow_rate(self, flow_rate_mlpm: float) -> bool:
        """Set the pump flow rate.

        Args:
            flow_rate_mlpm: Target flow rate in mL/min.

        Returns:
            True if the rate was set successfully.
        """
        ...

    @abstractmethod
    def get_speed_ml_per_min(self) -> float:
        """Return the current pump speed in mL/min."""
        ...

    # --- Shared Common Functions ---
    def get_dispense_duration_s(self, volume_ml: float) -> float:
        """
        Calculates how long a dispense will take in seconds at the current flow rate.
        """
        if volume_ml <= 0:
            return 0.0
        return self.get_dispense_duration_m(volume_ml) * 60.0

    def get_dispense_duration_m(self, volume_ml: float) -> float:
        """
        Calculates how long a dispense will take in minutes at the current flow rate.
        """
        current_speed = self.get_speed_ml_per_min()
        if current_speed <= 0:
            return 0.0
        return volume_ml / current_speed

    def get_dispense_volume_ml(self, duration_s: float) -> float:
        """
        Calculates the volume dispensed in milliliters given the elapsed time and flow rate.
        """
        current_speed = self.get_speed_ml_per_min()
        if current_speed <= 0:
            return 0.0
        return (duration_s / 60.0) * current_speed