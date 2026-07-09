# seqflow_models.py
"""pydantic model of seqflow job."""

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    AfterValidator,
)
from mixology.job import Job
from typing import Optional, Annotated, Any, Literal


DeviceType = Literal["pump", "heat_device", "wait", "stopper"]


class SeqFlowStep(BaseModel):
    """Model representing a single action within a sequence."""
    # --- STEP PARAMETERS ---
    duration_s: Optional[float] = Field(default=None, description="Time in seconds for each step.")
    temp_c: Optional[float] = Field(default=None, description="Temperature in Celsius for the heat wait step.")
    solution: dict[str, float] = Field(default_factory=dict, description="solution name and volume (mL) to fill into slides.")
    flow_rate_mlpm: Optional[float] = Field(default=None, description="Step-specific flow rate override in mL/min.")

    # TODO Validation! 

class SeqFlowJobStatus(BaseModel):
    """Model of messages used to convey state of seqflow job"""
    status: Literal["failed", "finished", "running", "paused", "idle"] = Field(
        ..., description="Indicated if status of job."
    )
    message: Optional[str] = Field(
        default=None, description="Optional message of additional info."
    )


class SeqFlowResumeState(BaseModel):
    """Resume state tracking for SeqFlow."""
    
    @staticmethod
    def values_in_seqflow_step(overrides: dict):
        """Ensure keys in the overrides dict exist as SeqFlowStep fields."""
        if not overrides:
            return overrides

        override_keys = set(overrides.keys())
        valid_model_fields = set(SeqFlowStep.model_fields.keys())

        if not override_keys.issubset(valid_model_fields):
            raise ValueError(
                f"Override fields must all be valid SeqFlowStep fields. "
                f"Invalid overrides: {override_keys - valid_model_fields}, "
                f"Valid SeqFlowSteps fields: {valid_model_fields}"
            )

        # Validate override values against SeqFlowStep value constraints.
        try:  
            # Lazy way: try making a valid Step using dummy metadata
            SeqFlowStep(
                **overrides,
            )
        except ValidationError as e:
            extra_msg = "Error validating ResumeState overrides against SeqFlowStep values."
            raise ValueError(extra_msg) from e

        return overrides

    step: int
    starting_solution: dict[str, float] = Field(default_factory=dict)
    
    # Overrides are a subset of SeqFlowStep fields whose values will 
    # override those in the current step (e.g., partial wait times).
    overrides: Annotated[
        Optional[dict[str, Any]], AfterValidator(values_in_seqflow_step)
    ] = None


class SeqFlowJob(Job):
    """SeqFlow specific job containing an ordered list of steps in sequence."""
    
    protocol: list[SeqFlowStep] = Field(
        default_factory=list, 
        description="A list of steps to be run in order."
    )
    resume_state: Optional[SeqFlowResumeState] = None

    def get_duration_s(self, start_step: int = 0) -> float:
        """
        Total job duration in seconds starting from the specified step.
        Note: Because `protocol` is a list of SeqFlowSteps, `start_step` 
        represents the starting step index (e.g., resuming from step 2).
        """
        total_time_s = 0.0

        for step in self.protocol[start_step:]:
            total_volume = sum(step.solution.values()) if step.solution else 0.0
            # Implicit Pump Step
            if total_volume > 0 and step.flow_rate_mlpm is not None:
                # Use step override if it exists, otherwise fall back to job default
                total_time_s += (total_volume / step.flow_rate_mlpm) * 60.0
            elif step.duration_s:
                total_time_s += step.duration_s
        return total_time_s

    def save_resume_state(
            self, step: int, starting_solution: dict, **overrides: dict
        ):
            """Generates and saves the resume state to the job."""
            self.resume_state = SeqFlowResumeState(
                step=step,
                starting_solution=starting_solution if starting_solution else {},
                overrides=overrides if overrides else None
            )