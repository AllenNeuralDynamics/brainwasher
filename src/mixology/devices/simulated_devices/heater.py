"""Simulated Heater"""

import math
from threading import Lock
from time import perf_counter
from typing import Optional

from mixology.devices.heater.heater import HeaterDevice


class SimHeater(HeaterDevice):
    """Simulated group of heating stages for testing and offline development.

    Each stage that is on moves linearly toward the target temperature, and each
    stage that is off moves back toward ambient, at `ramp_rate_c_per_s`.
    """

    def __init__(
        self,
        stage_names: list[str],
        name: str = "SimHeater",
        ambient_temp_c: float = 22.0,
        ramp_rate_c_per_s: float = 1.0,
        **kwds,
    ):
        """`kwds` (e.g., temp_tolerance_c, ramp_timeout_s, poll_interval_s) go to
        HeaterDevice."""
        super().__init__(name=name, **kwds)
        self.ambient_temp_c = ambient_temp_c
        self.ramp_rate_c_per_s = ramp_rate_c_per_s
        self._temps_c = {stage: ambient_temp_c for stage in stage_names}
        self._stages_on: set[str] = set()
        self._target_c: Optional[float] = None
        self._last_update_s = perf_counter()
        self._lock = Lock()  # Temperatures may be read from several threads.
        self._connected = False

    def connect(self) -> None:
        self.log.debug("Connecting to simulated heater.")
        self._connected = True

    def disconnect(self) -> None:
        self.turn_off()
        self.log.debug("Disconnecting from simulated heater.")
        self._connected = False

    def set_target_temperature(self, temp_c: float) -> None:
        with self._lock:
            self._update_temperatures()
            self._target_c = temp_c
        self.log.info(f"Target temperature set to {temp_c} C.")

    def turn_on(self, stages: Optional[list[str]] = None) -> None:
        if not self._connected:
            raise RuntimeError("Simulated heater is not connected.")
        if self._target_c is None:
            raise RuntimeError("Set a target temperature before turning stages on.")
        stages = self._check_stages(stages)
        with self._lock:
            self._update_temperatures()
            self._stages_on.update(stages)
        self.log.info(f"Heating {stages} to {self._target_c} C.")

    def turn_off(self, stages: Optional[list[str]] = None) -> None:
        stages = self._check_stages(stages)
        with self._lock:
            self._update_temperatures()
            self._stages_on.difference_update(stages)
        self.log.info(f"Stopped heating {stages}.")

    def get_stage_states(self) -> dict[str, bool]:
        with self._lock:
            return {stage: stage in self._stages_on for stage in self._temps_c}

    def get_temperatures_c(self) -> dict[str, float]:
        with self._lock:
            self._update_temperatures()
            return dict(self._temps_c)

    def self_test(self) -> None:
        self.log.info("Self-test passed.")

    def _check_stages(self, stages: Optional[list[str]]) -> list[str]:
        """Return `stages` (every stage if None), rejecting unknown names."""
        if stages is None:
            return list(self._temps_c)
        unknown = set(stages) - set(self._temps_c)
        if unknown:
            raise ValueError(f"Unknown stages: {sorted(unknown)}")
        return list(stages)

    def _update_temperatures(self) -> None:
        """Move each stage toward its target by the time elapsed since the last update."""
        now_s = perf_counter()
        max_step_c = (now_s - self._last_update_s) * self.ramp_rate_c_per_s
        self._last_update_s = now_s
        for stage, temp_c in self._temps_c.items():
            heating = stage in self._stages_on
            target_c = self._target_c if heating else self.ambient_temp_c
            delta_c = target_c - temp_c
            if abs(delta_c) <= max_step_c:
                self._temps_c[stage] = target_c
            else:
                self._temps_c[stage] = temp_c + math.copysign(max_step_c, delta_c)
