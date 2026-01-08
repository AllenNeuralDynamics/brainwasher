from brainwasher.devices.instruments.brainslosher import BrainSlosher
from brainwasher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob
from brainwasher.devices.vessels import ReactionVessel, WasteVessel
# from brainwasher.devices.simulated_devices.syringe_pump import SimSyringePump
# from brainwasher.devices.mixer import SimulatedMixer
from runze_control.multichannel_syringe_pump import SY01B
from brainwasher.devices.pololu.pololu_tic_mixer import PololuTicMixer
import logging
from one_liner.server import RouterServer
from pathlib import Path
import time
from datetime import datetime
from typing import Literal

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
        self.add_named_call("resume", "brainslosher", "run")
        self.add_named_call("stop", "brainslosher", "stop")

        # TODO: Hacky?
        instances["self"] = self
        self.add_named_call("get_config", "self", "get_config")
        self.add_named_call("set_fill_volume", "self", "set_fill_volume")
        self.add_named_call("set_drain_buffer_volume", "self", "set_drain_buffer_volume")
        self.add_named_call("start", "self", "start_run")
        self.add_stream("state", 1, self.get_state)
        self.add_stream("progress", 1, self.brainslosher.get_progress)
      

    def get_state(self) -> Literal["idle", "running"]:
        """
         Evaluate current state of brainslosher
        """

        if self.brainslosher.job_worker and self.brainslosher.job_worker.is_alive():
            return "running"
        else: 
            return "idle"

    def start_run(self, job: BrainSlosherJob, job_path: str):
        """
        Set up a run by creating and saving job to specified path
        
        :param job: job to run
        :param jobPath: where to save job
  
        """
        # validate and save job so instrument can run
        valid_job = BrainSlosherJob(**job)
        print(valid_job)
        with open(Path(job_path), "w") as f:
            f.write(valid_job.model_dump_json())

        self.brainslosher.run(job_path)
        self.job = job

    def get_config(self) -> BrainSlosherConfig:
        """
        Convienence method to get config
        """
    
        return self.brainslosher.config
    
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
    # pump = SimSyringePump(syringe_volume_ul=config.max_syringe_volume_ml, name="sim")
    # mixer = SimulatedMixer(max_rpm=200)
    pump = SY01B(com_port="COM4", baudrate=9600, position_count=0, syringe_volume_ul=4500)
    mixer = PololuTicMixer(200)
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
