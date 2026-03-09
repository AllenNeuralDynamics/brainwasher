from brainwasher.devices.instruments.brainslosher import BrainSlosher
from brainwasher.utils.email_issues import send_email
import logging
import logging.config
from one_liner.server import RouterServer
import time
import argparse
from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
import os
import brainwasher

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

        # Patch in extra client-interface-functionality without altering the instrument class by adding it to RouterServer directly.
        instances["self"] = self
        self.add_named_call("set_email", "self", "set_email")
        self.add_stream("check_job_status", 1, self.check_job_status)

    def set_email(self, email:str):
        """
        Set email to send errors to
        """
        self.brainslosher.config.user_email = email
            
    def check_job_status(self) -> dict:
        
        message = self.brainslosher.get_job_status()
        msg_dump = message.model_dump()
        
        if message.status == "finished":
            if self.brainslosher.config.user_email:
                send_email(subject="Brainslosher job is done!", 
                        body='<h2>Brainslosher job is done!</h2>', 
                        to=[self.brainslosher.config.user_email])
            self.brainslosher.clear_status() # finished status caught so reset status
        
        elif message.status == "failed": # error!
            if self.brainslosher.config.user_email:
                send_email(subject="Error during brainslosher job!", 
                            body='<h2>Error occured durring run:</h2>' + f'<h3>{message.message}. Please check device.</h3>', 
                            to=[self.brainslosher.config.user_email])
            self.brainslosher.clear_status() # failed status caught so reset status
            
        return msg_dump

def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=r"src\brainwasher\scripts\brainslosher_config.yaml")
    parser.add_argument("--log-level", type=str, default="INFO",
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
    config = Config(config_name)    # TODO: Should have some sort of validation here 
    
    # setup logging
    logging.config.dictConfig(dict(config.cfg["logging"]))  # set logging config before instantiating devices to not clear loggers

    # Create the instrument.
    device_specs = dict(config.cfg)
    factory = DeviceSpinner()
    device_trees = factory.create_devices_from_specs(device_specs["devices"])
    brainslosher = device_trees["brainwasher"]
    
    # set up formating for log server
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.project = "brainslosher"
        record.version = brainwasher.__version__
        record.comp_id = os.getenv("aibs_comp_id", "unknown")
        
        # set message prefix for log server readability
        prefix = f"{brainslosher.config.instrument_name}: " if brainslosher.config.instrument_name else ""
        record.msg = f"{prefix}{record.msg}"
        return record
    logging.setLogRecordFactory(record_factory)

    # start server
    server = ZMQServer(instances={"brainslosher":brainslosher}, **config.cfg.get("router_server_kwargs", {}))
    server.run()

    while not server.context.closed:
        time.sleep(1)


if __name__ == "__main__":
    main()
