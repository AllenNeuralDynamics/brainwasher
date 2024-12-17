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


    def reset(self):
        """Initialize all hardware while ensuring that the system can bleed any
        pressure pockets created to waste."""
        self.deenergize_all_valves()
        self.log.debug("Connecting Source Pump to waste.")
        # Connect: source pump -> waste.
        self.drain_exhaust_valve.energize()
        self.selector.move_to_position("OUTLET")
        self.pump.reset_syringe_position() # Home pump; dispense any liquid to waste.
        # Restore deenergized state.
        self.deenergize_all_valves()

    def deenergize_all_valves(self):
        self.log.debug("Deenergizing all solenoid valves.")
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.drain_exhaust_valve.deenergize()
        self.drain_waste_valve.deenergize()

    def prime_reservoir_line(self, chemical: str,
                             max_pump_displacement_ul: int = 25000):
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
        # Set selector to corresponding chemical port
        self.selector.move_to_position(chemical)
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
            # Return to chemical line.
            self.selector.move_to_position(chemical)
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
        while remaining_volume_ul:
            # Withdraw another stroke.
            stroke_volume_ul = min(remaining_volume_ul, syringe_volume_ul)
            self.log.debug("Withdrawing N2.")
            self.selector.move_to_position("AMBIENT") # Select gas.
            self.pump.withdraw(stroke_volume_ul) # Withdraw gas.
            self.selector.move_to_position(chemical) # Select chemical.
            self.pump.move_absolute_in_percent(0) # Plunge to starting position.
            remaining_volume_ul -= stroke_volume_ul
        self.log.info(f"Unpriming {chemical} complete.")

    def prime_pump_line(self, chemical):
        """Fill the selector-to-syringe line flowpath with the specified
            chemical."""
        self.prime_reservoir_line(chemical)
        if self.pump_lds.tripped():
            # Edge case: what happens if another chemical is in the line?
            self.log.debug("Exiting early. {chemical} already primed.")
            return
        # Withdraw to source pump sensor.
        # We can do this in <1 full stroke after the chemical is primed.
        self.log.debug("Withdrawing reservoir contents.")
        self.pump.withdraw(stroke_volume_ul/2) # FIXME: magic number
        while self.pump.is_busy():
            if self.pump.untripped():
                continue
            self.pump.halt()
        if self.pump_lds.untripped():
            raise RuntimeError("Did not detect any liquid after attempting "
                               "to prime up to the start of the source pump.")

    def purge_pump(self, dest="waste"):
        """Empty contents of source pump to waste. Fully plunge pump."""
        # If the source pump is fully plunged, exit.
        # Select dest line.
        # Fully plunge syringe.
        pass

    def purge_pump_line(self, dest="waste"):
        """Purge the current contents of the pump-to-select line flowpath
            to the appropriate waste. Fully plunge pump."""
        self.purge_pump(dest) # Do this first, or the line will remain
                                     # full until the source pump is empty.
        # If source pump line is clear at this point, exit.
        # Set selector to air.
        # Withdraw full volume of air + liquid.
        # Note: we *must* con
        # Select dest line.
        # If destination is not waste:
        #   Identify syringe line chemical.
        #   Select corresponding reservoir line.
        #   Purge syringe line contents back into reservoir.
        pass

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

