from mixology.instrument import Instrument
from mixology.devices.simulated_devices.syringe_pump import SimSyringePump
from mixology.devices.simulated_devices.selector import SimSelector
from seqflow.seqflow_models import (
    SeqFlowConfig,
    SeqFlowJob,
    SeqFlowJobStatus,
)
from mixology.devices.vessels import ReactionVessel, WasteVessel
from threading import RLock, current_thread, Lock, Thread
from functools import wraps
from datetime import datetime, timedelta
from typing import Literal, Union, Optional
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
        pump: SimSyringePump,
        selector: SimSelector,
        job: Optional[SeqFlowJob] = None,
    ):
        super().__init__()
        self.config = config
        self.pump = pump
        self.selector = selector
        # current job to run
        self._job: SeqFlowJob = job
        self.job_status: SeqFlowJobStatus = SeqFlowJobStatus(status="idle")

    
    def start_run(self):
        """
        Reset SeqFlow and start run

        :param job: job to run

        """
        return {"message": "Starting run!"}


    def get_progress(self) -> dict:
        """Get current progress of job as a dict."""
        return {"job_status": self.job_status.status, "message": self.job_status.message}
