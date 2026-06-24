from mixology.instrument import Instrument
from mixology.devices.simulated_devices.peristaltic_pump import SimPeristalticPump
from mixology.devices.simulated_devices.selector import SimSelector
from seqflow.seqflow_models import (
    SeqFlowConfig,
    SeqFlowJob,
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
        """
        Convienence method to get current job
        """
        pass

    def set_job(self, job: Union[dict, SeqFlowJob]) -> None:
        """
        Convienence method to set current job

        :param job: dict or SeqFlowJob object to set as current job

        """
        pass

    def pause(self) -> None:
        """Request that the system pause the currently running protocol and
        save the protocol path and current step to the config."""
        pass

    def get_progress(self) -> dict:
        """Get current progress of job as a dict."""
        return {"job_status": self.job_status.status, "message": self.job_status.message}

    def validate_job_against_instrument(self, job: SeqFlowJob):
        """Validate that the job is compatible with the instrument."""
        pass