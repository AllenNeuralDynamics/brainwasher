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

try:
    import seqflow
except ImportError:
    seqflow = None  # type: ignore

def loggic_setup():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

class ZMQServer(RouterServer):

    def __init__(self, rpc_port: str = "5555", broadcast_port: str = "5556",
                 config: Optional[dict] = None, instances: Optional[dict] = None):
        super().__init__(rpc_port=rpc_port, broadcast_port=broadcast_port,
                         instances=instances)
        
        self.log = logging.getLogger(self.__class__.__name__)
        self.config = config or {}
        if instances is None:
            raise ValueError("instances dictionary must be provided to ZMQServer")
        self.seqflow: SeqFlow = instances["seqflow"]  # create empyt Job
        
        self.add_named_call("start", "seqflow", "start_run")
        self.add_named_call("pause", "seqflow", "pause")
        self.add_named_call("get_job", "seqflow", "get_job")
        self.add_named_call("set_job", "seqflow", "set_job")
        self.add_named_call("get_config", "seqflow", "get_config")

        self.add_stream("get_progress", 1, "seqflow", "get_progress")

def make_pure_dict(obj):
    """Recursively converts dict-like objects into standard Python dictionaries."""
    if hasattr(obj, 'items'):  # Catches standard dicts and FileBackedDicts
        return {k: make_pure_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_pure_dict(i) for i in obj]
    return obj

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

    # Convert to dictionaries for JSON serialization
    logging_dict = make_pure_dict(config["logging"])
    logging.config.dictConfig(logging_dict)

    # Create the instrument (Mockup)
    device_specs = config
    factory = DeviceSpinner()
    device_trees = factory.create_devices_from_specs(device_specs["devices"])
    seqflow_device = device_trees["seqflow"]
    logger.info("Device tree successfully loaded.")

    # Set up formating for log server
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.project = "seqflow"
        record.version = getattr(seqflow, "__version__", "unknown") if seqflow else "unknown"
        record.comp_id = os.getenv("aibs_comp_id", "unknown")
        
        prefix = (
            f"{seqflow_device.config.instrument_name}: "
            if seqflow_device.config.instrument_name
            else ""
        )

        record.msg = f"SeqFlow: {prefix}{record.msg}"


        return record
    logging.setLogRecordFactory(record_factory)

    # Start server
    server = ZMQServer(
        instances={"seqflow": seqflow_device},
        **config.get("router_server_kwargs", {}),
    )
    logger.info("SeqFlow ZMQ Server started!")
    server.run()

    while not server.context.closed:
        time.sleep(1)


if __name__ == "__main__":
    main()
