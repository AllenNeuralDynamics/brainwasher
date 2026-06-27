# seqflow.py

from mixology.instrument import Instrument
from mixology.devices.simulated_devices.peristaltic_pump import SimPeristalticPump
from mixology.devices.simulated_devices.selector import SimSelector
from seqflow.seqflow_models import (
    SeqFlowConfig,
    SeqFlowJob,
    SeqFlowResumeState,
)
from mixology.devices.vessels import SlideContainer
from functools import wraps
from datetime import datetime
from typing import Union, Optional
from pathlib import Path
import time
import yaml


class SeqFlow(Instrument):
    """

    Class for controlling 0365 - AIND Hydrogel Imaging Prep Automation

    """

    def __init__(
        self,
        config: SeqFlowConfig,
        pump: SimPeristalticPump,
        selector: SimSelector,
        slide_container: SlideContainer,
    ):
        super().__init__()
        self.config = config
        self.pump = pump
        self.selector = selector

        # Just two different nametags pointing to the exact same physical container in memory
        # so the base Instrument class stays happy
        self.slide_container = slide_container
        self.rxn_vessel = self.slide_container

        # current job to run
        self._job: Optional[SeqFlowJob] = None
        # TODO: Add resume state tracking to SeqFlowJob. For now only remaining time is tracked in the instrument, but this should be saved to the job for resuming later.
        self.resume_state_overrides = {}

    def _load_job(self, job_path: str | Path) -> SeqFlowJob:
        """
        Override base class method to load a SeqFlowJob from a yaml file.
        """
        job_path = Path(job_path)
        if not job_path.exists():
            raise FileNotFoundError(
                f"Job does not exist at location: {job_path.resolve()}"
            )
        with open(job_path) as yaml_stream:
            self.log.debug(f"Loading job from: {job_path.absolute()}")
            job_dict = yaml.safe_load(yaml_stream)
            job = SeqFlowJob(**job_dict)
            return job
    
    def start_run(self, job: SeqFlowJob):
        """
        Reset SeqFlow and start run

        :param job: job to run

        """
        # validate and save job so instrument can run
        valid_job = SeqFlowJob(**job)

        # create path for job
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        job_path = Path(self.config.save_folder) / f"{valid_job.name}_{timestamp}.yaml"
        job_path.parent.mkdir(parents=True, exist_ok=True)

        valid_job.source_protocol.path = job_path
        with open(Path(job_path), "w") as f:
            yaml.dump(valid_job.model_dump(), f)
        self.run(job_path)
        return {"message": "Starting run!"}

    def get_job(self) -> dict | None:
        """Convenience method to get current job"""
        if self._job:
            return self._job.model_dump()

    def set_job(self, job: Union[dict, SeqFlowJob]) -> None:
        """Convenience method to set current job"""
        # TODO: Add lock and set_job is not allowed while a job is running
        if isinstance(job, dict):
            self._job = SeqFlowJob(**job)
        else:
            self._job = job

    def pause(self) -> None:
        """Request that the system pause the currently running protocol and
        save the protocol path and current step to the config."""
        super().pause()

    def get_progress(self) -> dict:
        """Get current progress of job as a dict."""
        # TODO get more details
        status = "idle"
        if self.job_worker and self.job_worker.is_alive():
            status = "paused" if self.pause_requested.is_set() else "running"
        job_name = self._job.name if self._job else "None"
        return {"job_status": status, "job_name": job_name}

    def validate_job_against_instrument(self, job: SeqFlowJob):
        """Validate that the job is compatible with the instrument."""
        # TODO
        pass

    def run_step(
            self, 
            sequence_name: str,
            sequence_index: int,
            device: str,
            solution: dict = None,
            flow_rate_mlpm: float = None,
            duration_m: float = None,
            temp_c: float = None
        ):
        duration_s = 0.0

        # TODO Change to actual hardware call after adding drivers
        # Calculate Time for Fluidics (Pump)
        if device == "pump" and flow_rate_mlpm and solution:
            total_vol = sum(solution.values())
            duration_s = (total_vol / flow_rate_mlpm) * 60.0

            # --- Simulated Hardware Calls Go Here ---
            self.log.info(f"Simulating Pump: {total_vol}mL at {flow_rate_mlpm}mL/min. Est time: {duration_s:.1f}s")

        # Calculate Time for Idle/Heat
        elif device in ["heat_device", "wait"] and duration_m:
            duration_s = duration_m * 60.0

            # --- Simulated Hardware Calls Go Here ---
            self.log.info(f"Simulating Wait/Heat: {duration_m} minutes. Est time: {duration_s:.1f}s")

        # Simulated Execution Loop (Blocks thread, checks for pause)
        if duration_s > 0:
            start_time = time.perf_counter()
    
            while (time.perf_counter() - start_time) < duration_s:

                # Catch pause request instantly
                if self.pause_requested.is_set():
                    elapsed_s = time.perf_counter() - start_time
                    remaining_m = (duration_s - elapsed_s) / 60.0

                    self.log.warning(f"Paused mid-{device}. {remaining_m:.2f} minutes remaining.")

                    # Override the remaining time so the resume step picks up the exact remainder
                    self.resume_state_overrides = {"duration_m": remaining_m}
                    return 

                # Short sleep to prevent CPU pegging during the while loop
                time.sleep(0.05)

    def _run_job_worker(self, job: SeqFlowJob, job_path: Path):
        # Sync the newly loaded disk object back to our main memory!
        self._job = job
        
        # Now hand it off to the base Instrument class
        super()._run_job_worker(job, job_path)

    def resume_run(self):
        """
        Resume job
        """
        job = self._job
        if not job or not job.resume_state:
            self.log.error("No job to resume")
            return

        if not job.source_protocol.path:
            self.log.error("No source protocol path to save to.")
            return

        self.run(job.source_protocol.path)