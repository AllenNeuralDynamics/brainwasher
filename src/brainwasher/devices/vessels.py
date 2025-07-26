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
        for chemical, volume_ul in chemicals.items():
            if chemical in self.solution:
                self.solution[chemical] += volume_ul
            else:
                self.solution[chemical] = volume_ul

    def purge_solution(self):
        self.solution = {}


@dataclass
class ReactionVessel(Vessel):
    pass


@dataclass(kw_only=True)
class WasteVessel(Vessel):

    compatible_chemicals: set = field(default_factory=set)