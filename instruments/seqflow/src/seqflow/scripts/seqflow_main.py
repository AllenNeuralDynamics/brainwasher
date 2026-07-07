import json
import os
import time
import logging
import logging.config
import argparse
from typing import Optional

from one_liner.server import RouterServer  # type: ignore
from device_spinner.file_backed_dict import FileBackedDict  # type: ignore
from device_spinner.device_spinner import DeviceSpinner  # type: ignore
from seqflow.seqflow import SeqFlow  # type: ignore


class ZMQServer(RouterServer):
    def __init__(self, rpc_port: str = "5555", broadcast_port: str = "5556",
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
    parser.add_argument("--config", type=str, default="src/seqflow/scripts/sim_seqflow_config.yaml")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["INFO", "DEBUG"])
    parser.add_argument("--simulated", default=False, action="store_true",
                        help="Simulate hardware device connections.")

    args = parser.parse_args()
    logger = logging.getLogger()
    
    # Override console log level if specified.
    for handler in logger.handlers:
        if handler.get_name() == 'console':
            handler.setLevel(args.log_level)

    config_name = args.config if not args.simulated else "src/seqflow/scripts/sim_seqflow_config.yaml"
    config = FileBackedDict(config_name)
    logging.config.dictConfig(config["logging"].to_dict())

    factory = DeviceSpinner()
    devices = factory.create_devices_from_specs(config.get("devices", {}))
    logger.info("Device tree successfully loaded.")

    # Start devices (if they have a start method)
    for device_name, device in devices.items():
        if hasattr(device, "start"):
            logger.debug(f"Starting device: {device_name}")
            device.start()

    # Set up formatting for log server (Specific to seqflow)
    seqflow_device = devices.get("seqflow")
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.project = "seqflow"
        record.version = getattr(SeqFlow, "__version__", "unknown") if SeqFlow is not None else "unknown"
        record.comp_id = os.getenv("aibs_comp_id", "unknown")
        prefix = ""
        if seqflow_device and hasattr(seqflow_device, "config") and seqflow_device.config.instrument_name:
            prefix = f"{seqflow_device.config.instrument_name}: "
        record.msg = f"SeqFlow: {prefix}{record.msg}"
        return record
    logging.setLogRecordFactory(record_factory)

    server = ZMQServer(instances=devices,
                        config=config.get("router_server_api", {}),
                        **config.get("router_server_kwargs", {}))
    
    logger.info("SeqFlow ZMQ Server started!")
    server.run()

    while not server.context.closed:
        time.sleep(1)

if __name__ == "__main__":
    main()