"""Reaction Vessel Class"""

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class Vessel:
    name: str
    max_volume_ul: float  # Max volume until the vessel is considered "filled."
    solution: dict = field(default_factory=dict)

    @property
    def curr_volume_ul(self):
        return sum(self.solution.values())

    def add_solution(self, **chemicals: dict[str, float]):
        added_volume_ul = sum(chemicals.values())
        if self.curr_volume_ul + added_volume_ul > self.max_volume_ul:
            raise ValueError("Adding solution would exceed max volume.")
        for chemical_name, volume_ul in chemicals.items():
            curr_volume_ul = self.solution.get(chemical_name, 0)
            self.solution[chemical_name] = curr_volume_ul + volume_ul

    def purge_solution(self):
        self.solution = {}


@dataclass
class ReactionVessel(Vessel):
    pass


@dataclass(kw_only=True)
class WasteVessel(Vessel):
    compatible_chemicals: set = field(default_factory=set)


@dataclass(kw_only=True)
class SlideContainer(Vessel):
    """A custom reaction vessel representing a multi-slide flow cell."""
    num_slides: int  # TODO: This can be used to calculate the duration_s of step
    max_volume_ul: float = field(init=False)

    def __post_init__(self):
        """Set max volume to infinity since this is a continuous flow cell."""
        self.max_volume_ul = float('inf')

    def add_solution(self, **chemicals: dict[str, float]):
        """
        Override the base Vessel add_solution method.
        Because this is a flow cell, excess liquid routes to waste.
        We track the chemicals currently added but ignore the max volume limit.
        """
        for chemical_name, volume_ul in chemicals.items():
            curr_volume_ul = self.solution.get(chemical_name, 0)
            self.solution[chemical_name] = curr_volume_ul + volume_ul
