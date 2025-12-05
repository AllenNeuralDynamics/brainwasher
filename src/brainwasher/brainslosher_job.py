"""pydantic model of brainwasher job."""

from pydantic import BaseModel
from typing import Optional
from brainwasher.job import Job


class Cycle(BaseModel):
    pass # TODO: implement me


class BrainSlosherJob(Job):
    protocol: Optional[list[Cycle]] = list()