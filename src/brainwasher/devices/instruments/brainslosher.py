from .instrument import Instrument
from runze_control.multichannel_syringe_pump import SY01B
from brainwasher.devices.pololu.pololu_tic_mixer import PololuTicMixer
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob, BrainSlosherJobStatus
from brainwasher.devices.vessels import ReactionVessel, WasteVessel
from threading import RLock, current_thread, Lock
from functools import wraps
from time import sleep
from typing import Literal
from pathlib import Path
from time import perf_counter
import yaml
from queue import Queue

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

        # attribute to track events that occur in job_worker
        self.job_status_lock = Lock()
        self.job_status: BrainSlosherJobStatus = BrainSlosherJobStatus(status="idle")

        # attributes to calculate progress
        self._job: BrainSlosherJob = None

        # track current step for progress
        self._step = 0

    def clear_job(self) -> None:
        """
        Clear job and update status
        """
        if self.job_status.status == "running":
            self.log.warning("Cannot reset state when instrument is running. Please pause.")
            return 
        self._job = None
        with self.job_status_lock:
            self.job_status = BrainSlosherJobStatus(status="idle")

    def clear_status(self) -> None:
        """clear status of failed if possible."""  
        
        if self.job_status.status != "failed":
            self.log.warning("No failed status to clear.")
            return 
        
        status = "paused" if self._job and self._job.resume_state else "idle"
        with self.job_status_lock:
            self.log.info(f"Clearing failed job status and setting to {status}")
            self.job_status = BrainSlosherJobStatus(status=status)

    def get_progress(self) -> int:
        """
        Progress of current run between 0 - 100
        """

        # return if no job or no resume state
        if not self._job or (not self.resume_state_overrides and not self._job.resume_state):
            return

        protocol = self._job.protocol
        curr_step_index = self._step - 1
        est_min = sum(step.washes * step.duration_min for step in protocol)

        # current step overrides or resume state
        curr_duration = (
            self.resume_state_overrides.get("duration_min")
            or self._job.resume_state.overrides["duration_min"]
        )
        curr_washes = (
            self.resume_state_overrides.get("washes")
            or self._job.resume_state.overrides["washes"]
        )

        elapsed_minutes = sum(step.washes * step.duration_min for step in protocol[:curr_step_index])

        # current step partial progress
        current_step = protocol[curr_step_index]
        elapsed_minutes += (curr_washes - 1) * current_step.duration_min
        elapsed_minutes += current_step.duration_min - curr_duration

        pct_done = elapsed_minutes / est_min
        return round(pct_done * 100, 1)


    def fill_chamber(self, solution: str, volume_ml: float) -> None:
        """
        Fill reaction vessel with specified solution amount
        
        :param solution: solution to fill chamber with
        :param volume_ml: total volume to fill in mL
        """
        
        if self.rxn_vessel.curr_volume_ul + volume_ml * 1000 > self.rxn_vessel.max_volume_ul:
            raise ValueError("Chamber will exceed max volume if filled. Please drain.")
        
        self.log.info(f"Filling chamber with {volume_ml}mL of {solution}")
        self.rxn_vessel.add_solution(**{solution:volume_ml * 1000})
        self.withdraw_and_dispense_solution(solution, volume_ml, 'chamber')

    
    def drain_chamber(self, volume_ml: float = None) -> None:
        """
        Drain chamber
        """
        
        if self.rxn_vessel.curr_volume_ul + self.waste.curr_volume_ul > self.waste.max_volume_ul:
            raise ValueError("Waste vessel will exceed max volume if chamber is drained. Please empty.")

        volume_ml = volume_ml or self.rxn_vessel.curr_volume_ul/1000 
        self.log.info(f"Draining chamber of {volume_ml}mL")
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
            self.log.debug(f"Moving pump to {solution} valve.")
            self.pump.move_valve_to_position(self.config.selector_port_map[solution])
            self.log.debug(f"Withdrawing {pump_vol}ml of {solution}.")
            self.pump.withdraw(pump_vol * 1000) # convert ml to ul
            self.log.debug(f"Dispensing to {dispense_to}.")
            self.pump.move_valve_to_position(self.config.selector_port_map[dispense_to])
            self.pump.dispense(pump_vol * 1000) # convert ml to ul
            volume_ml -= pump_vol
        self.log.debug(f"finished dispensing {volume_ml}mL of {solution} to {dispense_to}")

    def prime_line(self, solution: str) -> None:
        """
        Prime line
        
        :param solution: solution to prime line with
        """

        self.log.info(f"Priming line with {self.config.prime_volume_ml}mL {solution}.")
        self.withdraw_and_dispense_solution(solution, self.config.prime_volume_ml, "waste")
    
    def purge_line(self) -> None:
        """Purge line"""
        
        self.log.info(f"Purging line of {self.config.purge_volume_ml}mL.")
        self.withdraw_and_dispense_solution("air", 
                                            self.config.purge_volume_ml, 
                                            "chamber")
        self.pump.reset_syringe_position()

    def validate_job_against_instrument(self, job: BrainSlosherJob):
        """
        Validate solutions and volumes specified in job are compatable with insturment
        
        :raises ValueError: if solution or volume is not valid

        """
        # TODO: implement checks if neccessary 
        pass

    def run_step(self, solution: str, duration_min: float, washes: int):
        """
        Run through cycles defined in job 

        :param solution: solution to use in all washes in cycle
        :param duration_min: duration of all washes in cycle
        :param washes: number of washes in cycle

        """
        self._step += 1
        self.purge_line()
        self.resume_state_overrides.update(washes=washes)
        for i in range(washes):
            self.prime_line(solution)
            try:
                self.log.info(f"Starting wash step {i}")
                self.run_wash_step(duration_min=duration_min, solution=solution)
            except Exception as e:
                self.log.error(f"Error while performing wash {i + 1}: {str(e)}")
                return
            if self.pause_requested.is_set():
                return
            # update state to reflect was wash finished
            self.resume_state_overrides.update(washes=washes-(i+1))
    
    def _load_job(self, job_path: str) -> BrainSlosherJob:
        """
            Rewrite to validate against BrainSlosherJob type       
        """
        
        job_path = Path(job_path)
        if not job_path.exists():
            raise FileNotFoundError(f"Job does not exist at location: "
                                    f"{job_path.resolve()}")
        with open(job_path) as yaml_stream:
            self.log.debug(f"Loading job from: {job_path.absolute()}")
            job_dict = yaml.safe_load(yaml_stream)
            job = BrainSlosherJob(**job_dict)  
            return job
    
    def _run_job_worker(self, job: BrainSlosherJob, job_path: Path):
        """
        Configure mixer and job state for session. Put any errors in queue to be accessed by main thread        
        """
        
        self.mixer.set_mixing_speed(job.motor_speed_rpm)
        self._job = job
        self._step = 0 if not job.resume_state else job.resume_state.step

        try:
            self.log.info("Job starting.")
            with self.job_status_lock:
                self.job_status = BrainSlosherJobStatus(status="running") 
            super()._run_job_worker(job, job_path)
           
            # clear job if finished
            if not job.resume_state:
                self._job = None
                self._step = 0
                self.log.info("Job finished.")
                message = BrainSlosherJobStatus(status="finished")

            else: 
                self.log.info("Job paused.")
                message = BrainSlosherJobStatus(status="paused")

        except Exception as e:
            self.log.error(f"Error running job: {str(e)}.")
            message = BrainSlosherJobStatus(status="failed", message=str(e))
            raise e
        
        finally:
            with self.job_status_lock:
                self.job_status = message 
            self.mixer.stop_mixing()
    
    def get_job_status(self) -> BrainSlosherJobStatus:
        """
        Getter function that returns the job_status attribute
        """

        with self.job_status_lock:
            return self.job_status

    def get_job(self) -> dict | None:
        """
        Convienence method to get current job
        """
        if self._job:
            return self._job.model_dump()

    def save_resume_state(self, job: BrainSlosherJob, resume_step: int, starting_solution: str, **kwargs):
        """
            Save resume state of job. Overwrite since solution is string and startign solution is dict
        """
        job.save_resume_state(resume_step, {starting_solution: self.config.fill_volume_ml*1000}, **kwargs)

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
        if self.rxn_vessel.solution != {solution: self.config.fill_volume_ml * 1000}:
            self.log.info(f"Reaction vessel in incorrect state for wash step. Draining, priming, filling, and purging.")
            self.drain_chamber()
            self.prime_line(solution)
            self.fill_chamber(solution, 
                              self.config.fill_volume_ml)
            self.purge_line()
        
        start_time_s = perf_counter()
        duration_s = duration_min * 60
        self.log.info(f"Washing for {duration_min}")
        while (perf_counter() - start_time_s) < duration_s:
            # Handle pause request if called in a "job" context.
            elapsed_min = (perf_counter() - start_time_s)/60
            self.resume_state_overrides.update(duration_min=duration_min - round(elapsed_min, 3)) # updated outside of pause so overrides always has upto date overrides
            
            if self.job_worker and self.job_worker.is_alive() and self.pause_requested.is_set():
                self.log.warning(f"Aborting after {elapsed_min * 60}[s].")
                return
        self.resume_state_overrides.update(duration_min=0)
        self.drain_chamber()    
        


