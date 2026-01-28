from brainwasher.devices.instruments.brainslosher import BrainSlosher
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob
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
        self.add_stream("progress", 1, self.brainslosher.get_progress)

        # TODO: Hacky?
        instances["self"] = self
        self.add_named_call("set_email", "self", "set_email")
        self.add_named_call("get_config", "self", "get_config")
        self.add_named_call("set_fill_volume", "self", "set_fill_volume")
        self.add_named_call("set_drain_buffer_volume", "self", "set_drain_buffer_volume")
        self.add_named_call("empty_waste", "self", "empty_waste")
        self.add_named_call("start", "self", "start_run")
        self.add_named_call("resume", "self", "resume_run")
        self.add_named_call("save_job", "self", "save_job")
        self.add_stream("check_job_status", 1, self.check_job_status)

    def set_email(self, email:str):
        """
        Set email to send errors to
        """
        self.brainslosher.config.user_email = email
            

    def save_job(self, job: dict):
        """
        Save job to local computer based on the job name
        
        :param job: job to save
        """

        # validate job 
        valid_job = BrainSlosherJob(**job)
        
        # if the file exists, append a counter to make it unique
        counter = 1
        job_path = Path(self.brainslosher.config.save_folder) / f"{valid_job.name}.yaml"
        while job_path.exists():
            job_path = Path(self.brainslosher.config.save_folder) / f"{valid_job.name}_{counter}.yaml"
            counter += 1

        with open(Path(job_path), "w") as f:
            yaml.dump(valid_job.model_dump(), f)
        
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
        
    def resume_run(self):
        """
        Resume job
        """
        job = self.brainslosher._job
        if not job or not job.resume_state:
            logging.error("No job to resume")
            return
        
        if not job.source_protocol.path:
            logging.error("No source protocol path to save to.")
            return
                
        self.brainslosher.run(job.source_protocol.path)

    def restart_run(self, job: BrainSlosherJob):
        """
        Reset brainslosher and start run
        
        :param job: job to run
  
        """
        # reset brainslosher 
        self.brainslosher.reset_state()
        self.start_run(job)

    
    def start_run(self, job: BrainSlosherJob):
        """
        Set up a run by creating and saving job to specified path
        
        :param job: job to run
          
        """
        # validate and save job so instrument can run
        valid_job = BrainSlosherJob(**job)

        # create path for job
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        job_path = (
            Path(self.brainslosher.config.save_folder)
            / f"{valid_job.name}_{timestamp}.yaml"
        )

        valid_job.source_protocol.path = job_path
        with open(Path(job_path), "w") as f:
            yaml.dump(valid_job.model_dump(), f)
        self.brainslosher.run(job_path)
        
    def get_job(self) -> BrainSlosherJob | None:
        """
        Convienence method to get current job
        """
    
        return self.brainslosher._job

    
    def get_config(self) -> BrainSlosherConfig:
        """
        Convienence method to get config
        """
    
        return self.brainslosher.config.model_dump()
    
    def set_fill_volume(self, volume: float) -> None:
        """
        Convienence method for setting fill volume key in config
        
        :param volume: wash volume in ml
        """
        self.brainslosher.config.fill_volume_ml = volume
        
    def set_drain_buffer_volume(self, volume: float) -> None:
        """
        Convienence method for setting drain buffer key in config
        
        :param volume: drain buffer volume in ml
        """
        self.brainslosher.config.drain_volume_buffer_ml = volume

    def empty_waste(self) -> None:
        """
        waste container was emptied
        """
        self.brainslosher.waste.purge_solution()


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
