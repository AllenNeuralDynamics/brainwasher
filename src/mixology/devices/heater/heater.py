"""Heater Base Class"""

import logging
from abc import ABC, abstractmethod
from threading import Event
from time import perf_counter
from typing import Optional


class HeaterDevice(ABC):
    """Interface for a group of heating stages that share one target temperature.

    Each stage can be turned on or off on its own; every stage that is on heats
    toward the shared target. Heaters may use a DAQ rather than serial, so they
    do not inherit from SerialDevice. `heat_up` waits for the stages to reach
    temperature; the caller decides how long to hold it there.
    """

    def __init__(
        self,
        name: str = "",
        active_stages: Optional[list[str]] = None,
        temp_tolerance_c: float = 1.5,
        ramp_timeout_s: float = 300.0,
        poll_interval_s: float = 1.0,
    ):
        """
        Args:
            name: Device name.
            active_stages: Stages that `heat_up` turns on (every stage if None).
            temp_tolerance_c: A stage counts as at temperature within this many
                degrees C below the target.
            ramp_timeout_s: Max time for the stages to reach the target temperature.
            poll_interval_s: How often `heat_up` checks the stage temperatures.
        """
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)
        self.name = name
        self.active_stages = active_stages
        self.temp_tolerance_c = temp_tolerance_c
        self.ramp_timeout_s = ramp_timeout_s
        self.poll_interval_s = poll_interval_s

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

    def heat_up(self, temp_c: float, cancel: Optional[Event] = None) -> bool:
        """Turn the active stages on and wait until all of them reach `temp_c`.

        Heating stays on when this returns or raises; the caller turns it off.

        Args:
            temp_c: Target temperature [C].
            cancel: If set while waiting, stop waiting and return False.

        Returns:
            False if `cancel` was set before the stages reached temperature.

        Raises:
            RuntimeError: If a stage is still too cold after `ramp_timeout_s`.
        """
        cancel = cancel or Event()
        self.set_target_temperature(temp_c)
        self.turn_on(self.active_stages)
        deadline_s = perf_counter() + self.ramp_timeout_s
        while cold_stages := self.get_cold_stages(temp_c):
            self.log.debug(f"Waiting for stages to reach {temp_c} C: {cold_stages}")
            if perf_counter() > deadline_s:
                raise RuntimeError(
                    f"Stages did not reach {temp_c} C within "
                    f"{self.ramp_timeout_s} s: {cold_stages}"
                )
            if cancel.wait(timeout=self.poll_interval_s):
                return False
        self.log.info(f"All stages reached {temp_c} C.")
        return True
