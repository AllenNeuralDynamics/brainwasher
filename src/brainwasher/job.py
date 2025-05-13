"""pydantic model of job instance of protocol"""

from pathlib import Path
from pydantic import BaseModel, computed_field, field_serializer
from datetime import datetime
from typing import Optional
import logging

class WashStep(BaseModel):
    # FIXME: this should be retrieved from the function signature.
    # https://github.com/pydantic/pydantic/issues/1391
    mix_speed_rpm: int
    duration_s: float
    solution: dict[str, float]

class Event(BaseModel):
    timestamp: datetime


class StartEvent(Event):
    pass


class FinishEvent(Event):
    pass


class PauseEvent(Event):
    pass


class ResumeEvent(Event):
    pass


class RestartEvent(Event):
    pass


class History(BaseModel):
    starting_solution: Optional[dict[str, int]] = None
    execution_history: Optional[list[Event]] = None


class Job(BaseModel):
    """Local job, derived from a protocol, to be run on an instrument."""
    name: str
    source_protocol: Path
    start_timestamp: Optional[datetime] = None
    stop_timestamp: Optional[datetime] = None
    protocol: list[WashStep]
    resume_state: Optional[dict] = None
    history: Optional[History] = None

    @computed_field
    @property
    def chemicals(self) -> set[str]:
        """Extract set of chemicals from all solutions across all steps"""
        return set([chemical for step in self.protocol for chemical in step.solution.keys()])

    @field_serializer("source_protocol")
    def resolve_path(self, source_protocol: Path):
        """Coerce path output to absolute path string for serialization."""
        return str(Path(source_protocol).resolve())


if __name__ == "__main__":

    my_model = Job(name="test",
                   source_protocol=".",
                   protocol=[WashStep(mix_speed_rpm=1000, duration_s=1800, solution={"thf": 1000, "di_water": 4000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800, solution={"dcm": 5000})])

    import pprint
    pprint.pprint(my_model.model_dump())
    #print(my_model)
