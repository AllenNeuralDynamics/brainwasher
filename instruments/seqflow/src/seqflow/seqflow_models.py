"""pydantic model of seqflow job."""

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)
from mixology.job import Job
from typing import Optional, Annotated, Any, Literal
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
    volume: Optional[float] = 0.0
    source: Optional[str] = None
    solution: Optional[str] = None
    flow_rate: Optional[float] = None
    time: Optional[float] = None
    temperature: Optional[float] = None
    device: str

class SeqFlowSequence(BaseModel):
    """A named sequence of steps loaded from a JSON file."""
    name: str
    steps: list[SeqFlowStep] = Field(default_factory=list)

class SeqFlowJob(Job):
    """SeqFlow specific job containing an ordered list of sequences."""
    
    protocol: list[SeqFlowSequence] = Field(
        default_factory=list, 
        description="A list of sequences to be run in order."
    )
    resume_state = None  # TODO: Add SeqFlowResumeState

    @property
    def sequence_names(self) -> list[str]:
        """Helper property to quickly get an ordered list of all sequence names."""
        return [sequence.name for sequence in self.protocol]

    def get_duration_s(self, start_step: int = 0) -> float:
        """
        Total job duration in seconds starting from the specified step.
        Note: Because `protocol` is a list of SeqFlowSequences, `start_step` 
        represents the starting sequence index (e.g., resuming from sequence 2).
        """
        total_time_s = 0.0

        for sequence in self.protocol[start_step:]:
            for step in sequence.steps:
                if step.device == "pump" and step.volume and step.flow_rate:
                    # Convert: (volume / flow_rate) gives minutes. Multiply by 60 for seconds.
                    total_time_s += (step.volume / step.flow_rate) * 60.0
                elif step.device in ["heat_device", "wait"] and step.time:
                    # Time is already explicitly defined in seconds
                    total_time_s += step.time

        return total_time_s
