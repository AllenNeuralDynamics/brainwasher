from brainwasher.devices.mixer import Mixer
import subprocess
import logging

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

OPERATION_STATE = {
    "reset": 0,
    "reenergized": 2,
    "soft_error": 4,  
    "waiting_for_err_line": 6,
    "starting_up"  : 8,
    "normal": 10
}

class TicCmd:
    """Minimal ticcmd wrapper for USB control."""

    def __init__(self, serial: str):
        self.serial = serial

    def _run(self, *args) -> str:
        """
        Send list of args to tic
        
        :param args: list of args for subprocess
        """
        
        cmd = ["ticcmd", "--serial", self.serial, *args] 
        return subprocess.check_output(cmd, text=True)
    
    def energize(self):
        self._run("--energize")

    def deenergize(self):
        self._run("--deenergize")

    def exit_safe_start(self):
        self._run("--exit-safe-start")

    def enter_safe_start(self):
        self._run("--enter-safe-start")

    def set_target_velocity(self, velocity: int | str):
        
        logging.debug(f"Setting velocity to {velocity}.")
        self._run("--velocity", str(int(velocity)))

    def set_step_mode(self, step_mode) -> int:
        logging.debug(f"Setting step mode to {step_mode}.")
        self._run("--step-mode", str(int(step_mode)))
    
    def _parse_status(self, starts_with: str) -> str:
        """
        Parse status message for specified line

        :param starts_with: string line starts with 
        """
        out = self._run("--status")
        for line in out.splitlines():
            if line.strip().startswith(starts_with):
                return line.split()[-1]
        
        raise RuntimeError(f"Could not determine status message line that starts with {starts_with}.")
        

class PololuTicMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, serial:str, max_rpm: float,
                 min_rpm: float = 0,
                 steps_per_rev: int = 200,
                 microstep_mode: int = 16,
                 name: str = None):
        
        self.tic = TicCmd(serial=serial)
        self.steps_per_rev = steps_per_rev

        # put mixer in corret microstep mode
        self.tic.set_step_mode(microstep_mode)
        self.microstep_mode = microstep_mode

        super().__init__(min_rpm=min_rpm, max_rpm=max_rpm, name=name)

    def _set_mixing_speed(self, rpm: float):
        
        # convert rpms to microsteps per 10,000 secs
        logging.debug(f"Setting rpm to {rpm}")
        microsteps_per_rev = self.steps_per_rev * MICROSTEP_FACTORS[self.microstep_mode]
        steps_per_10000_secs = (rpm/60) * microsteps_per_rev * 10000
        logging.debug(f"rpm of {rpm} converted to {steps_per_10000_secs} steps/10000s.")
        self.tic.set_target_velocity(round(steps_per_10000_secs))

    def _start_mixing(self):
        logging.debug(f"Starting mixing.")
        self.tic.energize()
        self.tic.exit_safe_start()
    
    def _stop_mixing(self):
        logging.debug("Stopping mixing.")
        self.tic.deenergize()
        self.tic.enter_safe_start()
