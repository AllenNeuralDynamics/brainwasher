"""pydantic model of job instance of protocol"""

from pathlib import Path
from pydantic import BaseModel, computed_field, field_serializer, model_serializer, AfterValidator, Field
from pydantic import ValidationError
from datetime import datetime
from typing import Annotated, Optional, Any, Literal, Union
import logging


class SourceProtocol(BaseModel):
    """Path denoting the job or protocol that this job was generated from."""
    path: Optional[Path] = None
    accessed: Optional[datetime] = None

    @field_serializer("path")
    def resolve_path(self, path: Path):
        """Coerce path output to absolute path string for serialization."""
        return str(Path(path).resolve()) if path else None


class WashStep(BaseModel):
    # FIXME: this should be retrieved from the function signature.
    # https://github.com/pydantic/pydantic/issues/1391
    # Warning: names & default values must match those in brainwasher.run_wash_step
    intermittent_mixing_on_time_s: Optional[float] = None
    intermittent_mixing_off_time_s: Optional[float] = None
    mix_speed_rpm: Optional[float] = 0
    duration_s: Optional[float] = 0
    solution: dict[str, float]

    @property
    def solution_volume_ul(self):
        """Total solution volume computed from chemical sums.

        Does not need to be represented in pydantic model.
        """
        return sum(self.solution.values())


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

    @staticmethod
    def values_in_wash_step(overrides: dict):
        """Ensure keys in the overrides dict exist as WashStep fields.

        .. note::
           WashStep `solution` field cannot be overritten.

        """
        override_keys = set(overrides.keys())
        valid_wash_step_model_fields = set(WashStep.model_fields) - {"solution"}
        if not override_keys.issubset(valid_wash_step_model_fields):
            raise ValueError(f"Override fields must all be valid WashStep "
                             f"fields and cannot include the solution field. "
                             f"overrides: {override_keys}, "
                             f"WashSteps: {valid_wash_step_model_fields}")
        # Validate override values against WashStep value constraints.
        try:  # Lazy way: try making a valid WashStep.
            wash_step = WashStep(**overrides, solution={})
        except ValidationError as e:
            extra_msg = "Error validating ResumeState overrides against WashStep values."
            raise ValueError(extra_msg) from e
            raise
        return overrides

    step: int
    # overrides are a subset of WashStep fields whose values will override
    # those in a WashStep.
    overrides: Annotated[Optional[dict[str, Any]], AfterValidator(values_in_wash_step)] = None


class History(BaseModel):
    starting_solution: Optional[dict[str, int]] = None
    events: Optional[list[Event]] = list()


class Job(BaseModel):
    """Local job, derived from a protocol, to be run on an instrument."""
    name: str
    source_protocol: Optional[SourceProtocol] = SourceProtocol()
    protocol: Optional[list[WashStep]] = list()
    resume_state: Optional[ResumeState] = None
    history: Optional[History] = History()

    @computed_field
    @property
    def chemicals(self) -> set[str]:
        """Extract set of chemicals from all solutions across all steps"""
        return set([chemical for step in self.protocol for chemical in step.solution.keys()])

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

    def save_resume_state(self, step: int, **overrides: dict):
        self.resume_state = ResumeState(step=step, overrides=overrides)

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


if __name__ == "__main__":

    my_model = Job(name="test_brian",
                   #source_protocol=".",
                   #resume_state=ResumeState(step=0, overrides={"duration_s": 123}),
                   protocol=[WashStep(mix_speed_rpm=1000, duration_s=1800, solution={"thf": 1000, "di_water": 4000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800, solution={"dcm": 5000})])

    import pprint
    pprint.pprint(my_model.model_dump())
    print()
    print("Saving resume state!")
    my_model.save_resume_state(2, duration_s=1000)
    pprint.pprint(my_model.model_dump())
    print()
    print("Clearing resume state!")
    my_model.clear_resume_state()
    pprint.pprint(my_model.model_dump())
    #print(my_model)
