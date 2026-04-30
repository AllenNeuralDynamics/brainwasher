from brainslosher.brainslosher_models import (
    BrainSlosherConfig,
)
import pytest
from pydantic import ValidationError


def test_required_keys():
    """Test that config selector_port_map requires air, chamber, waste"""

    with pytest.raises(ValidationError) as e:
        BrainSlosherConfig(
            selector_port_map={}, drain_volume_buffer_ml=2, fill_volume_ml=5
        )
    error_str = str(e.value)
    assert "selector_port_map must contain an 'air' key for purging line." in error_str

    with pytest.raises(ValidationError) as e:
        BrainSlosherConfig(
            selector_port_map={"air": 0, "chamber": 1},
            drain_volume_buffer_ml=2,
            fill_volume_ml=5,
        )
    error_str = str(e.value)
    assert "selector_port_map must contain a 'waste' key." in error_str

    BrainSlosherConfig(
        selector_port_map={"air": 0, "chamber": 1, "waste": 2},
        drain_volume_buffer_ml=2,
        fill_volume_ml=5,
    )
