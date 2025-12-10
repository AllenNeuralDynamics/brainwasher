"""pydantic model of brainwasher job."""

from pydantic import BaseModel, Field, field_validator
from brainwasher.job import Job


class Cycle(BaseModel):
    solution: str = Field(..., description="Solution to use in all washes of cycle.")
    duration_min: float = Field(..., description="Duration in minutes of all washes in cycle.")
    washes: int = Field(..., description="Number of washes performed in cycle.")

class WashVolumes(BaseModel):
    fill_volume_ml: float = Field(..., description="Fill volume of all washes.")
    drain_volume_ml: float = Field(..., description="Drain volume of all washes. May exceed fill to totally drain reaction vessel.")

class BrainSlosherJob(Job):
    protocol: list[Cycle] = list()
    motor_speed_rpm: float = Field(..., description="Speed of motor in rpms. Set to 0 to disable motor.")



class BrainSlosherConfig(BaseModel):
    selector_port_map: dict[str, int]
    max_syringe_volume_ml: float = Field(default=4.5, description="Maximum fill volume of the syringe to prevent chatter when operating.")
    prime_pump_volume_ml: float = Field(default=3, description="Volume to prime line with.")
    prime_line_reps: int = Field(..., description="Number of reps to prime line.")
    waste_volume_ml: float = Field(..., description="Volume of waste volume vessel.")

    @field_validator("selector_port_map")
    def check_required_keys(cls, v):
        if "air" not in v:
            raise ValueError("selector_port_map must contain an 'air' key for purging line.")
        elif "chamber" not in v:
            raise ValueError("selector_port_map must contain a 'chamber' key.")
        elif "waste" not in v:
            raise ValueError("selector_port_map must contain a 'waste' key.")
        return v