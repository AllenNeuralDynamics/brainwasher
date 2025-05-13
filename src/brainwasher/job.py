"""pydantic model of job instance of protocol"""

from pathlib import Path
from pydantic import BaseModel, computed_field, field_serializer, model_serializer, AfterValidator
from datetime import datetime
from typing import Annotated, Optional, Any
import logging

class WashStep(BaseModel):
    # FIXME: this should be retrieved from the function signature.
    # https://github.com/pydantic/pydantic/issues/1391
    mix_speed_rpm: int
    duration_s: float
    solution: dict[str, float]

    @property
    def volume_ul(self):
        """Total solution volume computed from chemical sums.

        Does not need to be represented in pydantic model.
        """
        return sum(self.solution.values())


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


class ResumeState(BaseModel):

    @staticmethod
    def values_in_wash_step(overrides: dict):
        """Ensure keys in the overrides dict exist as WashStep fields."""
        # TODO: ensure that these keys satisfy any WashStep field validators also.
        override_keys = set(overrides.keys())
        wash_step_model_fields = set(WashStep.model_fields)
        if not override_keys.issubset(wash_step_model_fields):
            raise ValueError(f"Override fields must all be valid WashStep fields. overrides: {override_keys}, WashSteps: {wash_step_model_fields}")
        return overrides

    step: int
    overrides: Annotated[Optional[dict[str, Any]], AfterValidator(values_in_wash_step)] = None


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
    resume_state: Optional[ResumeState] = None
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

    def save_resume_state(self, step: int, **overrides: dict):
        self.resume_state = ResumeState(step=step, overrides=overrides)

    def clear_resume_state(self):
        self.resume_state = None

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
            kwargs["exclude"] = set(["resume_state"])
        return super().model_dump(**kwargs)


if __name__ == "__main__":

    my_model = Job(name="test_brian",
                   source_protocol=".",
                   resume_state=ResumeState(step=0, overrides={"duration_s": 123}),
                   protocol=[WashStep(mix_speed_rpm=1000, duration_s=1800, solution={"thf": 1000, "di_water": 4000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800, solution={"dcm": 5000})])

    import pprint
    pprint.pprint(my_model.model_dump())
    print()
    my_model.save_resume_state(2, duration_s=1000)
    pprint.pprint(my_model.model_dump())
    print()
    my_model.clear_resume_state()
    pprint.pprint(my_model.model_dump())
    #print(my_model)
