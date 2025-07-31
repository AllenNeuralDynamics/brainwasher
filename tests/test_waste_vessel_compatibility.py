import pytest

from brainwasher.devices.instruments.brainwasher import BrainWasher
from device_spinner.device_spinner import DeviceSpinner
from device_spinner.config import Config
from brainwasher.devices.vessels import WasteVessel
from pathlib import Path


import brainwasher.devices.instruments.brainwasher
brainwasher.devices.instruments.brainwasher.SIMULATED = True


def get_simulated_brainwasher():
    pkg_dir = Path(__file__).parent.parent
    cfg_file = pkg_dir / Path("bin") / Path("sim_instrument_config.yaml")
    if not cfg_file.exists():
        raise FileNotFoundError(f"Cannot find {cfg_file.name} from path: "
                                f"{cfg_file.resolve()}")
    cfg = Config(cfg_file)
    devices = DeviceSpinner().create_devices_from_specs(dict(cfg.cfg)["devices"])
    return devices["brainwasher"]


def test_get_chemicals_for_waste_components():

    bw = get_simulated_brainwasher()
    assert bw.get_compatible_waste_vessel_id(*{"thf", "deionized_water"}) == 0
    assert bw.get_compatible_waste_vessel_id(*{"dcm"}) == 1
    assert bw.get_compatible_waste_vessel_id(*{"peanut_butter"}) == None

    # TODO: test compatibility when both vessels are compatible.
    ## Both are compatible with deionized_water. Return the least full one or
    ## the first one if they are equally full.

    # "No chemicals" case. Return the first vessel with less filled volume.
    assert bw.get_compatible_waste_vessel_id(*[]) == 0
