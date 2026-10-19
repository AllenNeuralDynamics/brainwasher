from pathlib import Path
from typing import Any, Literal

from device_spinner.models import DeviceTrees  # type: ignore
from one_liner.models import RouterServerConfig  # type: ignore
from pydantic import BaseModel, ConfigDict, Field


class HandlerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    class_: str = Field(..., alias="class")
    level: str | None = None
    formatter: str | None = None
    filename: str | None = None


class LoggingConfig(BaseModel):
    version: Literal[1]
    disable_existing_loggers: bool = False
    formatters: dict[str, dict[str, Any]] | None = None
    handlers: dict[str, HandlerConfig] | None = None
    loggers: dict[str, dict[str, Any]] | None = None
    root: dict[str, Any] | None = None


class RouterServerPortConfig(BaseModel):
    rpc_port: int = 5557
    broadcast_port: int = 5558


class SeqFlowConfig(BaseModel, validate_assignment=True):
    # Use default_factory to satisfy mypy's static type checker
    save_folder: Path = Field(default_factory=lambda: Path("../../seq_flow_jobs/"))
    selector_port_map: dict[str, int]
    instrument_name: str | None = Field(
        default=None, description="Optional instrument name."
    )


class SeqFlowSystemConfig(BaseModel, validate_assignment=True):
    devices: DeviceTrees = Field(default_factory=dict)
    router_server_kwargs: RouterServerPortConfig = Field(
        default_factory=RouterServerPortConfig
    )
    router_server_api: RouterServerConfig
    logging: LoggingConfig
