from brainwasher.devices.instruments.brainslosher import BrainSlosher
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob, BrainSlosherJobStatus
from brainwasher.utils.email_issues import send_email
import logging
import logging.config
from one_liner.server import RouterServer
from pathlib import Path
import time
from datetime import datetime
from typing import Literal
import queue
import argparse
from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
import yaml

logging.basicConfig(level=logging.DEBUG)

class ZMQServer(RouterServer):

    def __init__(self, rpc_port: str = "5555", broadcast_port: str = "5556",
                 config: dict[str, str] = None, instances: dict = None):
        super().__init__(rpc_port=rpc_port, broadcast_port=broadcast_port,
                         instances=instances)
        
        self.log = logging.getLogger(self.__class__.__name__)
        self.config = config or {}
        self.brainslosher: BrainSlosher = instances["brainslosher"]
        
        self.add_named_call("fill_chamber", "brainslosher", "fill_chamber")
        self.add_named_call("drain_chamber", "brainslosher", "drain_chamber", kwargs={"volume_ml": self.brainslosher.rxn_vessel.max_volume_ul/1000})    # fully drain vessel since ui does not know current fill
        self.add_named_call("pause", "brainslosher", "pause")
        self.add_named_call("clear", "brainslosher", "clear_job")
        self.add_named_call("get_job", "brainslosher", "get_job")
        self.add_named_call("set_job", "brainslosher", "set_job")
        self.add_named_call("get_config", "brainslosher", "get_config")
        self.add_named_call("set_fill_volume", "brainslosher", "set_fill_volume")
        self.add_named_call("set_drain_buffer_volume", "brainslosher", "set_drain_buffer_volume")
        self.add_named_call("empty_waste", "brainslosher", "empty_waste")
        self.add_named_call("start", "brainslosher", "start_run")
        self.add_named_call("resume", "brainslosher", "resume_run")
        self.add_named_call("save_job", "brainslosher", "save_job")
        self.add_stream("progress", 1, self.brainslosher.get_progress)
        self.add_stream("check_job_status", 1, self.brainslosher.get_job_status_message)

        # Patch in extra client-interface-functionality without altering the instrument class by adding it to RouterServer directly.
        instances["self"] = self
        self.add_named_call("set_email", "self", "set_email")
        self.brainslosher.add_job_status_listener(self.alert_on_job_status_change)

    def set_email(self, email:str):
        """
        Set email to send errors to
        """
        self.brainslosher.config.user_email = email

    def alert_on_job_status_change(self, job_status: JobStatus):
        """Send an email on certain job status changes."""
        message = job_status
        if message.status == "finished":
            if self.brainslosher.config.user_email:
                send_email(subject="Brainslosher job is done!",
                        body='<h2>Brainslosher job is done!</h2>',
                        to=[self.brainslosher.config.user_email])
        elif message.status == "failed": # error!
            if self.brainslosher.config.user_email:
                send_email(subject="Error during brainslosher job!",
                            body='<h2>Error occured durring run:</h2>'
                                 + f'<h3>{message.message}. Please check device.</h3>',
                            to=[self.brainslosher.config.user_email])

def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=r"src\brainwasher\scripts\brainslosher_config.yaml")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["INFO", "DEBUG"])
    parser.add_argument("--simulated", default=False, action="store_true",
                        help="Simulate hardware device connections.")

    args = parser.parse_args()
    logger = logging.getLogger()
    
    # Override console log level if specified.
    for handler in logger.handlers:
        if handler.get_name() == 'console':
            handler.setLevel(args.log_level)
    
    config_name = args.config if not args.simulated else r"src\brainwasher\scripts\sim_brainslosher_config.yaml"
    config = Config(config_name)
    
    # setup logging
    logging.config.dictConfig(dict(config.cfg["logging"]))
        
    # Create the instrument.
    device_specs = dict(config.cfg)
    factory = DeviceSpinner()
    device_trees = factory.create_devices_from_specs(device_specs["devices"])
    brainslosher = device_trees["brainwasher"]
    server = ZMQServer(instances={"brainslosher":brainslosher})
    server.run()

    while not server.context.closed:
        time.sleep(1)


if __name__ == "__main__":
    main()
