from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, Literal
from device_spinner.models import DeviceTrees  # type: ignore
from one_liner.models import RouterServerConfig  # type: ignore


class HandlerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    class_: str = Field(..., alias="class")
    level: Optional[str] = None
    formatter: Optional[str] = None
    filename: Optional[str] = None


class LoggingConfig(BaseModel):
    version: Literal[1]
    disable_existing_loggers: bool = False
    formatters: Optional[Dict[str, Dict[str, Any]]] = None
    handlers: Optional[Dict[str, HandlerConfig]] = None
    loggers: Optional[Dict[str, Dict[str, Any]]] = None
    root: Optional[Dict[str, Any]] = None


class RouterServerPortConfig(BaseModel):
    rpc_port: int = 5557
    broadcast_port: int = 5558


class SeqFlowConfig(BaseModel, validate_assignment=True):
    instrument_name: Optional[str] = Field(
        default=None, description="Optional instrument name."
    )
    # Use default_factory to satisfy mypy's static type checker
    save_folder: Path = Field(default_factory=lambda: Path("../../seq_flow_jobs/"))
    protocols_folder: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent / "protocols"
    )

class SeqFlowSystemConfig(BaseModel, validate_assignment=True):
    devices: DeviceTrees = Field(default_factory=dict)
    router_server_kwargs: RouterServerPortConfig = Field(
        default_factory=RouterServerPortConfig
    )
    router_server_api: RouterServerConfig
    logging: LoggingConfig
