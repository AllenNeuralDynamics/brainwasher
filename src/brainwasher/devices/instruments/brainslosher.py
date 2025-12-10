from .instrument import Instrument
from runze_control.syringe_pump import SY08
from brainwasher.devices.pololu.pololu_tic_mixer import PololuTicMixer
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob
from brainwasher.devices.vessels import ReactionVessel, WasteVessel
from threading import RLock, current_thread
from functools import wraps
from time import sleep

def lock_flowpath(func):
    """Provide methods with exclusive access to components that alter the flowpath."""
    @wraps(func) # required for sphinx doc generation
    def inner(self, *args, **kwds):
        with self.flowpath_lock:
            self.log.debug(f"Locking flowpath to "
                           f"{current_thread().name} for {func.__name__} fn.")
            return func(self, *args, **kwds)
    return inner

class BrainSlosher(Instrument):
    """

    Class for controlling 0365 - AIND Hydrogel Imaging Prep Automation

    """

    def __init__(self, 
                config: BrainSlosherConfig,
                reaction_vessel: ReactionVessel,
                pump: SY08, 
                mixer: PololuTicMixer, 
                waste_vessel: WasteVessel):
        
        super().__init__()

        self.config = config
        self.reaction_vessel = reaction_vessel
        self.pump = pump
        self.mixer = mixer
        self.waste_vessel = waste_vessel

        # Thread-safe protection within a class instance.
        self.flowpath_lock = RLock()

    def fill(self, volume: float, solution: str) -> None:
        """Fill reaction vessel with specified solution amount"""

    def drain(self, volume: float) -> None:
        """Drain reaction"""

    def prime_line(self, solution: str) -> None:
        """Prime line"""

    def purge_line(self) -> None:
        """Purge line"""
        self.pump.move_valve_to_position(self.config.selector_port_map["air"])
        self.pump.withdraw(self.config.max_syringe_volume_ml*1000)  # convert ml to ul
        self.pump.move_valve_to_position(self.config.selector_port_map["chamber"])
        self.pump.reset_syringe_position()

    def validate_job_against_instrument(self, job: BrainSlosherJob):
        """
        Validate solutions and volumes specified in job are compatable with insturment
        
        :raises ValueError: if solution or volume is not valid

        """

    def run_step(self, solution: str, duration_min: float, washes: int):
        """
        Run through cycles defined in job 

        :param solution: solution to use in all washes in cycle
        :param duration_min: duration of all washes in cycle
        :param washes: number of washes in cycle

        """
        purge_line()
        for i in range(washes):
            prime_line(solution)
            run_wash_step(duration_s=duration_min*60)

    @lock_flowpath
    def run_wash_step(self, 
                    duration_s: float, 
                    solution: str):
        
        """Drain (optional), mix, and empty (opt) the reaction vessel to
        complete one wash cycle.

        :param duration_s: time in seconds to mix.
        :param start_empty: if True, drain the vessel before introducing new
            liquids.
        :param end_empty: if True, draing the vessel after mixing.
        :param solution: solution to use in wash.

        """
        # Validate solution
        if solution not in self.config.selector_port_map.keys():
            raise ValueError(f"Solution {solution} is not currently plumbed based on config.")


        # Drain if requested.
        if start_empty: # and self.rxn_vessel.curr_volume_ul > 0:
            self.drain_vessel()
        # Fill
        if len(solution):
            self.log.info(f"Filling vessel with solution: {solution}.")
        for chemical_name, ul in solution.items():
            self.dispense_to_vessel(ul, chemical_name)
        if mix_speed_rpm > 0:
            try:
                self.mixer.set_mixing_speed(mix_speed_rpm)
            except NotImplementedError:
                self.log.warning("Mixer does not support speed control. "
                                    "Skipping speed setting.")
                mix_speed_rpm = self.mixer.rpm_range[1]
        # Produce a sensible log message depending on what we're going to do.
        if (mix_speed_rpm > 0) and (duration_s > 0):
            intermittent_mixing_msg = ""
            if intermittent_mixing:
                intermittent_mixing_msg = (f" with intermittent mixing "
                    f"strategy: on for {intermittent_mixing_on_time_s}[sec], "
                    f"off for {intermittent_mixing_off_time_s}[sec]")
            self.log.info(f"Mixing for {duration_s} seconds at {mix_speed_rpm}"
                            f"[rpm]" + intermittent_mixing_msg + ".")
        elif duration_s > 0:
            self.log.info(f"Idling for {duration_s} seconds.")
        start_time_s = now()
        if mix_speed_rpm > 0:
            self.mixer.start_mixing()
        # Wait while implementing intermittent mixing strategy.
        while (now() - start_time_s) < duration_s:
            # Handle pause request if called in a "job" context.
            if self.job_worker and self.job_worker.is_alive() and self.pause_requested.is_set():
                elapsed_time_s = round(now() - start_time_s)
                action_msg = "mixing" if mix_speed_rpm else "idling"
                self.log.warning(f"Aborting after {elapsed_time_s}[s] of {action_msg}.")
                self.resume_state_overrides.update(duration_s=(duration_s - elapsed_time_s))
                return
            if not intermittent_mixing:
                sleep(0.010)
                continue
            sleep(intermittent_mixing_on_time_s)
            self.mixer.stop_mixing()
            sleep(intermittent_mixing_off_time_s)
            self.mixer.start_mixing()
        if mix_speed_rpm > 0:
            self.mixer.stop_mixing()
        # Drain (if required).
        if end_empty:
            self.drain_vessel()


