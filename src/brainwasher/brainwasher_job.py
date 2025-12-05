"""pydantic model of brainwasher job."""

from pydantic import BaseModel, AfterValidator
from typing import Optional, Annotated, Any
from brainwasher.job import Job
from pydantic import ValidationError


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
    def components(self):
        """names of chemical components used in this step."""
        return set(self.solution.keys())

    @property
    def solution_volume_ul(self):
        """Total solution volume computed from chemical sums.

        Does not need to be represented in pydantic model.
        """
        return sum(self.solution.values())


class BrainwasherResumeState(BaseModel):

    @staticmethod
    def values_in_wash_step(overrides: dict):
        """Ensure keys in the overrides dict exist as WashStep fields.

        .. note::
           WashStep `solution` field cannot be overwritten.

        """
        override_keys = set(overrides.keys())
        valid_wash_step_model_fields = set(WashStep.model_fields) - {"solution"}
        if not override_keys.issubset(valid_wash_step_model_fields):
            raise ValueError(f"Override fields must all be valid WashStep "
                             f"fields and cannot include the solution field. "
                             f"overrides: {override_keys}, "
                             f"WashSteps: {valid_wash_step_model_fields}")
        # Validate override values against WashStep value constraints.
        try:  # Lazy way: try making a valid Step.
            wash_step = WashStep(**overrides, solution={})
        except ValidationError as e:
            extra_msg = "Error validating ResumeState overrides against WashStep values."
            raise ValueError(extra_msg) from e
            raise
        return overrides

    step: int
    starting_solution: dict[str, float]  # Required since we need to know
                                         # How to handle waste.
    # overrides are a subset of WashStep fields whose values will override
    # those in a WashStep.
    overrides: Annotated[Optional[dict[str, Any]], AfterValidator(values_in_wash_step)] = None



class BrainwasherJob(Job):
    protocol: Optional[list[WashStep]] = list()
    resume_state: Optional[BrainwasherResumeState] = None
