from .instrument import Instrument
from runze_control.multichannel_syringe_pump import SY01B
from brainwasher.devices.pololu.pololu_tic_mixer import PololuTicMixer
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob
from brainwasher.devices.vessels import ReactionVessel, WasteVessel
from threading import RLock, current_thread
from functools import wraps
from time import sleep
from typing import Literal
from pathlib import Path
from time import perf_counter

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
                rxn_vessel: ReactionVessel,
                pump: SY01B, 
                mixer: PololuTicMixer, 
                waste_vessel: WasteVessel):
        
        super().__init__()

        self.config = config
        self.rxn_vessel = rxn_vessel
        self.pump = pump
        self.mixer = mixer
        self.waste = waste_vessel
        self.resume_state_overrides = {}
        
        # Thread-safe protection within a class instance.
        self.flowpath_lock = RLock()

    def fill_chamber(self, solution: str, volume_ml: float) -> None:
        """
        Fill reaction vessel with specified solution amount
        
        :param solution: solution to fill chamber with
        :param volume_ml: total volume to fill in mL
        """
        
        if self.rxn_vessel.curr_volume_ul + volume_ml * 1000 > self.rxn_vessel.max_volume_ul:
            raise ValueError("Chamber will exceed max volume if filled. Please drain.")
        
        self.rxn_vessel.add_solution({solution:volume_ml * 1000})
        self.withdraw_and_dispense_solution(solution, volume_ml, 'chamber')

    
    def drain_chamber(self) -> None:
        """
        Drain chamber
        """
        
        if self.rxn_vessel.curr_volume_ul + self.waste.curr_volume_ul > self.waste.max_volume_ul:
            raise ValueError("Waste vessel will exceed max volume if chamber is drained. Please empty.")

        volume_ml = self.rxn_vessel.curr_volume_ul/1000
        self.withdraw_and_dispense_solution("drain", 
                                            volume_ml + self.config.drain_volume_buffer_ml, 
                                            "waste")
        self.waste.add_solution(**self.rxn_vessel.solution)
        self.rxn_vessel.purge_solution()

    @lock_flowpath
    def withdraw_and_dispense_solution(self, 
                  solution: str, 
                  volume_ml: float, 
                  dispense_to: Literal["waste", "chamber"]) -> None:
        """
        Withdraw solution and dispense into either waste or chamber
        
        :param solution: solution to pull through line
        :param volume_ml: total volume to push through line in mL
        :param dispense_to: where to dispense solution. Must be to waste or chamber
        """
        
        max_pump = self.config.max_syringe_volume_ml
        while volume_ml > 0:
            pump_vol = max_pump if volume_ml >= max_pump else volume_ml
            self.pump.move_valve_to_position(solution)
            self.pump.withdraw(pump_vol * 1000) # convert ml to ul
            self.pump.move_valve_to_position(dispense_to)
            self.pump.dispense(pump_vol * 1000) # convert ml to ul
            volume_ml -= pump_vol

    def prime_line(self, solution: str) -> None:
        """
        Prime line
        
        :param solution: solution to prime line with
        """
        self.withdraw_and_dispense_solution(solution, self.config.purge_volume_ml, "waste")
    
    def purge_line(self) -> None:
        """Purge line"""
        
        self.withdraw_and_dispense_solution(self.config.selector_port_map["air"], 
                                            self.config.purge_volume_ml, 
                                            "chamber")
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
        self.purge_line()
        for i in range(washes):
            self.prime_line(solution)
            self.run_wash_step(duration_min=duration_min, solution=solution)

    def _run_job_worker(self, job: BrainSlosherJob, job_path: Path):
        """
        Configure mixer for session        
        """
        
        self.mixer.set_mixing_speed(job.motor_speed_rpm)
        return super()._run_job_worker(job, job_path)

    @lock_flowpath
    def run_wash_step(self, 
                    duration_min: float, 
                    solution: str):
        
        """Fill, mix, and empty the reaction vessel to
        complete one wash cycle.

        :param duration_min: time in minutes to mix.
        :param solution: solution to use in wash.
        :param fill_volume_ml: volume to fill vessel

        """
        # Validate solution
        if solution not in self.config.selector_port_map.keys():
            raise ValueError(f"Solution {solution} is not currently plumbed based on config.")

        # Check if chamber is in correct state 
        if self.rxn_vessel.solution != {solution: self.config.fill_volume_ml}:
            self.drain_chamber()
            self.prime_line(solution)
            self.fill_chamber(solution, 
                              self.config.fill_volume_ml)
            self.purge_line()
        
        start_time_s = perf_counter()
        duration_s = duration_min * 60
        while (perf_counter() - start_time_s) < duration_s:
            # Handle pause request if called in a "job" context.
            if self.job_worker and self.job_worker.is_alive() and self.pause_requested.is_set():
                elapsed_time_s = round(perf_counter()() - start_time_s)
                self.log.warning(f"Aborting after {elapsed_time_s}[s].")
                self.resume_state_overrides.update(duration_min=(duration_s - elapsed_time_s)/60)
                return
        self.drain_chamber()
        self.mixer.stop_mixing()
        


