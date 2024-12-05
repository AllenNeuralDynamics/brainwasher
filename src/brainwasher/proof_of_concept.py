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
                 source_pump, waste_pump,
                 reaction_vessel,
                 pump_selector_valve,
                 source_pump_selector_valve,
                 waste_pump_selector_valve,
                 source_pump_prime_lds,
                 waste_pump_prime_lds
                 #tube_length_grap
                 ):
        """"""
        self.log = logging.getLogger(__name__)
        self.selector = selector
        self.selector_lds_map = selector_lds_map
        self.source_pump = source_pump
        self.waste_pump = waste_pump
        self.rxn_vessel = reaction_vessel
        self.pump_selector_valve = pump_selector_valve
        self.source_pump_selector_valve = source_pump_selector_valve
        self.waste_pump_selector_valve = waste_pump_selector_valve
        self.source_pump_prime_lds = source_pump_prime_lds
        self.waste_pump_prime_lds = waste_pump_prime_lds

        self.prime_volumes_ul = {} # Store how much volume was displaced to
                                   # prime a particular chemical so that we
                                   # can "unprime" it if necessary.


    def reset(self):
        self.log.debug("Connecting Source Pump to waste.")
        self.deenergize_all_valves()
        self.selector.move_to_position("OUTLET")
        # The above cmd connects: source pump -> waste.
        self.source_pump.reset_syringe_position() # Home pump; dispense any liquid to waste.
        # Connect: waste pump -> waste
        self.log.debug("Connecting Waste Pump to waste.")
        self.pump_selector_valve.energize()
        self.waste_pump_selector_valve.energize()
        self.waste_pump.reset_syringe_position() # Home pump; dispense any liquid to waste.
        # Restore deenergized state.
        self.deenergize_all_valves()

    def deenergize_all_valves(self):
        self.log.debug("Deenergizing all solenoid valves.")
        self.pump_selector_valve.deenergize()
        self.source_pump_selector_valve.deenergize()
        self.waste_pump_selector_valve.deenergize()

    def prime_reservoir_line(self, chemical: str,
                             max_pump_displacement_ul: int = 50000):
        """Fill the specified chemical's flowpath up to the port of the
           selector valve. Bail if we exceed max pump distance and no chemical
           is detected."""
        # Configure syringe path to dump air to waste
        self.log.debug(f"Opening source pump path to waste.")
        self.pump_selector_valve.deenergize()
        self.source_pump_selector_valve.deenergize()
        # TODO: purge_source_pump and source pump line

        # Bail-early if we're already primed.
        if self.selector_lds_map[chemical].tripped():
            return
        # Set selector to corresponding chemical port
        self.selector.move_to_position(chemical)
        syringe_volume_ul = self.source_pump.syringe_volume_ul
        remaining_volume_ul = max_pump_displacement_ul
        # Withdraw (100%) until reservoir line is tripped.
        # Track how much total volume we displaced so we can bail on fail.
        while self.selector_lds_map[chemical].untripped() and remaining_volume_ul:
            # Withdraw another stroke.
            self.log.debug("Withdrawing reservoir contents.")
            stroke_volume_ul = min(remaining_volume_ul, syringe_volume_ul)
            self.source_pump.withdraw(stroke_volume_ul)
            # Poll syringe for lds state change. Kill if sensor is tripped.
            while self.syringe_pump.is_busy():
                if self.selector_lds_map[chemical].untripped():
                    continue
                self.source_pump.halt()
                remaining_volume_ul -= self.syringe_pump.get_position_ul()
                break
            remaining_volume_ul -= stroke_volume_ul
            # Reset syringe stroke by purging displaced air to waste.
            self.log.debug("Resetting source pump stroke.")
            self.selector.move_to_position("OUTLET")
            self.source_pump.move_absolute_in_percent(0) # Plunge
            # Return to chemical line.
            self.selector.move_to_position(chemical)
        if not remaining_volume_ul and self.selector_lds_map[chemical].untripped():
            raise RuntimeError("Withdrew maximum volume and no liquid detected.")
        displaced_volume_ul = max_pump_displacement_ul - remaining_volume_ul
        self.prime_volumes_ul[chemical] = displaced_volume_ul
        self.log.debug(f"Priming {chemical} complete. "
                       f"Function displaced {displaced_volume_ul}[uL].")

    def prime_source_pump_line(self, chemical):
        """Fill the selector-to-syringe line flowpath with the specified
            chemical."""
        self.prime_reservoir_line(chemical)
        if self.source_pump_lds.tripped():
            return
        # Withdraw to source pump sensor.
        # We can do this in <1 full stroke after the chemical is primed.
        self.log.debug("Withdrawing reservoir contents.")
        self.source_pump.withdraw(stroke_volume_ul/2) # FIXME: magic number
        while self.syringe_pump.is_busy():
            if self.source_pump_lds.untripped():
                continue
            self.source_pump.halt()
        if self.source_pump_lds.untripped():
            raise RuntimeError("Did not detect any liquid after attempting "
                               "to prime up to the start of the source pump.")

    def purge_source_pump(self, dest="waste"):
        """Empty contents of source pump to waste. Fully plunge pump."""
        # If the source pump is fully plunged, exit.
        # Select dest line.
        # Fully plunge syringe.
        pass

    def purge_source_pump_line(self, dest="waste"):
        """Purge the current contents of the pump-to-select line flowpath
            to the appropriate waste. Fully plunge pump."""
        self.purge_source_pump(dest) # Do this first, or the line will remain
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

