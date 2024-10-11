"""Reaction Vessel Class"""

from dataclasses import dataclass


@dataclass
class ReactionVessel:

    name: str
    curr_volume_ul: float # The current volume (or starting volume upon init).
    min_volume_ul: float = 5000 # Minimum volume to keep media submerged.
    max_volume_ul: float = 8000 # Maximum volume until the vessel is safely
                                #   considered "filled."

