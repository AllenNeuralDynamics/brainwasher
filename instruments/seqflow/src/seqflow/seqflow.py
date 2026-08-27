# seqflow.py

from mixology.devices.selector.selector import SerialSelector
from mixology.devices.pump.peristaltic_pump import SerialPeristalticPumpDevice
from mixology.devices.selector.mux import CascadedMux
from mixology.instrument import Instrument
from mixology.devices.simulated_devices.peristaltic_pump import SimPeristalticPump
from mixology.devices.simulated_devices.selector import SimSerialSelector
from seqflow.seqflow_models import SeqFlowJob, SeqFlowJobStatus
from seqflow.seqflow_config_model import SeqFlowConfig
from threading import Lock
from mixology.devices.vessels import SlideContainer
from datetime import datetime
from typing import Union, Optional, Any, Literal
from pathlib import Path
import time
import yaml


class SeqFlow(Instrument):
    """

    Class for controlling BARseq SeqFlow instrument.

    """

    def __init__(
        self,
        config: SeqFlowConfig,
        pump: SimPeristalticPump | SerialPeristalticPumpDevice,
        selector: SimSerialSelector | CascadedMux | SerialSelector,
        rxn_vessel: SlideContainer,
    ):
        super().__init__()
        self.config = config
        self.pump = pump
        self.selector = selector
        self.rxn_vessel = rxn_vessel

        # start devices
        self.pump.connect()
        self.selector.connect()

        # attribute to track events that occur in job_worker
        self.job_status_lock = Lock()
        self.job_status: SeqFlowJobStatus = SeqFlowJobStatus(status="idle")

        # current job to run
        self._job: Optional[SeqFlowJob] = None
        # TODO: Add resume state tracking to SeqFlowJob. For now only remaining time is tracked in the instrument, but this should be saved to the job for resuming later.
        self.resume_state_overrides: dict[str, Any] = {}

    def _load_job(self, job_path: str) -> SeqFlowJob:
        return super()._load_job(job_path, job_class=SeqFlowJob)

    def restart_run(self, job: SeqFlowJob):
        """
        Reset SeqFlow and start run

        :param job: job to run

        """
        # reset SeqFlow
        self.clear_job()
        self.start_run(job)

    def clear_job(self) -> None:
        """
        Clear job and update status
        """
        if self.job_status.status == "running":
            self.log.warning(
                "Cannot reset state when instrument is running. Please pause."
            )
            return
        self._job = None
        with self.job_status_lock:
            self.job_status = SeqFlowJobStatus(status="idle")

    def start_run(self, job: SeqFlowJob):
        """
        Reset SeqFlow and start run

        :param job: job to run

        """
        # Clear the vessel state from any previous state. Vessel routes excess liquid to waste.
        self.rxn_vessel.purge_solution()

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

        return None

    def set_job(self, job: Union[dict, SeqFlowJob]) -> None:
        """Convenience method to set current job"""
        if self.job_status.status == "running":
            self.log.warning("Cannot set job when instrument is running. Please pause.")
            return

        self._job = SeqFlowJob(**job) if isinstance(job, dict) else job
        status: Literal["paused", "idle"] = (
            "paused" if self._job.resume_state else "idle"
        )
        with self.job_status_lock:
            self.log.info(f"Job set and setting to {status}")
            self.job_status = SeqFlowJobStatus(status=status)

    def clear_status(self) -> None:
        """clear status of failed if possible."""

        if self.job_status.status == "running":
            self.log.warning("Cannot clear state while running.")
            return

        status: Literal["paused", "idle"] = (
            "paused" if self._job and self._job.resume_state else "idle"
        )
        with self.job_status_lock:
            self.log.info(
                f"Clearing {self.job_status.status} job status and setting to {status}"
            )
            self.job_status = SeqFlowJobStatus(status=status)

    def pause(self) -> None:
        """Request that the system pause the currently running protocol and
        save the protocol path and current step to the config."""
        super().pause()

    def get_progress(self) -> dict:
        """Get current progress of job as a dict."""
        # TODO get more details
        if not self._job:
            return {"status": "idle"}
        current_status = self.get_job_status()
        return current_status.model_dump()

    def get_job_status(self) -> SeqFlowJobStatus:
        """
        Getter function that returns the job_status attribute
        """

        with self.job_status_lock:
            return self.job_status

    def validate_job_against_instrument(self, job: SeqFlowJob):
        """Validate that the job is compatible with the instrument."""
        for i, step in enumerate(job.protocol):
            total_vol = sum(step.solution.values()) if step.solution else 0.0

            # Prevent undefined wait states (0 Volume without Duration)
            if total_vol == 0.0 and step.duration_s is None:
                raise ValueError(
                    f"Validation failed at step {i + 1}: "
                    f"Steps with 0.0mL volume (like heat/wait steps) must provide an explicit 'duration_s'."
                )

            # Verify hardware capabilities (Valid Port Mapping)
            if total_vol > 0:
                solution_name = next(iter(step.solution))
                if solution_name not in self.selector.port_map:
                    raise ValueError(
                        f"Validation failed at step {i + 1}: "
                        f"Solution '{solution_name}' is not in the instrument. "
                        f"Available ports: {list(self.selector.port_map.keys())}"
                    )

    def run_step(
        self,
        solution: Optional[dict] = None,
        duration_s: Optional[float] = None,
        temp_c: Optional[float] = None,
        flow_rate_mlpm: float = 0.0,
    ):
        """
        Executes a single step in the sequence protocol, acting as either a dispense 
        solution or a wait step depending on the inputs.
        
        This method handles purging the reaction vessel (free flow slides), setting the 
        pump flow rate, selecting the correct port, and dispensing solutions. It also 
        supports pausing mid-step, saving the remaining time and volume to allow for a 
        clean resume.

        How duration is determined:
        1. Dispense Steps: If the solution is found in the selector's port map (meaning 
           it is a chemical solution), the dispense time is automatically calculated 
           based on the requested volume and flow rate (overriding any passed `duration_s`).
        2. Wait/Heat Steps: If the solution is NOT in the port map (such as an incubation 
           or a label like 'heat_wait'), the method acts as a timer, pausing execution 
           for the exact number of seconds provided in `duration_s`.

        Args:
            solution (Optional[dict]): A single-item dictionary mapping the solution 
                name to its target volume in mL (e.g., {'pbst': 0.1}). For heat or 
                incubation steps, the volume is set to 0.0 (e.g., {'heat_wait': 0.0}). 
            duration_s (Optional[float]): The explicit wait time in seconds for heat or 
                incubation steps. Ignored and recalculated if the step is an active 
                dispense step.
            temp_c (Optional[float]): The target temperature in degrees Celsius for 
                this step.
            flow_rate_mlpm (float): The pump flow rate in milliliters per minute 
                (mL/min). Defaults to 0.0.

        Raises:
            ValueError: If `self._job` is None (no job has been loaded).
        """
        if self._job is None:
            raise ValueError("No job loaded. Please load a job before running a step.")

        sol_name, vol = next(iter(solution.items())) if solution else (None, 0.0)

        self.rxn_vessel.purge_solution()
        self.pump.set_flow_rate(flow_rate_mlpm)
        if sol_name in self.selector.port_map:
            self.selector.move_to_position(sol_name)
            duration_s = self.pump.get_dispense_duration_s(vol)
            self.log.debug(f"dispensing volume: {vol:.2f} mL over {duration_s:.2f} seconds.")
            self.pump.start()
        self.rxn_vessel.add_solution(**(solution or {}))

        if duration_s is not None and duration_s > 0:
            start_time = time.perf_counter()
            while (time.perf_counter() - start_time) < duration_s:
                if self.pause_requested.is_set():
                    sol_info = f" {solution}" if solution else ""
                    self.log.warning(f"Paused mid-{sol_info}.")
                    elapsed_s = time.perf_counter() - start_time
                    remaining_s = duration_s - elapsed_s
                    remaining_vol = self.pump.get_dispense_volume_ml(remaining_s)
                    override_solution = {sol_name: remaining_vol} if sol_name is not None else solution
                    self.resume_state_overrides.update(
                        duration_s=remaining_s,
                        solution=override_solution
                    )
                    return

        if sol_name in self.selector.port_map:
            self.pump.stop()

    def _run_job_worker(self, job: SeqFlowJob, job_path: Path):
        # Sync the newly loaded disk object back to our main memory!
        self._job = job

        try:
            with self.job_status_lock:
                self.job_status = SeqFlowJobStatus(status="running")
            # Now hand it off to the base Instrument class
            super()._run_job_worker(job, job_path)

            # clear job if finished
            if not job.resume_state:
                self._job = None
                self.log.info("Job finished.")
                message = SeqFlowJobStatus(status="finished")

            else:
                self.log.info("Job paused.")
                message = SeqFlowJobStatus(status="paused")

        except Exception as e:
            self.log.error(f"Error running job: {str(e)}.")
            message = SeqFlowJobStatus(status="failed", message=str(e))
            raise e

        finally:
            with self.job_status_lock:
                self.job_status = message
            self.pump.stop()

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
