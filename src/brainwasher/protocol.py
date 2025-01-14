"""Tissue-clearing proof-of-concept"""

import logging
import pandas as pd
import re
from enum import Enum
from functools import lru_cache
from pathlib import Path
from pint import UnitRegistry
from typing import Union


class Protocol:
    """Parser for reading/writing protocols to/from CSV files."""

    def __init__(self, file: Union[Path, str, None] = None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.ureg = UnitRegistry()
        self.df = pd.read_csv(file) if file else None

    def load(self, file: Union[Path, str]):
        self.df = pd.read_csv(file)
        self.get_chemicals.cache_clear()
        self.get_solution.cache_clear()

    @property
    def step_count(self):
        """Return the number of steps in this protocol."""
        return len(self.df.index)

    @lru_cache(maxsize=None)
    def get_chemicals(self, step: Union[int, None] = None):
        """Return all chemicals present in a protocol file or for a specific
        step."""
        if step is not None:
            entry = self.df.loc[step, "Chemicals"]
            return {c.strip() for c in entry.split(",")}
        column = self.df.loc[:, "Chemicals"]
        chem_list = [c.strip() for entry in column.values for c in entry.split(",")]
        return set(chem_list)

    def get_duration_s(self, step: int):
        """Return the duration in seconds"""
        return self.ureg(self.df.loc[step, "Duration"]).to('seconds').m

    def get_mix_speed_percent(self, step: int):
        parsed_mix_speed = self.ureg(self.df.loc[step, "Mix Speed"])
        if type(parsed_mix_speed) in [float, int]:
            return float(parsed_mix_speed)
        if type(parsed_mix_speed) == self.ureg.Quantity:
            if parsed_mix_speed.units == self.ureg.percent:
                return float(parsed_mix_speed.magnitude)
        raise ValueError("Unrecognized mix speed specification.")

    @lru_cache(maxsize=None)
    def get_solution(self, step: int, max_volume_ul: float):
        """Return a dictionary, keyed by chemical name, of the solution volume
        in microliters"""
        solution = {}
        solution_str = self.df.loc[step, "Solution"]
        chemicals = self.get_chemicals(step)
        all_chemicals = self.get_chemicals()
        # Parse string for volume fraction.
        qty_words = [q.strip() for q in solution_str.split(',')]
        for qty_word in qty_words:
            found_chemical = None
            qty = None
            for chemical in chemicals:
                if chemical in qty_word:
                    found_chemical = chemical
                    qty = self.ureg(qty_word.rstrip(chemical))
                    # Convert 'amount' to microliters.
                    if type(qty) != self.ureg.Quantity:
                        raise ValueError("Solution specification for step "
                                         f"{step} has no units!")
                    if qty.units == self.ureg.percent:
                        ul = float((qty.magnitude / 100.) * max_volume_ul)
                    else:
                        ul = float(qty.to('uL').magnitude)
                    solution[chemical] = ul
            if not all([found_chemical, qty]):
                raise RuntimeError(f"Cannot parse solution on step {step}.")
        # TODO: Infer remaining percents if any are missing.
        ## If any quantities are specified as a percent, infer any missing qty.
        #if any([i.units == self.ureg.percent for i in solution.values()]):
        #    print("found percent!!")
        return solution

    def validate(self):
        """Read the current schedule. Ensure every step is doable on the
        target system.
        """
        for index, row in self.df.iterrows():
            #print(row['c1'], row['c2'])
            pass
        # Easy way: iterate through all function calls and cache everything.
        # Validate column names.
        # Validate chemicals.
        # Validate solutions.
        # Validate durations.
        # Validate solution spec as "all percent" or "all volume-based"
        pass



