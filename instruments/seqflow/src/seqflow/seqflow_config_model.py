from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from device_spinner.models import DeviceTrees  # type: ignore


class NamedCallConfig(BaseModel):
    """Configuration for a single named call."""
    obj_name: str
    attr_name: str


class PeriodicStreamConfig(NamedCallConfig):
    """Configuration for a periodic stream. Inherits obj and attr names."""
    frequency_hz: float


class RouterServerAPIConfig(BaseModel):
    """Validates the router_server_api section, defaulting to empty dicts if missing."""
    named_calls: Dict[str, NamedCallConfig] = Field(default_factory=dict)
    periodic_streams: Dict[str, PeriodicStreamConfig] = Field(default_factory=dict)


class RouterServerConfig(BaseModel):
    rpc_port: int = 5557
    broadcast_port: int = 5558


class SeqFlowConfig(BaseModel, validate_assignment=True):
    # Use default_factory to satisfy mypy's static type checker
    save_folder: Path = Field(default_factory=lambda: Path("../../seq_flow_jobs/"))
    selector_port_map: dict[str, int]
    instrument_name: Optional[str] = Field(
        default=None, 
        description="Optional instrument name."
    )

class SeqFlowSystemConfig(BaseModel, validate_assignment=True):
    devices: DeviceTrees = Field(default_factory=dict)
    router_server_kwargs: RouterServerConfig = Field(default_factory=RouterServerConfig)
    router_server_api: RouterServerAPIConfig = Field(default_factory=RouterServerAPIConfig)
    logging: Dict[str, Any] = Field(default_factory=dict, description="Logging configuration dictionary.")  # TODO: Add pydantic model
    

