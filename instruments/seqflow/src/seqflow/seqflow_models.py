# seqflow_models.py
"""pydantic model of seqflow job."""

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    AfterValidator,
)
from mixology.job import Job
from typing import Optional, Annotated, Any
from pathlib import Path

class SeqFlowConfig(
    BaseModel,
    validate_assignment=True,
):
    save_folder: Path = Field(default="../../seq_flow_jobs/")
    selector_port_map: dict[str, int]
    instrument_name: Optional[str] = Field(
        default=None, description="Optional instrument name."
    )

class SeqFlowStep(BaseModel):
    """Model representing a single action within a sequence."""
    # --- METADATA TRACKING ---
    sequence_name: str = Field(description="The name of the sequence this step belongs to.")
    sequence_index: int = Field(description="The execution order index of the parent sequence.")

    # --- STEP PARAMETERS ---
    # TODO clean up some fields, currently match with sequence.json file
    flow_rate_mlpm: Optional[float] = Field(default=None, description="Flow rate in mL/min for pump device.")
    duration_m: Optional[float] = Field(default=None, description="Time in minutes for each step.")
    temp_c: Optional[float] = Field(default=None, description="Temperature in Celsius for the heat wait step.")
    device: str = Field(description="The device to be used for this step (e.g., pump, heat_device, wait, stopper).")
    solution: dict[str, float] = Field(default_factory=dict, description="solution name and volumn (mL) to fill into slides.")

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
                sequence_name="resume_validation",  # TODO
                sequence_index=0, 
                device="pump"
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
            if step.device == "pump" and step.flow_rate_mlpm:
                total_volume = sum(step.solution.values()) if step.solution else 0.0
                if total_volume > 0:
                    # Convert: (volume / flow_rate) gives minutes. Multiply by 60 for seconds.
                    # TODO maybe need to multiply by number of slides. (Check pump)
                    total_time_s += (total_volume / step.flow_rate_mlpm) * 60.0
            elif step.device in ["heat_device", "wait"] and step.duration_m:
                    total_time_s += step.duration_m * 60.0  # Convert minutes to seconds
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