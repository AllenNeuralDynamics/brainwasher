"""Instrument base class"""
from abc import abstractmethod
from pathlib import Path
from brainwasher.job import Job
from threading import Thread, Event
import logging
from datetime import timedelta
import yaml


class Instrument:

    def __init__(self, ):
        self.log = logging.getLogger(__name__ + "." + self.__class__.__name__)
        self.rxn_vessel = None
        self.job_worker: Thread = None
        self.pause_requested: Event = None

    def run(self, job_path: str):
        """Run the job specified from the specified filepath."""
        if self.job_worker and self.job_worker.is_alive():
            raise ValueError("Cannot run another job while an existing "
                             "job is running.")
        job = self._load_job(job_path)
        self.validate_job_against_instrument(job)
        logging.debug(f"Launching job worker thread.")
        # Run job in a separate thread to lock out flowpath
        # and support pause/resume control.
        self.job_worker = Thread(target=self._run_job_worker,
                                 name="run_job_worker",
                                 args=[job, Path(job_path)],
                                 daemon=True)
        self.job_worker.start()

    @abstractmethod
    def run_step(self, *args, **kwargs):
        """The main function that gets called over and over."""
        raise NotImplementedError("Implement me in the derived class!")

    @abstractmethod
    def validate_job_against_instrument(self, job: Job):
        raise NotImplementedError("Implement me in th derived class!")

    def _load_job(self, job_path: str) -> Job:
        job_path = Path(job_path)
        if not job_path.exists():
            raise FileNotFoundError(f"Job does not exist at location: "
                                    f"{job_path.resolve()}")
        with open(job_path) as yaml_stream:
            self.log.debug(f"Loading job from: {job_path.absolute()}")
            job_dict = yaml.safe_load(yaml_stream)
            logging.debug(f"Validating job from file.")
            job = Job(**job_dict)  # validate
            logging.debug(f"Job is a valid job.")
            return job

    @lock_flowpath
    def _run_job_worker(self, job: Job, job_path: Path):
        """Start or resume a job from job_path"""
        # When starting/resuming, ensure the current rxn vessel solution is
        # either unspecified (assume user filled it with correct starting solution)
        # or matches the job starting solution (user instructed machine to fill
        # it with the correct starting solution).
        if job.resume_state:
            start_step = job.resume_state.step
            start_step_overrides = job.resume_state.overrides
            starting_or_resuming_msg = "Resuming"
            if not self.rxn_vessel.solution: # assume unspecified.
                self.rxn_vessel.add_solution(**job.resume_state.starting_solution)
            if self.rxn_vessel.solution != job.resume_state.starting_solution:
                raise ValueError("When resuming, reaction vessel starting "
                                 "solution does not match the correct resume "
                                 "state starting solution.")
            job.clear_resume_state()
            job.record_resume()
        else:
            start_step = 0
            start_step_overrides = None
            starting_or_resuming_msg = "Starting"
            if not self.rxn_vessel.solution: # assume unspecified.
                self.rxn_vessel.add_solution(**job.starting_solution)
            if  self.rxn_vessel.solution != job.starting_solution:
                raise ValueError("When starting, reaction vessel starting "
                                 "solution does not match the correct resume "
                                 "state starting solution.")
            job.record_start()
        log_msg = f"{starting_or_resuming_msg} job: '{job.name}'"
        if start_step > 0:
            log_msg += f" at step {start_step+1}."  # Steps in logs are 1-indexed.
        else:
            log_msg += ". "
        log_msg += f"Job should take {timedelta(seconds=job.get_duration_s(start_step))}."
        self.log.info(log_msg)
        # Execute the protocol.
        for index, step in enumerate(job.protocol[start_step:], start=start_step):
            resume_step = index # Save resume step in case of unhandled exception.
            try:
                # Apply overrides (recursive) on the first (ie resume) step only.
                if index == start_step and start_step_overrides:
                    step = step.model_copy(update=start_step_overrides)
                    self.log.info(f"Applying overrides to starting step: "
                                  f"{start_step_overrides}.")
                # Convert step parameters to valid function parameters.
                kwargs = step.model_dump(exclude='solution')  # omit **solution
                kwargs.update(step.solution)  # splat **solution
                self.log.info(f"Conducting step: "
                              f"{index + 1}/{len(job.protocol)} with "
                              f"{step.solution}")
                # Run step.
                self.run_step(**kwargs)
                # Handle pause state.
                # Save current step if not completed (overrides present) or
                # next step if the current step completed.
                resume_step = index if self.resume_state_overrides else index + 1
                if self.pause_requested.is_set():
                    # Note: steps are 1-indexed when referenced in logs.
                    self.log.warning(f"Pausing system at step {resume_step+1}.")
                    job.record_pause()
                    self.pause_requested.clear()
                    self.log.info(f"System paused.")
                    return  # Will execute finally block first.
            finally:
                # Always save the current step in case of an unhandled exception
                # or power failure.
                job.save_resume_state(resume_step, step.solution,
                                      **self.resume_state_overrides)
                self.resume_state_overrides = {}
                with open(job_path, "w") as job_file:
                    yaml.dump(job.model_dump(exclude_none=True), job_file)
                self.log.debug(f"Job progress saved to: {job_path}")
        job.clear_resume_state()
        job.record_finish()
        with open(job_path, "w") as job_file:
            yaml.dump(job.model_dump(exclude_none=True), job_file)
        self.log.info(f"Finished job: {job.name} from {job_path}")

    def pause(self):
        """Request that the system pause the currently running protocol and
        save the protocol path and current step to the config."""
        if self.job_worker is None or not self.job_worker.is_alive():
            self.log.error("Ignoring pause request. System is not running a protocol.")
            return
        self.log.info("Requesting system pause.")
        self.pause_requested.set()
