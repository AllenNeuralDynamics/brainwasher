from brainwasher.devices.mixer import Mixer
from ticlib import TicUSB

MICROSTEP_FACTORS = {
    0: 1,
    1: 2,
    2: 4,
    3: 8,
    4: 16,
    5: 32,
    6: 2,   # 1/2 step 100%
    7: 64,
    8: 128,
    9: 256,
}


class PololuTicMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, max_rpm: float,
                 min_rpm: float = 0,
                 steps_per_rev: int = 200,
                 name: str = None):
        self.tic = TicUSB()
        self.steps_per_rev = steps_per_rev
        super().__init__(min_rpm=min_rpm, max_rpm=max_rpm, name=name)

    def _set_mixing_speed(self, rpm: float):
        
        # convert rpms to microsteps per 10,000 secs
        microstep_mode = self.tic.get_step_mode()
        microsteps_per_rev = self.steps_per_rev * MICROSTEP_FACTORS[microstep_mode]
        steps_per_10000_secs = (rpm/60) * microsteps_per_rev * 10000
        self.tic.set_target_velocity(steps_per_10000_secs)

    def _start_mixing(self):
        self.tic.energize()
        self.tic.enter_safe_start()
    
    def _stop_mixing(self):
        self.tic.deenergize()
        self.tic.exit_safe_start()