"""Tissue-clearing proof-of-concept"""

import logging
from runze_control.syringe_pump import SY08
from time import perf_counter as now
from typing import Union


class FlowChamber:

    """Class for controlling/maintaining the FlowChamber.

    Note that functions should work whether an "empty" reaction vessel is
    installed (i.e: for cleaning) or a normal reaction vessel with tissue is
    installed.

    """

    def __init__(self, selector, selector_lds_map,
                 pump,
                 reaction_vessel,
                 rv_source_valve,
                 rv_exhaust_valve,
                 drain_exhaust_valve,
                 drain_waste_valve,
                 pump_prime_lds,
                 #tube_length_grap
                 ):
        """"""
        self.log = logging.getLogger(__name__)
        self.selector = selector
        self.selector_lds_map = selector_lds_map
        self.pump = pump
        self.rxn_vessel = reaction_vessel
        self.rv_source_valve = rv_source_valve
        self.rv_exhaust_valve = rv_exhaust_valve
        self.drain_exhaust_valve = drain_exhaust_valve
        self.drain_waste_valve = drain_waste_valve
        self.pump_prime_lds = pump_prime_lds

        self.prime_volumes_ul = {} # Store how much volume was displaced to
                                   # prime a particular chemical so that we
                                   # can "unprime" it if necessary.

        self.nominal_pump_speed_percent = 10
        self.slow_pump_speed_percent = 5
        self.pump_unprime_speed_percent = 30


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

    def prime_reservoir_line(self, chemical: str,
                             max_pump_displacement_ul: int = 12500):
        """Fill the specified chemical's flowpath up to the port of the
           selector valve. Bail if we exceed max pump distance and no chemical
           is detected."""
        # Bail-early if we're already primed.
        if self.selector_lds_map[chemical].tripped():
            self.log.debug(f"{chemical} already primed. Exiting early.")
            return
        # Error if the pump is not reset to 0 position.
        starting_pump_volume_ul = self.pump.get_position_ul()
        if starting_pump_volume_ul != 0:
            self.log.error("Error. Pump is not starting from reset position "
                           "and may contain another chemical.")
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
            f"{displaced_volume_ul:.3f}[uL] of gas.")

    def unprime_reservoir_line(self, chemical: str,
                               max_pump_displacement_ul: int = 25000):
        """Unprime reservoir line by using N2 to push back volume used to prime
           (+10%) or max_pump_displacement_ul if unspecified."""
        # Error if the pump is not reset to 0 position.
        starting_pump_volume_ul = self.pump.get_position_ul()
        if starting_pump_volume_ul != 0:
            error_msg = "Error. Pump is not starting from its reset position " \
                "and may contain another chemical."
            self.log.error(error_msg)
            raise RuntimeError(error_msg)
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
            self.log.debug("Withdrawing N2.")
            self.selector.move_to_position("AMBIENT") # Select gas.
            self.pump.withdraw(stroke_volume_ul) # Withdraw gas.
            self.selector.move_to_position(chemical) # Select chemical.
            self.pump.move_absolute_in_percent(0) # Plunge to starting position.
            remaining_volume_ul -= stroke_volume_ul
        # Reset speed.
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        self.log.info(f"Unpriming {chemical} complete.")

    def prime_pump_line(self, chemical):
        """Fill the selector-to-syringe line flowpath with the specified
            chemical."""
        if self.pump.get_position_ul() != 0:
            error_msg = "Error. Pump is not starting from its reset position " \
                "and may contain another chemical."
            self.log.error(error_msg)
            raise RuntimeError(error_msg)
        self.prime_reservoir_line(chemical)
        if self.pump_prime_lds.tripped():
            # Edge case: what happens if another chemical is in the line?
            self.log.warning("Exiting early. {chemical} already primed.")
            return
        self.selector.move_to_position(chemical) # Select chemical.
        # Withdraw to source pump sensor.
        # We can do this in <1 full stroke after the chemical is primed.
        self.log.debug(f"Withdrawing {chemical} from reservoir.")
        self.pump.set_speed_percent(self.slow_pump_speed_percent)
        self.pump.withdraw(self.pump.syringe_volume_ul/3) # FIXME: magic number
        while self.pump.is_busy():
            if self.pump_prime_lds.untripped():
                continue
            self.pump.halt()
            self.log.debug("Priming pump line detected liquid after displacing "
                f"{self.pump.get_position_ul()}[uL].")
            # Restore speed
            self.pump.set_speed_percent(self.nominal_pump_speed_percent)
            return
        raise RuntimeError(f"Did not detect any liquid ({chemical}) after "
            "attempting to aspirate to the start of the pump.")

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
            # Select N2
            self.selector.move_to_position("AMBIENT")
            # Fully withdraw syringe to bring primed liquid into syringe.
            self.pump.move_absolute_in_percent(100)
            # Select dest line.
            self.log.debug("Purging pump line contents to waste.")
            self.selector.move_to_position("OUTLET")
            # Fully plunge syringe.
            self.pump.move_absolute_in_percent(0)
        finally:
            # Close waste flowpath.
            self.drain_exhaust_valve.deenergize()
        self.log.debug("Purging pump line complete.")


    def transfer(self, volume_ul, source, destination):
        """Transfer the specified amount of liquid from source to destination.

        .. code-block:: python

            bw.transfer(volume_ul=10000,
                        source=bw.reservoirs["isopropyl alchohol"],
                        dest=bw.reaction_vessel)

        """
        # TODO: account for path lengths.
        # TODO: push stirring state. Stop stirring. Pop Stirring state when done.
        pass

    #def safe_replace_vessel_solution(self, total_volume_ul: float,
    #    chemical: str, dilution_factor: Union[int, None] = 100,
    #    prev_solution_volume_ul: Union[int, None] = None):
    #    """Similar to :meth:`replace_vessel_solution` except always keep the
    #    minimum volume of liquid in the reaction vessel above its minimum
    #    volume."""
    #    self.replace_vessel_solution(**kwargs,
    #        min_volume_ul=self.rxn_vessel.min_volume_ul)

    #def replace_vessel_solution(self, total_volume_ul: float, chemical: str,
    #    prev_solution_volume_ul: Union[int, None] = None,
    #    dilution_factor: Union[int, None] = 100,
    #    min_volume_ul: float = 0):
    #    """Replace the solution in the vessel with the specified volume of the
    #    new chemical. Old solution is dumped to waste.

    #    :param min_volume_ul: minimum volume that can exist in the reaction
    #        vessel at any time.

    #    .. code-block:: python

    #        # Fill the vessel with 3000uL of isopropyl alcohol and 2000uL of
    #        # the previous solution.
    #        bw.replace_vessel_solution(prev_solution_volume=2000,
    #                                   total_volume_ul=5000,
    #                                   chemical='isopropyl alcohol')

    #        # or

    #        # Fill the vessel up to the 5000uL mark with 100:1 ratio of
    #        # isopropyl alcohol to the previous solution.
    #        bw.replace_vessel_solution(dilution_factor=100,
    #                                   volume_ul=5000,
    #                                   chemical='isopropyl alcohol')

    #    """
    #    start_time_s = now()
    #    log_data = dict()
    #    log_data.update(locals()) # Log function args.
    #    log_data['total_chemical_volume_consumed'] = 0 # Total volume consumed
    #                                                   # during the chemical
    #                                                   # exchange.
    #    # Consolidate representation to prev_solution_volume_ul
    #    if dilution_factor is not None:
    #        prev_solution_volume_ul = total_volume_ul / dilution_factor

    #    # TODO: total volume < reaction vessel max volume.
    #    if total_volume_ul < min_volume_ul:
    #        raise ValueError(f"Cannot fill the vessel with {chemical}. "
    #            f"Specified volume ({total_volume_ul} [uL]) < "
    #            f"minimum volume ({min_volume_ul} [uL])")
    #    if all(r is None for r in [dilution_factor, prev_solution_volume]):
    #        raise ValueError(f"Cannot specify volume exchange in terms of "
    #            "both dilution_factor and prev_solution_volume")
    #    if prev_solution_volume_ul is not None:
    #        if self.rxn_vessel.curr_volume_ul < prev_solution_volume_ul:
    #            raise ValueError(f"Reaction vessel starting volume is too low.")
    #    if self.rxn_vessel.curr_volume_ul < prev_solution_volume_ul:
    #        spec = 'dilution_factor' if dilution_factor is not None else 'prev_solution_volume_ul'
    #        raise ValueError(f"Previous solution in reaction vessel is too "
    #            f"low to hit the specified {spec}."
    #        # FIXME: check if we can't hit the dilution factor with the
    #        # specified chemistry.
    #        pass

    #    new_solution_volume_ul = total_volume_ul - prev_solution_volume_ul

    #    # FIXME: actually implement this function.
    #    # Note: if prev_solution_volume_ul < self.rxn_vessel.min_volume_ul, this
    #    # requires more work.

    #    # Convert to general representation to extract all "transfers".
    #    # Consolidate dilution factor and prev_solution_volume_ul
    #    # FIXME: dilution_factor = 0 (not None)


    #    log_data['execution_time_s'] = now() - start_time_s
    #    self.log.info("Metrics.", data=log_data)



    def aspirate(self, microliters):
        pass

    def dispense(self, microliters):
        pass


    #@liquid_level_check
    def dispense_reservoir_to_chamber(self, microliters, chemical):
        """Withdraw specified chemical from the appropriate container and
        dispense it into the reaction vessel."""
        pass

    def dispense_chamber_to_waste(self):
        pass

    def run_schedule(self):
        pass

    def load_state(self, state):
        pass

    def save_state(self):
        pass

