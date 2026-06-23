from mixology.instrument import Instrument
from mixology.devices.simulated_devices.peristaltic_pump import SimPeristalticPump
from mixology.devices.simulated_devices.selector import SimSelector
from seqflow.seqflow_models import (
    SeqFlowConfig,
    SeqFlowJob,
    SeqFlowJobStatus,
)
from mixology.devices.vessels import SlideContainer
from functools import wraps
from datetime import datetime
from typing import Union, Optional
from pathlib import Path
from time import perf_counter
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
        self.job_status: SeqFlowJobStatus = SeqFlowJobStatus(status="idle")

    
    def get_job(self) -> dict | None:
        """
        Convienence method to get current job
        """
        if self._job:
            return self._job.model_dump()
    
    def set_job(self, job: Union[dict, SeqFlowJob]) -> None:
        """
        Convienence method to set current job

        :param job: dict or SeqFlowJob object to set as current job

        """
        if self.job_status.status == "running":
            self.log.warning("Cannot set job when instrument is running. Please pause.")
            return

        self._job = SeqFlowJob(**job) if type(job) == dict else job
        status = "paused" if self._job.resume_state else "idle"
        with self.job_status_lock:
            self.log.info(f"Job set and setting to {status}")
            self.job_status = SeqFlowJobStatus(status=status)

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


    def get_progress(self) -> dict:
        """Get current progress of job as a dict."""
        return {"job_status": self.job_status.status, "message": self.job_status.message}


    def validate_job_against_instrument(self, job: SeqFlowJob):
        """Validate that the job is compatible with the instrument."""
        pass