import os
import time
import logging
import logging.config
import argparse
from typing import Optional
from pathlib import Path

from one_liner.server import RouterServer  # type: ignore
from device_spinner.device_spinner import DeviceSpinner  # type: ignore
from seqflow.seqflow import SeqFlow
from seqflow.seqflow_config_model import SeqFlowSystemConfig
from ficus.services.configs import get_config  # type: ignore
from ficus.database.filesys import FileSysStore  # type: ignore


class ZMQServer(RouterServer):
    def __init__(self, rpc_port: str = "5557", broadcast_port: str = "5558",
                 config: Optional[dict] = None, instances: Optional[dict] = None):
        
        super().__init__(rpc_port=rpc_port, broadcast_port=broadcast_port,
                         instances=instances, config=config)

        self.log = logging.getLogger(self.__class__.__name__)
        self.config = config or {}
        
        if instances is None:
            raise ValueError("instances dictionary must be provided to ZMQServer")

        if "seqflow" in instances:
            self.seqflow: SeqFlow = instances["seqflow"]
        

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Override the console log level specified in the config file."
    )
    parser.add_argument("--simulated", default=False, action="store_true",
                        help="Simulate hardware device connections.")
    parser.add_argument("--config-dir", type=str, default=None,
                        help="Absolute or relative path to the configs directory.")

    args = parser.parse_args()
    logger = logging.getLogger()
    
    # Config
    if args.config_dir:
        config_dir = Path(args.config_dir).resolve()
    else:
        config_dir = Path(__file__).resolve().parents[3] / "configs"
    data_store = FileSysStore(rootdir=config_dir, scopes={"defaults", "hostname"})
    current_scopes = {"hostname": "dev_computer"}
    logging_config = get_config(data_store=data_store, namespace="logging")
    seqflow_config = get_config(data_store=data_store, namespace="seqflow", scope_identifiers=current_scopes)
    seqflow_config.data["logging"] = logging_config.data.get("logging", {})
    config = SeqFlowSystemConfig(**seqflow_config.data)

    # Set log level and get Logger
    if args.log_level:
        config.logging['handlers']['console']['level'] = args.log_level
    logging.config.dictConfig(config.logging)

    # Send as spec (class_name -> class object, kwawrgs -> kwds, Remove None values)
    factory = DeviceSpinner()
    devices_dict = config.devices.model_dump(by_alias=True, exclude_none=True)
    devices = factory.create_devices_from_specs(devices_dict)
    logger.info("Device tree successfully loaded.")

    # Set up formatting for log server (Specific to seqflow)
    seqflow_device = devices.get("seqflow")
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.project = "seqflow"
        record.version = getattr(SeqFlow, "__version__", "unknown")
        record.comp_id = os.getenv("aibs_comp_id", "unknown")
        prefix = f"{seqflow_device.config.instrument_name}: "
        record.msg = f"SeqFlow: {prefix}{record.msg}"
        return record
    logging.setLogRecordFactory(record_factory)

    server = ZMQServer(instances=devices,
                        config=config.router_server_api.model_dump(),
                        **config.router_server_kwargs.model_dump())
    
    logger.info("SeqFlow ZMQ Server started!")
    server.run()

    try:
        while not server.context.closed:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down seqflow server..")
    finally:
        pass

if __name__ == "__main__":
    main()