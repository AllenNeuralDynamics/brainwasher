"""Reaction Vessel Class"""

from dataclasses import dataclass, field


@dataclass(kw_only=True)
class Vessel:

    name: str
    max_volume_ul: float   # Max volume until the vessel is considered "filled."
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