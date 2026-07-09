from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class SeqFlowConfig(BaseModel, validate_assignment=True):
    # Use default_factory to satisfy mypy's static type checker
    save_folder: Path = Field(default_factory=lambda: Path("../../seq_flow_jobs/"))
    
    selector_port_map: dict[str, int]
    instrument_name: Optional[str] = Field(
        default=None, 
        description="Optional instrument name."
    )
