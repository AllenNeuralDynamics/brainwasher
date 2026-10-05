from pathlib import Path

import pytest
import yaml

from mixology.devices.simulated_devices.peristaltic_pump import SimPeristalticPump
from mixology.devices.simulated_devices.selector import SimSerialSelector
from mixology.devices.vessels import SlideContainer
from seqflow.seqflow import SeqFlow
from seqflow.seqflow_config_model import SeqFlowConfig
from seqflow.seqflow_models import SeqFlowJob

PACKAGE_DIR = Path(__file__).parent.parent
PROTOCOL_FILES = sorted((PACKAGE_DIR / "protocols").glob("*.yml"))


def load_port_map() -> dict[str, int]:
    """Selector port map from the default (hardware) instrument config."""
    config_file = PACKAGE_DIR / "configs" / "defaults" / "seqflow" / "default.yml"
    config = yaml.safe_load(config_file.read_text())
    return config["devices"]["selector_port_map"]["kwds"]


@pytest.fixture
def seqflow(tmp_path):
    return SeqFlow(
        config=SeqFlowConfig(save_folder=tmp_path),
        pump=SimPeristalticPump(name="sim_pump"),
        selector=SimSerialSelector(name="sim_selector", position_map=load_port_map()),
        rxn_vessel=SlideContainer(name="slide_container", num_slides=3),
    )


@pytest.mark.parametrize("protocol_file", PROTOCOL_FILES, ids=lambda p: p.name)
def test_protocol_is_valid(seqflow, protocol_file):
    job = SeqFlowJob(**yaml.safe_load(protocol_file.read_text()))
    seqflow.validate_job_against_instrument(job)
    assert job.total_duration_s > 0
