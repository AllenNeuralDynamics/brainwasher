"""pydantic model of job instance of protocol"""

from pathlib import Path
from pydantic import BaseModel, computed_field, field_serializer, model_serializer, Field

from datetime import datetime
from functools import cached_property
from typing import, Optional, Any, Literal, Union
import logging


class SourceProtocol(BaseModel):
    """Path denoting the job or protocol that this job was generated from."""
    path: Optional[Path] = None
    accessed: Optional[datetime] = None

    @field_serializer("path")
    def resolve_path(self, path: Path):
        """Coerce path output to absolute path string for serialization."""
        return str(Path(path).resolve()) if path else None


class Step(BaseModel):
    pass


class Event(BaseModel):
    timestamp: datetime
    type: str


class StartEvent(Event):
    type: Literal["start"] = "start" # TODO: how to make this fixed.


class FinishEvent(Event):
    type: Literal["end"] = "end"  # TODO: how to make this fixed


class PauseEvent(Event):
    type: Literal["pause"] = "pause"  # TODO: how to make this fixed


class ResumeEvent(Event):
    type: Literal["resume"] = "resume"  # TODO: how to make this fixed


class RestartEvent(Event):
    pass

class ResumeState(BaseModel):
    pass



class History(BaseModel):
    events: Optional[list[Event]] = list()


class Job(BaseModel):
    """Local job, derived from a protocol, to be run on an instrument."""
    name: str
    starting_solution: dict[str, float]
    source_protocol: Optional[SourceProtocol] = SourceProtocol()
    protocol: Optional[list[Step]] = list()
    resume_state: Optional[ResumeState] = None
    history: Optional[History] = History()

    def get_duration_s(self, start_step: int = 0):
        """Total job duration in seconds starting from the specified step."""
        return sum([step.duration_s for step in self.protocol[start_step:]])

    @cached_property
    def chemicals(self) -> set[str]:
        """Extract set of chemicals from all solutions across all steps"""
        step_components = set([chemical for step in self.protocol
                          for chemical in step.components])
        # Include starting solution chemicals.
        return step_components | set(self.starting_solution.keys())

    @computed_field
    @cached_property
    def stock_chemical_volumes_ul(self) -> dict[str, float]:
        """Dict of total chemical volumes (in microliters) needed across all
        steps."""
        stock_chemicals = {}
        for step in self.protocol:
            for chemical_name, volume_ul in step.solution.items():
                curr_volume_ul = stock_chemicals.get(chemical_name, 0)
                stock_chemicals[chemical_name] = curr_volume_ul + volume_ul
        return stock_chemicals

    def record_start(self, timestamp: datetime = None):
        """Record a start event to the job's history."""
        timestamp = timestamp if timestamp else datetime.now()
        self.history.events.append(StartEvent(timestamp=timestamp))

    def record_finish(self, timestamp: datetime = None):
        """Record a finish event to the job's history."""
        timestamp = timestamp if timestamp else datetime.now()
        self.history.events.append(FinishEvent(timestamp=timestamp))

    def record_pause(self, timestamp: datetime = None):
        """Record a finish event to the job's history."""
        timestamp = timestamp if timestamp else datetime.now()
        self.history.events.append(PauseEvent(timestamp=timestamp))

    def record_resume(self, timestamp: datetime = None):
        """Record a finish event to the job's history."""
        timestamp = timestamp if timestamp else datetime.now()
        self.history.events.append(ResumeEvent(timestamp=timestamp))

    def save_resume_state(self, step: int, starting_solution: dict[str, float],
                          **overrides: dict):
        self.resume_state = ResumeState(step=step,
                                        starting_solution=starting_solution,
                                        overrides=overrides)

    def clear_resume_state(self):
        self.resume_state = None

    def purge_history(self):
        self.history = History()

    def set_source_protocol(self, path: Path, access_timestamp: datetime = None):
        access_timestamp = access_timestamp if access_timestamp else datetime.now()
        self.source_protocol = SourceProtocol(path=path,
                                              accessed=access_timestamp)

    def model_dump(self, **kwargs):
        """Override model dump to always exclude empty resume_state since this field
        will only be added by software running the job.
        """
        if self.resume_state:
            return super().model_dump(**kwargs)
        # Omit resume state if it is empty.
        default_excludes = kwargs.get("exclude", None)
        if default_excludes:
            default_excludes.add("resume_state")
        else:
            kwargs["exclude"] = {"resume_state"}
        return super().model_dump(**kwargs)
