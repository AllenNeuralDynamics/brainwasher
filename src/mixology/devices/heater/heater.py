"""Heater Base Class"""

from abc import ABC, abstractmethod
from typing import Optional


class HeaterDevice(ABC):
    """Interface for a group of heating stages that share one target temperature.

    Each stage can be turned on or off on its own; every stage that is on heats
    toward the shared target. Heaters may use a DAQ rather than serial, so they
    do not inherit from SerialDevice. The caller decides how long to wait for the
    stages to reach temperature and how long to hold it there.
    """

    def __init__(self, name: str = ""):
        self.name = name

    @abstractmethod
    def connect(self) -> None:
        """Initialize hardware connections."""
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Turn every stage off and release hardware resources."""
        ...

    @abstractmethod
    def set_target_temperature(self, temp_c: float) -> None:
        """Set the target temperature [C] shared by every stage that is on."""
        ...

    @abstractmethod
    def turn_on(self, stages: Optional[list[str]] = None) -> None:
        """Start heating `stages` (every stage if None) toward the target temperature.

        Raises:
            RuntimeError: If no target temperature has been set.
        """
        ...

    @abstractmethod
    def turn_off(self, stages: Optional[list[str]] = None) -> None:
        """Stop heating `stages` (every stage if None)."""
        ...

    @abstractmethod
    def get_stage_states(self) -> dict[str, bool]:
        """Return whether each stage is on, keyed by stage name."""
        ...

    @abstractmethod
    def get_temperatures_c(self) -> dict[str, float]:
        """Return the current temperature [C] of each stage, keyed by stage name."""
        ...

    @abstractmethod
    def self_test(self) -> None:
        """Check that every stage reads a sane temperature and responds to heating.

        Raises:
            RuntimeError: If any stage fails the test.
        """
        ...
