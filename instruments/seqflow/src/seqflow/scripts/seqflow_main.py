import os
import time
import logging
import logging.config
import argparse
from typing import Optional

from one_liner.server import RouterServer  # type: ignore
from device_spinner.config import Config  # type: ignore
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
        self.seqflow: SeqFlow = instances["seqflow"]  # create empyt Job
        
        self.add_named_call("start", "seqflow", "start_run")
        self.add_named_call("pause", "seqflow", "pause")
        self.add_named_call("get_job", "seqflow", "get_job")
        self.add_named_call("set_job", "seqflow", "set_job")
        self.add_named_call("get_config", "seqflow", "get_config")

        self.add_stream("get_progress", 1, "seqflow", "get_progress")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=r"src\seqflow\scripts\sim_seqflow_config.yaml")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["INFO", "DEBUG"])
    parser.add_argument("--simulated", default=False, action="store_true",
                        help="Simulate hardware device connections.")

    args = parser.parse_args()
    logger = logging.getLogger()
    
    # Override console log level if specified.
    for handler in logger.handlers:
        if handler.get_name() == 'console':
            handler.setLevel(args.log_level)

    config_name = args.config if not args.simulated else r"src\seqflow\scripts\sim_seqflow_config.yaml"
    config = Config(config_name)

    # Set logging config before instantiating devices to not clear loggers
    if hasattr(config, "cfg") and "logging" in config.cfg:
        logging.config.dictConfig(dict(config.cfg["logging"]))  # TODO Add logging into yaml config
    else:
        loggic_setup()

    # Create the instrument (Mockup)
    device_specs = dict(config.cfg)
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
        
        record.msg = f"SeqFlow: {record.msg}"
        return record
    logging.setLogRecordFactory(record_factory)

    # Start server
    server = ZMQServer(
        instances={"seqflow": seqflow_device},
        **config.cfg.get("router_server_kwargs", {}),
    )
    logger.info(f"SeqFlow ZMQ Server started!")
    server.run()

    while not server.context.closed:
        time.sleep(1)


if __name__ == "__main__":
    main()
