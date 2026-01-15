from brainwasher.devices.instruments.brainslosher import BrainSlosher
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob
from brainwasher.devices.vessels import ReactionVessel, WasteVessel
from brainwasher.devices.simulated_devices.syringe_pump import SimSyringePump
from brainwasher.devices.mixer import SimulatedMixer
from runze_control.multichannel_syringe_pump import SY01B
from brainwasher.devices.pololu.pololu_tic_mixer import PololuTicMixer
import logging
from one_liner.server import RouterServer
from pathlib import Path
import time
from datetime import datetime
from typing import Literal
import queue


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
        self.add_named_call("drain_chamber", "brainslosher", "drain_chamber")
        self.add_named_call("pause", "brainslosher", "pause")
        self.add_named_call("restart", "brainslosher", "start_run")
        self.add_named_call("clear", "brainslosher", "reset_state")
        self.add_stream("progress", 1, self.brainslosher.get_progress)

        # TODO: Hacky?
        instances["self"] = self
        self.add_named_call("get_config", "self", "get_config")
        self.add_named_call("set_fill_volume", "self", "set_fill_volume")
        self.add_named_call("set_drain_buffer_volume", "self", "set_drain_buffer_volume")
        self.add_named_call("empty_waste", "self", "empty_waste")
        self.add_named_call("start", "self", "start_run")
        self.add_named_call("resume", "self", "resume_run")
        self.add_stream("error_check", 1, self.check_worker_errors)
        self.add_stream("state", 1, self.get_state)    
              

    def check_worker_errors(self):
        try:
            err = self.brainslosher.job_worker_error.get_nowait()
            return f"Error occured during run: {err}"
        except queue.Empty as e:
            pass
            
    def get_state(self) -> Literal["idle", "running"]:
        """
         Evaluate current state of brainslosher
        """

        if self.brainslosher.job_worker and self.brainslosher.job_worker.is_alive():
            return "running"
        
        elif self.brainslosher._job and self.brainslosher._job.resume_state:
            return "paused"
        
        else: 
            return "idle"

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
        
        # run pre check to catch error in main thread
        if  self.brainslosher.rxn_vessel.solution != job.starting_solution:
                raise ValueError("When starting, reaction vessel starting "
                                 f"solution {self.brainslosher.rxn_vessel.solution} does not match the correct "
                                 f"starting solution {job.starting_solution}. Please drain")
        
        self.brainslosher.run(job.source_protocol.path)

    def start_run(self, job: BrainSlosherJob):
        """
        Set up a run by creating and saving job to specified path
        
        :param job: job to run
        :param jobPath: where to save job
  
        """
        # validate and save job so instrument can run
        valid_job = BrainSlosherJob(**job)

        # run pre check to catch error in main thread
        if  self.brainslosher.rxn_vessel.solution != valid_job.starting_solution:
                raise ValueError("When starting, reaction vessel starting "
                                 f"solution {self.brainslosher.rxn_vessel.solution} does not match the correct "
                                 f"starting solution {valid_job.starting_solution}. Please drain")

        # create path for job
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        job_path = (
            Path(self.brainslosher.config.save_folder)
            / f"{valid_job.name}_{timestamp}.yaml"
        )

        valid_job.source_protocol.path = job_path
        with open(Path(job_path), "w") as f:
            f.write(valid_job.model_dump_json())
        self.brainslosher.run(job_path)
        
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
    
    config = BrainSlosherConfig(selector_port_map= {
                                                    "air": 4,
                                                    "chamber": 6,
                                                    "waste": 3,
                                                    "drain":5,
                                                    "PBS": 1,
                                                    "diH20":2
                                                    },
                                drain_volume_buffer_ml=.5,
                                fill_volume_ml=10 
                                )
    chamber = ReactionVessel(name="chamber", max_volume_ul=50000)
    waste = WasteVessel(name="waste", max_volume_ul=50000)
    pump = SimSyringePump(syringe_volume_ul=config.max_syringe_volume_ml, name="sim")
    mixer = SimulatedMixer(max_rpm=200)
    # pump = SY01B(com_port="COM4", baudrate=9600, position_count=0, syringe_volume_ul=5000)
    # mixer = PololuTicMixer(200)
    brainslosher = BrainSlosher(config=config,
                                rxn_vessel=chamber,
                                pump=pump,
                                mixer=mixer,
                                waste_vessel=waste)
    server = ZMQServer(instances={"brainslosher":brainslosher})
    server.run()

    while not server.context.closed:
        time.sleep(1)


if __name__ == "__main__":
    main()
