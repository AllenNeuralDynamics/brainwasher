"""Tissue-clearing proof-of-concept"""

import _thread
import logging

from brainwasher.devices.instruments.brainwasher import BrainWasher

from mock import patch


class SimBrainWasher(BrainWasher):

    """Brainwasher with simulated return values where functionality depends
    on real-world system state.
    """

    #@patch(BrainWasher, "selector_lds_map['YELLOW']")
    def prime_reservoir_line(self, chemical: str,
                             max_pump_displacement_ul: int = 12500):
        # patch attribute return value.
        super().prime_reservoir_line(chemical=chemical,
                                     max_pump_displacement_ul=max_pump_displacement_ul)

    def unprime_reservoir_line(self, chemical: str,
                               max_pump_displacement_ul: int = 25000):
        super().unprime_reservoir_line(chemical=chemical,
                                       max_pump_displacement_ul=max_pump_displacement_ul)

    def purge_pump_line(self, full_cycles: int = 1):
        super().purge_pump_line(full_cycles=full_cycles)

    def dispense_to_vessel(self, microliters: float, chemical: str):
        super().dispense_to_vessel(microliters=microliters, chemical=chemical)

    def drain_vessel(self, drain_volume_ul: float = 40000):
        super().drain_vessel(drain_volume_ul=drain_volume_ul)

    def fast_gas_charge_syringe(self, percent: float = 100):
        super().fast_gas_charge_syringe(percent=percent)

    def run_wash_step(self, duration_s: float, mix_speed_percent: float = 100.,
                      start_empty: bool = True, end_empty: bool = False,
                      **chemical_volumes_ul: float):
        super().run_wash_step(duration_s=duration_s,
                              mix_speed_percent=mix_speed_percent,
                              start_empty=start_empty, end_empty=end_empty,
                              **chemical_volumes_ul)

    def leak_check_syringe_to_selector_common_path(self):
        super().leak_check_syringe_to_selector_common_path()

    def leak_check_syringe_to_drain_exaust_normally_open_path(self):
        super().leak_check_syringe_to_drain_exaust_normally_open_path()

    def leak_check_syringe_to_waste_bypass_path(self):
        super().leak_check_syringe_to_waste_bypass_path()

    def leak_check_syringe_to_reaction_vessel(self):
        super().leak_check_syringe_to_reaction_vessel()

    def _squeeze_and_measure(self, pump_compression_percent: float = None,
                             measurement_time_s: float = 4.0):
        super().squeeze_and_measure(
            pump_compression_percent=pump_compression_percent,
            measurement_time_s=measurement_time_s)

