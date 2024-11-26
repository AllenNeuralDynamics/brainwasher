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

    def __init__(self, multiport_selector, source_pump, waste_pump,
                 tube_length_graph, reaction_vessel):
        """"""
        self.log = logging.getLogger(__name__)
        self.selector = vici
        self.source_pump = source_pump
        self.waste_pump = waste_pump
        self.rxn_vessel = reaction_vessel

        # Assuming the device wasn't stopped with liquid in it, this is safe.
        self.selector.select(selector.ports.waste)
        self.source_pump.reset() # Leaves pump in 0 position.
        # TODO: set waste pump to waste line for waste air access.
        self.waste_pump.reset()

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

    def safe_replace_vessel_solution(self, total_volume_ul: float,
        chemical: str, dilution_factor: Union[int, None] = 100,
        prev_solution_volume_ul: Union[int, None] = None):
        """Similar to :meth:`replace_vessel_solution` except always keep the
        minimum volume of liquid in the reaction vessel above its minimum
        volume."""
        self.replace_vessel_solution(**kwargs,
            min_volume_ul=self.rxn_vessel.min_volume_ul)

    def replace_vessel_solution(self, total_volume_ul: float, chemical: str,
        prev_solution_volume_ul: Union[int, None] = None,
        dilution_factor: Union[int, None] = 100,
        min_volume_ul: float = 0):
        """Replace the solution in the vessel with the specified volume of the
        new chemical. Old solution is dumped to waste.

        :param min_volume_ul: minimum volume that can exist in the reaction
            vessel at any time.

        .. code-block:: python

            # Fill the vessel with 3000uL of isopropyl alcohol and 2000uL of
            # the previous solution.
            bw.replace_vessel_solution(prev_solution_volume=2000,
                                       total_volume_ul=5000,
                                       chemical='isopropyl alcohol')

            # or

            # Fill the vessel up to the 5000uL mark with 100:1 ratio of
            # isopropyl alcohol to the previous solution.
            bw.replace_vessel_solution(dilution_factor=100,
                                       volume_ul=5000,
                                       chemical='isopropyl alcohol')

        """
        start_time_s = now()
        log_data = dict()
        log_data.update(locals()) # Log function args.
        log_data['total_chemical_volume_consumed'] = 0 # Total volume consumed
                                                       # during the chemical
                                                       # exchange.
        # Consolidate representation to prev_solution_volume_ul
        if dilution_factor is not None:
            prev_solution_volume_ul = total_volume_ul / dilution_factor

        # TODO: total volume < reaction vessel max volume.
        if total_volume_ul < min_volume_ul:
            raise ValueError(f"Cannot fill the vessel with {chemical}. "
                f"Specified volume ({total_volume_ul} [uL]) < "
                f"minimum volume ({min_volume_ul} [uL])")
        if all(r is None for r in [dilution_factor, prev_solution_volume]):
            raise ValueError(f"Cannot specify volume exchange in terms of "
                "both dilution_factor and prev_solution_volume")
        if prev_solution_volume_ul is not None:
            if self.rxn_vessel.curr_volume_ul < prev_solution_volume_ul:
                raise ValueError(f"Reaction vessel starting volume is too low.")
        if self.rxn_vessel.curr_volume_ul < prev_solution_volume_ul:
            spec = 'dilution_factor' if dilution_factor is not None else 'prev_solution_volume_ul'
            raise ValueError(f"Previous solution in reaction vessel is too "
                f"low to hit the specified {spec}."
            # FIXME: check if we can't hit the dilution factor with the
            # specified chemistry.
            pass

        new_solution_volume_ul = total_volume_ul - prev_solution_volume_ul

        # FIXME: actually implement this function.
        # Note: if prev_solution_volume_ul < self.rxn_vessel.min_volume_ul, this
        # requires more work.

        # Convert to general representation to extract all "transfers".
        # Consolidate dilution factor and prev_solution_volume_ul
        # FIXME: dilution_factor = 0 (not None)


        log_data['execution_time_s'] = now() - start_time_s
        self.log.info("Metrics.", data=log_data)

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

    def prime_reservoir_line(self, chemical):
        """Fill the specified chemical's flowpath up to the port of the
           selector valve."""
        # purge_source_pump.
        # purge_source_pump_line.
        #
        # Set selector to corresponding chemical port
        # While True:
        #   Withdraw (100%) until reservoir line is tripped.
        #   Set dispensor to waste (or air if we are 100% sure it's just air).
        #   Fully plunge syringe.
        # Set selector to waste.
        # Fully plunge syringe to reset it.
        pass

    def prime_source_pump_line(self, chemical):
        """Fill the selector-to-syringe line flowpath with the specified
            chemical."""
        # Call prime_reservoir_line(chemical)
        # Withdraw up to sensor.
        pass


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

