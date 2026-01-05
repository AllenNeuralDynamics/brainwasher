from brainwasher.devices.instruments.brainslosher import BrainSlosher
from brainwasher.brainslosher_models import BrainSlosherConfig
from brainwasher.devices.vessels import ReactionVessel, WasteVessel
from brainwasher.devices.simulated_devices.syringe_pump import SimSyringePump
from brainwasher.devices.mixer import SimulatedMixer
import logging
from one_liner.server import RouterServer
from one_liner.client import RouterClient
import time

class ZMQServer(RouterServer):

    def __init__(self, rpc_port: str = "5555", broadcast_port: str = "5556",
                 config: dict[str, str] = None, instances: dict = None):
        super().__init__(rpc_port=rpc_port, broadcast_port=broadcast_port,
                         instances=instances)
        
        self.log = logging.getLogger(self.__class__.__name__)
        self.config = config or {}
        
        self.add_named_call("set_fill_volume", "brainslosher", "set_fill_volume")
        self.add_named_call("set_drain_buffer_volume", "brainslosher", "set_drain_buffer_volume")
        self.add_named_call("get_config", "brainslosher", "get_config")
        
def main():
    
    config = BrainSlosherConfig(selector_port_map= {
                                                    "air": 0,
                                                    "chamber": 1,
                                                    "waste": 2,
                                                    "PBS": 3,
                                                    "diH20":4
                                                    },
                                drain_volume_buffer_ml=.5,
                                fill_volume_ml=11 
                                )
    chamber = ReactionVessel(name="chamber", max_volume_ul=50000)
    waste = WasteVessel(name="waste", max_volume_ul=50000)
    pump = SimSyringePump(syringe_volume_ul=config.max_syringe_volume_ml, name="sim")
    mixer = SimulatedMixer(max_rpm=200)
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
