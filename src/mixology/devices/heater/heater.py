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

    def __init__(
        self, name: str = "", temp_tolerance_c: float = 1.5, ramp_timeout_s: float = 300.0
    ):
        """
        Args:
            name: Device name.
            temp_tolerance_c: A stage counts as at temperature within this many
                degrees C below the target.
            ramp_timeout_s: Max time for the stages to reach the target temperature.
        """
        self.name = name
        self.temp_tolerance_c = temp_tolerance_c
        self.ramp_timeout_s = ramp_timeout_s

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

    # --- Shared Common Functions ---
    def get_cold_stages(self, temp_c: float) -> dict[str, float]:
        """Return each stage that is on but still more than `temp_tolerance_c`
        below `temp_c`, with its current temperature [C].
        """
        stages_on = self.get_stage_states()
        threshold_c = temp_c - self.temp_tolerance_c
        return {
            stage: stage_temp_c
            for stage, stage_temp_c in self.get_temperatures_c().items()
            if stages_on[stage] and stage_temp_c < threshold_c
        }
