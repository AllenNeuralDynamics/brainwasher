"""Tissue-clearing proof-of-concept"""

import logging
from brainwasher.protocol import Protocol
from functools import wraps
from pathlib import Path
from runze_control.syringe_pump import SY08
from time import perf_counter as now
from time import sleep
from threading import Event, Thread
from typing import Union


def syringe_empty(func):
    """Ensure that the syringe is empty (i.e: fully plunged)."""

    @wraps(func) # required for sphinx doc generation
    def inner(self, *args, **kwds):
        if self.pump.get_position_ul() != 0:
            error_msg = "Error. Pump is not starting from its reset position " \
                "and contains liquid or gas!"
            self.log.error(error_msg)
            raise RuntimeError(error_msg)
        return func(self, *args, **kwds)
    return inner


class FlowChamber:

    """Class for controlling/maintaining the FlowChamber.

    Note that functions should work whether an "empty" reaction vessel is
    installed (i.e: for cleaning) or a normal reaction vessel with tissue is
    installed.

    """

    def __init__(self, selector, selector_lds_map,
                 pump,
                 reaction_vessel,
                 mixer,
                 pressure_sensor,
                 rv_source_valve,
                 rv_exhaust_valve,
                 drain_exhaust_valve,
                 drain_waste_valve,
                 pump_prime_lds,
                 #tube_length_graph
                 ):
        """"""
        self.log = logging.getLogger(__name__)
        self.selector = selector
        self.selector_lds_map = selector_lds_map
        self.pump = pump
        self.rxn_vessel = reaction_vessel
        self.mixer = mixer
        self.pressure_sensor = pressure_sensor
        self.rv_source_valve = rv_source_valve
        self.rv_exhaust_valve = rv_exhaust_valve
        self.drain_exhaust_valve = drain_exhaust_valve
        self.drain_waste_valve = drain_waste_valve
        self.pump_prime_lds = pump_prime_lds

        self.prime_volumes_ul = {} # Store how much volume was displaced to
                                   # prime a particular chemical so that we
                                   # can "unprime" it if necessary.
        self.pump_is_primed_with = None

        self.nominal_pump_speed_percent = 10
        self.slow_pump_speed_percent = 5
        self.pump_unprime_speed_percent = 30
        # Thread control
        self.monitoring_pressure = Event()
        self.pressure_monitor_thread = None

    def reset(self):
        """Initialize all hardware while ensuring that the system can bleed any
        pressure pockets created to waste."""
        self.log.info("Resetting instrument.")
        self.deenergize_all_valves()
        self.log.debug("Connecting Source Pump to waste.")
        # Connect: source pump -> waste.
        self.drain_exhaust_valve.energize()
        self.selector.move_to_position("OUTLET")
        self.pump.reset_syringe_position() # Home pump; dispense any liquid to waste.
        # TODO: slow down pump speed here.
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        # Restore deenergized state.
        self.deenergize_all_valves()

    def deenergize_all_valves(self):
        self.log.debug("Deenergizing all solenoid valves.")
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.drain_exhaust_valve.deenergize()
        self.drain_waste_valve.deenergize()

    def start_pressure_monitor(self):
        if self.monitoring_pressure.is_set():
            return
        self.monitoring_pressure.set()
        self.pressure_monitor_thread = Thread(target=self._monitor_pressure_worker,
                                              daemon=True)
        self.pressure_monitor_thread.start()

    def stop_pressure_monitor(self):
        if not self.monitoring_pressure.is_set():
            return
        self.monitoring_pressure.clear()
        self.pressure_monitor_thread.join()
        self.pressure_monitor_thread = None

    def _monitor_pressure_worker(self):
        while self.monitoring_pressure.is_set():
            print(self.pressure_sensor.get_pressure_psig())
            sleep(0.5)

    @syringe_empty
    def prime_reservoir_line(self, chemical: str,
                             max_pump_displacement_ul: int = 12500):
        """Fill the specified chemical's flowpath up to the port of the
           selector valve. Bail if we exceed max pump distance and no chemical
           is detected."""
        # TODO: consider a force parameter to prime anyway up to a fixed volume.
        # Bail-early if we're already primed.
        if chemical in self.prime_volumes_ul:
            self.log.warning(f"{chemical} was previously primed. Aborting.")
            return
        # Bail-early if we're already primed.
        if self.selector_lds_map[chemical].tripped():
            self.log.warning(f"{chemical} already primed. Aborting.")
            return
        self.log.info(f"Priming {chemical} reservoir line.")
        # Configure syringe path to dump air to waste
        self.log.debug(f"Opening pump path to waste.")
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.drain_exhaust_valve.energize()
        syringe_volume_ul = self.pump.syringe_volume_ul
        remaining_volume_ul = max_pump_displacement_ul
        # Withdraw (100%) until reservoir line is tripped.
        # Track how much total volume we displaced so we can bail on fail.
        # Note: add small fudge factor since we can be +/- 1 step (~2.0833uL).
        liquid_detected = False
        while (not liquid_detected) and (remaining_volume_ul > 5):
            # Withdraw another stroke.
            if self.selector_lds_map[chemical].tripped():
                liquid_detected = True
                break
            stroke_volume_ul = min(remaining_volume_ul, syringe_volume_ul)
            self.log.debug("Polling prime sensor while withdrawing up to "
                           f"{stroke_volume_ul}[uL] of {chemical}.")
            # Select chemical line.
            self.selector.move_to_position(chemical)
            self.pump.withdraw(stroke_volume_ul, wait=False)
            # Temporarily remove pump log message spam.
            old_log_level = self.pump.log.level # save current log level.
            self.pump.log.setLevel(logging.INFO) # Unset Debug level (if set) for pump.
            # Poll syringe for lds state change. Kill if sensor is tripped.
            while self.pump.is_busy():
                if self.selector_lds_map[chemical].untripped():
                    continue
                self.log.debug("Halting pump mid-stroke.")
                self.pump.halt()
                liquid_detected = True
                break
            self.pump.log.setLevel(old_log_level) # Restore pump log level.
            # subtact off however much volume we actually withdrew.
            remaining_volume_ul -= self.pump.get_position_ul()
            # Reset syringe stroke by purging displaced air to waste.
            self.log.debug("Removing displaced gas.")
            self.selector.move_to_position("OUTLET")
            self.pump.move_absolute_in_percent(0) # Plunge to starting position.
        if not remaining_volume_ul and not liquid_detected:
            raise RuntimeError("Withdrew maximum volume "
                f"({max_pump_displacement_ul}[uL]) and no liquid detected.")
        self.drain_exhaust_valve.deenergize()
        displaced_volume_ul = max_pump_displacement_ul - remaining_volume_ul
        # Save displaced volume.
        self.prime_volumes_ul[chemical] = displaced_volume_ul
        self.log.info(f"Priming {chemical} complete. Function displaced "
            f"{displaced_volume_ul:.3f}[uL] of volume.")

    @syringe_empty
    def unprime_reservoir_line(self, chemical: str,
                               max_pump_displacement_ul: int = 25000):
        """Unprime reservoir line by using N2 to push back volume used to prime
           (+10%) or max_pump_displacement_ul if unspecified."""
        self.log.info(f"Unpriming {chemical} reservoir line.")
        if chemical not in self.prime_volumes_ul:
            self.log.warning(f"{chemical} has never been primed before. "
                f"Unpriming will displace {max_pump_displacement_ul}[uL].")
        unprime_volume_ul = self.prime_volumes_ul.get(chemical,
                                                      max_pump_displacement_ul)
        # Add 5% for good measure, but stay below alotted maximum.
        unprime_volume_ul = min(unprime_volume_ul*1.05, # FIXME: magic number
                                max_pump_displacement_ul)
        # Displace volume in discrete pump strokes.
        syringe_volume_ul = self.pump.syringe_volume_ul
        remaining_volume_ul = unprime_volume_ul
        # Speed up pump for purging.
        self.pump.set_speed_percent(self.pump_unprime_speed_percent)
        while remaining_volume_ul:
            # Withdraw another stroke.
            stroke_volume_ul = min(remaining_volume_ul, syringe_volume_ul)
            self.fast_gas_charge_syringe()
            self.selector.move_to_position(chemical) # Select chemical.
            self.pump.move_absolute_in_percent(0) # Plunge to starting position.
            remaining_volume_ul -= stroke_volume_ul
        self.pump_is_primed_with = None  # Clear prime line state.
        # Reset speed.
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        if chemical in self.prime_volumes_ul:
            del self.prime_volumes_ul[chemical] # Remove record of chemical.
        self.log.info(f"Unpriming {chemical} complete.")

    @syringe_empty
    def prime_pump_line(self, chemical: str):
        """Fill the selector-to-syringe line flowpath with the specified
            chemical."""
        self.prime_reservoir_line(chemical)
        # FIXME: store this state in software in case we are at the edge
        #  of the sensor trip threshold.
        if self.pump_is_primed_with: #self.pump_prime_lds.tripped():
            # Edge case: what happens if another chemical is in the line?
            self.log.warning(f"Pump line already primed with "
                             f"{self.pump_is_primed_with}.")
            return
        self.log.info(f"Priming pump line with {chemical}.")
        self.selector.move_to_position(chemical) # Select chemical.
        # Withdraw to source pump sensor.
        # We can do this in <1 full stroke after the chemical is primed.
        self.log.debug(f"Withdrawing {chemical} from reservoir.")
        self.pump.set_speed_percent(self.slow_pump_speed_percent)
        # Temporarily remove pump log message spam.
        old_log_level = self.pump.log.level # save current log level.
        self.pump.log.setLevel(logging.INFO) # Unset Debug level (if set) for pump.
        self.pump.withdraw(self.pump.syringe_volume_ul/3, wait=False) # FIXME: magic number
        while self.pump.is_busy():
            if self.pump_prime_lds.untripped():
                continue
            self.pump.halt()
            self.log.debug("Priming pump line detected liquid after displacing "
                f"{self.pump.get_position_ul()}[uL].")
            # Restore speed
            self.pump.set_speed_percent(self.nominal_pump_speed_percent)
            self.pump.log.setLevel(old_log_level) # Restore pump log level.
            self.pump_is_primed_with = f"{chemical}"
            return
        raise RuntimeError(f"Did not detect any liquid ({chemical}) after "
            "attempting to aspirate to the start of the pump.")

    # It is OK if the pump does not enter this function with an empty syringe.
    def purge_pump_line(self):
        """Empty selector-to-pump line by purging contents to waste.
        It is OK if the pump does not enter this function fully-plunged.
        """
        self.log.debug("Purging pump line.")
        # Configure syringe path to dump air to waste
        self.log.debug(f"Opening pump path to waste.")
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.drain_exhaust_valve.energize()
        try:
            # Purge all starting contents of the syringe.
            if self.pump.get_position_ul() != 0:
                self.log.warning("Syringe is not empty. Directing existing "
                    "contents to waste.")
                # Select dest line.
                self.selector.move_to_position("OUTLET")
                # Fully plunge syringe.
                self.pump.move_absolute_in_percent(0)
            self.log.debug("Pulling residual pump line contents into syringe "
                "with N2.")
            # Charge pump with N2.
            self.fast_gas_charge_syringe()
            # Select dest line.
            self.log.debug("Purging pump line contents to waste.")
            self.selector.move_to_position("OUTLET")
            # Fully plunge syringe.
            self.pump.move_absolute_in_percent(0)
        finally:
            # Close waste flowpath.
            self.drain_exhaust_valve.deenergize()
        self.log.debug("Purging pump line complete.")
        self.pump_is_primed_with = None

    def dispense_to_vessel(self, microliters: float, chemical: str):
        """Withdraw specified chemical from the appropriate container and
        dispense it into the reaction vessel."""
        # Safety checks:
        if microliters + self.rxn_vessel.curr_volume_ul > self.rxn_vessel.max_volume_ul:
            raise ValueError("Requested dispense amount would exceed vessel capacity.")
        # State checks:
        if chemical not in self.selector_lds_map:
            raise ValueError(f"{chemical} is not a valid chemical.")
        if chemical not in self.prime_volumes_ul:
            self.log.warning(f"{chemical} has not yet been primed. Priming now.")
            self.prime_reservoir_line(chemical)
        self.prime_pump_line(chemical) # Prime pump line.
        # Set outlet flowpath starting configuration.
        self.rv_source_valve.energize()
        self.rv_exhaust_valve.energize()
        self.drain_exhaust_valve.energize()
        self.selector.move_to_position(chemical)
        pump_to_common_dv_ul = 10.0 # FIXME: magic number. get this from a graph.
        # Subtract off pump-to-common dead volume because we will introduce
        # this volume back when we fully purge the pump-to-vessel flowpath.
        self.pump.withdraw(microliters - pump_to_common_dv_ul)
        self.selector.move_to_position("OUTLET")
        # Fully plunge. Note: some liquid will remain in the pump-to-vessel
        # path at this point.
        self.log.debug(f"Plunging initial {microliters - pump_to_common_dv_ul}[uL].")
        self.pump.move_absolute_in_percent(0)
        self.log.debug(f"Plunging remaining {pump_to_common_dv_ul}[uL]"
                       f"(pump-to-vessel dead volume) to clear line and "
                       f"fully dispense {microliters}[uL].")
        # Now push residual liquid out of pump-to-vessel line using gas.
        # This adds pump_to_common_dv_ul and bypasses any dead volume.
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        purge_volumes = [15, 5]  # FIXME: magic numbers.
        for purge_volume in purge_volumes:
            self.fast_gas_charge_syringe(purge_volume)
            # Select dest line.
            self.selector.move_to_position("OUTLET")
            # Fully plunge syringe.
            self.pump.move_absolute_in_percent(0)
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        # Update State:
        self.pump_is_primed_with = None  # Clear prime line state.
        self.rxn_vessel.curr_volume_ul += microliters
        # Seal reaction vessel and all other flowpaths.
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.drain_exhaust_valve.deenergize()
        self.log.debug(f"Dispensed {microliters}[uL] into reaction vessel. "
                       f"Prime line is now cleared.")

    @syringe_empty
    def drain_vessel(self, drain_volume_ul: float = 40000):
        """Drain the reaction vessel."""
        # Set outlet flowpath starting configuration.
        self.rv_source_valve.energize()
        self.rv_exhaust_valve.deenergize()  # Lock out the rv top exhaust port.
        self.drain_waste_valve.energize()  # Open rv lower drain path.
        self.pump.set_speed_percent(100)
        # Pump the pump through the specified volume with gas.
        # Note: gas is compressible, so the volume displaced is less than
        #   the volume movement of the pump.
        syringe_volume_ul = self.pump.syringe_volume_ul
        remaining_volume_ul = drain_volume_ul
        while remaining_volume_ul:
            # Withdraw another stroke.
            stroke_volume_ul = min(remaining_volume_ul, syringe_volume_ul)
            stroke_percent = stroke_volume_ul/syringe_volume_ul * 100.
            # Push out the vessel contents with gas.
            self.fast_gas_charge_syringe(stroke_percent)
            # Select dest line.
            self.selector.move_to_position("OUTLET")
            # Fully plunge syringe.
            self.pump.move_absolute_in_percent(0)
            remaining_volume_ul -= stroke_volume_ul
            sleep(0.5)  # Wait for liquid to finish moving (system to hit equilibrium).
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        # Update State:
        self.rxn_vessel.curr_volume_ul = 0
        # Close valves
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.drain_waste_valve.deenergize()

    def fast_gas_charge_syringe(self, percent: float = 100):
        """quickly charge the syringe with gas."""
        self.log.debug(f"Fast-charging pump to {percent}% volume with gas.")
        self.selector.move_to_position("AMBIENT")
        old_speed = self.pump.get_speed_percent()
        self.pump.set_speed_percent(100)  # draw up gas quickly.
        self.pump.move_absolute_in_percent(percent)
        self.pump.set_speed_percent(old_speed) # restore original speed.

    def run_wash_step(self, duration_s: float, mix_speed_percent: float = 100.,
                      start_empty: bool = True, end_empty: bool = False,
                      **chemical_volumes_ul: float):
        """Drain (optional), mix, and empty (opt) the reaction vessel to
        complete one wash cycle.

        :param duration_s: time in seconds to mix.
        :param mix_speed_percent: percent [0-100.0] to mix the chemicals during
            the mix step.
        :param start_empty: if True, drain the vessel before introducing new
            liquids.
        :param end_empty: if True, draing the vessel after mixing.
        :param chemical_volumes: dict, keyed by chemical name of chemical
            amount in microliters.

        .. note::
           It is possible to call this function with *no* chemicals specified
           and `start_empty=False` i.e: for a pure-mixing step.

        .. note::
           It is possible to call this function with *no* mixing time and
           `end_empty=False` i.e: a pure fill step.

        .. note::
           It is possible to call this function with *no* mixing speed i.e:
           a pure passive exposure step.
        """
        # Validate chemicals.
        common_chemicals = self.selector_lds_map.keys() & chemical_volumes_ul.keys()
        used_chemicals = set(chemical_volumes_ul.keys())
        if len(common_chemicals) < len(used_chemicals):
            unrecognized_chemicals = common_chemicals ^ used_chemicals
            raise ValueError(f"Unrecognized chemicals: {unrecognized_chemicals}.")
        # Drain if requested.
        if start_empty and self.rxn_vessel.curr_volume_ul > 0:
            self.drain_vessel()
        # Fill
        for chemical_name, ul in chemical_volumes_ul.items():
            self.dispense_to_vessel(ul, chemical_name)
        try:
            self.mixer.set_mixing_speed(mix_speed_percent)
        except NotImplementedError:
            self.log.debug("Mixer does not support speed control. Skipping.")
        if mix_speed_percent > 0:
            self.mixer.start_mixing()
        # Wait.
        sleep(duration_s)
        if mix_speed_percent > 0:
            self.mixer.stop_mixing()
        # Drain (if required).
        if end_empty:
            self.drain_vessel()

    def mix(self, duration_s: int, mix_speed_percent: float = 100.0):
        self.run_wash_step(duration_s=duration_s, mix_speed_percent=mix_speed_percent,
                           start_empty=False, end_empty=False)

    def fill(self, empty_first=False, **chemical_volumes_ul: float):
        self.run_wash_step(duration_s=0, mix_speed_percent=0, start_empty=empty_first,
                           end_empty=False, **chemical_volumes_ul)

    def run_protocol(self, path: Path):
        protocol = Protocol(path)
        protocol.validate()
        for step in range(protocol.step_count):
            duration_s = protocol.get_duration_s(step)
            chemical_volumes_ul = protocol.get_solution(step,
                                                        max_volume_ul=self.rxn_vessel.max_volume_ul)
            self.log.info(f"Conducting step: {step}/{protocol.step_count} with {chemical_volumes_ul}")
            mix_speed_percent = protocol.get_mix_speed_percent(step)
            self.run_wash_step(duration_s=duration_s,
                               mix_speed_percent=mix_speed_percent,
                               start_empty=True, end_empty=False,
                               **chemical_volumes_ul)

    def clean_system(self):
        pass