"""pydantic model of brainwasher job."""

from pydantic import BaseModel, Field, field_validator, EmailStr, ValidationError, AfterValidator
from brainwasher.job import Job
from typing import Optional, Annotated, Any, Literal
from pathlib import Path

class BrainSlosherJobStatusMessage(BaseModel):
    """Model of messages used to convey if brainslosher job failed or finished"""
    status: Literal["failed", "finished", "running", "paused", "idle"] = Field(..., description="Indicated if job is finished or errored out.")
    message: Optional[str] = Field(default=None, description="Optional message of additional info.")

class BrainSlosherResumeState(BaseModel):

    @staticmethod
    def values_in_cycle(overrides: dict):
        """Ensure keys in the overrides dict exist as Cycle fields.

        .. note::
           WashStep `solution` field cannot be overwritten.

        """
        override_keys = set(overrides.keys())
        valid_cycle_model_fields = set(Cycle.model_fields) - {"solution"}
        if not override_keys.issubset(valid_cycle_model_fields):
            raise ValueError(f"Override fields must all be valid Cycle "
                             f"fields and cannot include the solution field. "
                             f"overrides: {override_keys}, "
                             f"Cycle: {valid_cycle_model_fields}")
        # Validate override values against WashStep value constraints.
        try:  # Lazy way: try making a valid Step.
            cylce = Cycle(**overrides, solution="")
        except ValidationError as e:
            extra_msg = "Error validating ResumeState overrides against Cycle values."
            raise ValueError(extra_msg) from e
        return overrides

    step: int
    starting_solution: dict[str, float]
    overrides: Annotated[Optional[dict[str, Any]], AfterValidator(values_in_cycle)] = None

class Cycle(BaseModel):
    solution: str = Field(..., description="Solution to use in all washes of cycle.")
    duration_min: float = Field(..., description="Duration in minutes of all washes in cycle.")
    washes: int = Field(..., description="Number of washes performed in cycle.")

class BrainSlosherJob(Job):
    protocol: list[Cycle] = list()
    motor_speed_rpm: float = Field(..., description="Speed of motor in rpms. Set to 0 to disable motor.")
    resume_state: Optional[BrainSlosherResumeState] = None

    def get_duration_s(self, start_step: int = 0):
        """Total job duration in seconds starting from the specified step."""
        return sum([step.duration_min * step.washes * 60 for step in self.protocol[start_step:]])

    def save_resume_state(self, step: int, starting_solution: dict[str, float],
                          **overrides: dict):
        self.resume_state = BrainSlosherResumeState(step=step,
                                                    starting_solution=starting_solution,
                                                    overrides=overrides)

"""pydantic model of brainwasher config."""

class BrainSlosherConfig(BaseModel):
    save_folder: Path = Field(default="../../brain_slosher_jobs/")
    selector_port_map: dict[str, int]
    max_syringe_volume_ml: float = Field(default=4.5, description="Maximum fill volume of the syringe to prevent chatter when operating.")
    prime_volume_ml: float = Field(default=11, description="Volume to prime lines.")
    purge_volume_ml: float = Field(default=4.5, description="Volume to purge drain line.")
    drain_volume_buffer_ml: float = Field(..., description="Buffer to add to draining volume to ensure chamber is completly empty.")
    fill_volume_ml: float = Field(..., description="Volume to fill chamber completly.")
    user_email: Optional[EmailStr] = Field(default=None, description="Optional email to send errors to.")    # validates email with email-validator package

    @field_validator("selector_port_map")
    def check_required_keys(cls, v: dict[str, int]):
        """Check that air, chamber, and waste are in map"""

        if "air" not in v:
            raise ValueError("selector_port_map must contain an 'air' key for purging line.")
        elif "chamber" not in v:
            raise ValueError("selector_port_map must contain a 'chamber' key.")
        elif "waste" not in v:
            raise ValueError("selector_port_map must contain a 'waste' key.")
        return v
    
    @field_validator("selector_port_map")
    def check_duplicated_ports(cls, v: dict[str, int]):
        """Check that no ports are mapped twice"""
        ports = set(v.values())
        if len(ports) != len(list(v.values())):
            raise ValueError("Duplicate port references in selector_port_map.")
        return v