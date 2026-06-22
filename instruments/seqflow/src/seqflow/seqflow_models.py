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


class SeqFlowJob(Job):
    pass
    
class SeqFlowJobStatus(BaseModel):
    """Model of messages used to convey state of seqflow job"""

    status: Literal["failed", "finished", "running", "paused", "idle"] = Field(
        ..., description="Indicated if status of job."
    )
    message: Optional[str] = Field(
        default=None, description="Optional message of additional info."
    )