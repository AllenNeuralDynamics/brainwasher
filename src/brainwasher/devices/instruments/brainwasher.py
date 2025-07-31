"""Tissue-clearing proof-of-concept"""

import _thread  # To kill the main thread from a child thread.
import logging
import yaml

from brainwasher.devices.vessels import Vessel, ReactionVessel, WasteVessel
from brainwasher.devices.mixer import Mixer
from brainwasher.devices.liquid_presence_detection import BubbleDetectionSensor
from brainwasher.devices.sequent_microsystems.valve import NCValve, ThreeTwoValve
from brainwasher.devices.pressure_sensor import PressureSensor
from brainwasher.devices.valves.closeable_vici import CloseableVICI
from brainwasher.errors.instrument_errors import LeakCheckError
from brainwasher.protocol import Protocol
from brainwasher.job import Job
from datetime import timedelta
from functools import wraps
from pathlib import Path
from runze_control.syringe_pump import SyringePump
from time import sleep
from time import perf_counter as now
from threading import Event, Thread, RLock, current_thread


SIMULATED = False

def lock_flowpath(func):
    """Provide methods with exclusive access to components that alter the flowpath."""
    @wraps(func) # required for sphinx doc generation
    def inner(self, *args, **kwds):
        with self.flowpath_lock:
            self.log.debug(f"Locking flowpath to "
                           f"{current_thread().name} for {func.__name__} fn.")
            return func(self, *args, **kwds)
    return inner

def syringe_empty(func):
    """Ensure that the syringe is empty (i.e: fully plunged)."""

    @wraps(func) # required for sphinx doc generation
    def inner(self, *args, **kwds):
        self.log.debug("Ensuring syringe is empty.")
        # MiniSY04 does not always return exactly 0.
        pump_position_ul = self.pump.get_position_ul()
        if abs(pump_position_ul) > self.PUMP_APPROX_ZERO_UL:
            error_msg = "Error. Pump is not starting from its reset position (~0) " \
                f"and contains liquid or gas! abs(position) = {pump_position_ul}[uL]"
            self.log.error(error_msg)
            raise RuntimeError(error_msg)
        return func(self, *args, **kwds)
    return inner


class BrainWasher:

    """Class for controlling/maintaining the FlowChamber.

    Note that functions should work whether an "empty" reaction vessel is
    installed (i.e: for cleaning) or a normal reaction vessel with tissue is
    installed.

    """

    PUMP_APPROX_ZERO_UL =  30.0 #12.5
    MAX_SAFE_PRESSURE_PSIG = 13.0
    MAX_PURGE_PRESSURE_PSIG = 8.0
    LEAK_CHECK_SQUEEZE_PERCENT = 15.
    MIN_LEAK_CHECK_STARTING_PRESSURE_PSIG = 1.0
    MAX_LEAK_CHECK_PRESSURE_DELTA_PSIG = 0.10  # Max permissable relative change
                                               # in pressure during leak checks.

    def __init__(self, selector: CloseableVICI,
                 selector_lds_map: dict[str, int],
                 pump: SyringePump,
                 reaction_vessel: ReactionVessel,
                 mixer: Mixer,
                 pressure_sensor: PressureSensor,
                 rv_source_valve: ThreeTwoValve,
                 rv_exhaust_valve: ThreeTwoValve,
                 waste_vessels: list[WasteVessel],
                 output_bypass_valves: list[NCValve],
                 waste_drain_valves: list[NCValve],
                 pump_prime_lds: BubbleDetectionSensor,
                 starting_state: dict = None,
                 #tube_length_graph
                 ):
        """
        :param waste_vessels: list of waste vessels, each of which may have
            different compatible chemicals that can be added to it.
        :param waste_drain_valves: list of valves gating each waste vessel.
            Valve order must match the order of the waste vessels.

        """
        self.log = logging.getLogger(self.__class__.__name__)
        self.selector = selector
        self.selector_lds_map = selector_lds_map
        self.pump = pump
        self.rxn_vessel = reaction_vessel
        self.waste_vessels: list = waste_vessels
        self.mixer = mixer
        self.pressure_sensor = pressure_sensor
        self.rv_source_valve = rv_source_valve
        self.rv_exhaust_valve = rv_exhaust_valve
        self.output_bypass_valves = output_bypass_valves # liquids and vapors to waste.
        self.waste_drain_valves = waste_drain_valves  # reaction vessel waste drain valve.
        self.pump_prime_lds = pump_prime_lds

        self.prime_volumes_ul = {} # Store how much volume was displaced to
                                   # prime a particular chemical so that we
                                   # can "unprime" it if necessary.
        self.pump_is_primed_with = None

        self.nominal_pump_speed_percent = 20
        self.slow_pump_speed_percent = 10
        self.pump_unprime_speed_percent = 60
        self.pump_purge_speed_percent = 100
        # Pressure Monitor Thread control
        self.monitoring_pressure = Event()
        self.buffer_samples = Event()
        self.pressure_sample_buffer = []
        self.pressure_monitor_thread = None
        self.pressure_avg_start_time_s = 0
        self.pressure_avg_duration_s = 0
        self.pressure_psig = 0
        self._validate_setup()
        # Protocol Thread control
        self.job_worker = None
        # Thread-safe protection within a class instance.
        self.flowpath_lock = RLock()
        # Pause Control
        self.pause_requested = Event()
        self.resume_state_overrides = {}
        # Launch pressure monitor thread.
        self.start_pressure_monitor()

    def _validate_setup(self):
        # Ensure names match in selector port map and bds port map
        # names in the bds port map should be a subset of names in the
        selector_lds_map_keys = set(self.selector_lds_map.keys())
        selector_port_map_keys = set(self.selector.port_map.keys())
        # selector port map.
        if not (selector_lds_map_keys <= selector_port_map_keys):
            raise RuntimeError("Key names in selector port map and bds map do "
                               "not match!")
        # "ambient" and "outlet" must exist in the selector port map.
        required_ports = {"ambient", "outlet"}
        if not (required_ports <= selector_port_map_keys):
            raise RuntimeError("The selector port map must include the "
                               f"followig named ports: {required_ports}")

    @property
    def plumbed_chemicals(self):
        """Chemicals that the instrument is currently plumbed with."""
        return set(self.selector_lds_map.keys())

    @lock_flowpath
    def reset(self):
        """Initialize all hardware while ensuring that the system can bleed any
        pressure pockets created to waste."""
        self.log.info("Resetting instrument.")
        self.mixer.stop_mixing()
        self.deenergize_all_valves()
        try:
            # Connect: source pump -> waste.
            # FIXME: we need to know what we're purging.
            #   We need to write out state to a file.
            self.log.debug("Connecting pump to waste.")
            self.log.error("Dumping unknown pump contents to unknown waste.")
            self.output_bypass_valves[0].energize()
            self.selector.move_to_port("outlet")
            self.pump.reset_syringe_position() # Home pump; dispense contents to waste.
            self.pump.set_speed_percent(self.nominal_pump_speed_percent)
            # Restore deenergized state.
        finally:
            self.deenergize_all_valves()

    def halt(self):
        # FIXME: do we need the flowpath_lock here??
        # FIXME: do we need to tell child threads to stop?
        # FIXME: do we need to check if protocol is running?
        self.log.warning("Halting and disabling all active components.")
        try:
            if self.pump.is_busy():
                self.pump.halt()
        except Exception:
            self.log.critical("Error halting pump.")
        self.deenergize_all_valves()
        self.mixer.stop_mixing()

    @lock_flowpath
    def deenergize_all_valves(self):
        self.log.debug("Deenergizing all solenoid valves.")
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        for valve in self.output_bypass_valves:
            valve.deenergize()
        for valve in self.waste_drain_valves:
            valve.deenergize()

    def start_pressure_monitor(self):
        if self.monitoring_pressure.is_set():
            return
        self.monitoring_pressure.set()
        self.pressure_monitor_thread = Thread(target=self._monitor_pressure_worker,
                                              name="pressure_monitor_worker",
                                              daemon=True)
        self.pressure_monitor_thread.start()

    def stop_pressure_monitor(self):
        if not self.monitoring_pressure.is_set():
            return
        self.monitoring_pressure.clear()
        self.pressure_monitor_thread.join()
        self.pressure_monitor_thread = None

    def get_average_psig(self, duration_s: float):
        # Set event to stuff samples into an array.
        self.pressure_sample_buffer = []  # clear old samples.
        self.pressure_avg_start_time_s = now()
        self.pressure_avg_duration_s = duration_s
        self.buffer_samples.set()
        # Wait for event to clear.
        while self.buffer_samples.is_set():
            sleep(0.01)
        return sum(self.pressure_sample_buffer)/len(self.pressure_sample_buffer)

    def _monitor_pressure_worker(self):
        """Pressure monitor thread that ensures system stays below maximum
        pressure and aborts otherwise.
        """
        while self.monitoring_pressure.is_set():
            pressure_psig = self.pressure_sensor.get_pressure_psig()
            self.pressure_psig = pressure_psig
            if self.buffer_samples.is_set():
                self.pressure_sample_buffer.append(pressure_psig)
                if (now() - self.pressure_avg_start_time_s)\
                        > self.pressure_avg_duration_s:
                    self.buffer_samples.clear()
            if self.pressure_psig > self.MAX_SAFE_PRESSURE_PSIG:
                error_msg = "Jam detected!! Aborting syringe movement."
                self.log.critical(error_msg)
                self.halt()
                _thread.interrupt_main()
            sleep(0.01)

    def get_compatible_waste_vessel_id(self, *chemicals: str) -> int | None:
        """Given a series of chemicals, return a waste vessel chemically
        compatible to store the solution contents. If multiple are
        compatible, return the vessel with the most spare volume."""
        if not chemicals:
            self.log.warning("Reaction vessel is empty. Any waste vessel is "
                             "compatible.")
        # A solution is chemically compatible if its components are a subset
        # of the vessel's compatible components.
        waste_compatibility = [set(chemicals) <= wv.compatible_chemicals
                               for wv in self.waste_vessels]
        # None are compatible: bail early.
        if not any(waste_compatibility):
            self.log.error(f"No compatible waste found for: {chemicals}.")
            return None
        # Both are compatible! Return the one with less liquid or the first if equal.
        if waste_compatibility.count(True) == len(self.waste_vessels):
            volumes = [wv.curr_volume_ul for wv in self.waste_vessels]
            return volumes.index(min(volumes))
        # Only one or the other are compatible.
        return waste_compatibility.index(True)

    def reset_waste_vessel(self, index: int):
        """Update the specified waste vessel volume to empty."""
        self.waste_vessels[index].purge_solution()

    @lock_flowpath
    @syringe_empty
    def prime_reservoir_line(self, chemical: str,
                             max_pump_displacement_ul: int = 12500):
        """Fill the specified chemical's flowpath up to the port of the
           selector valve. Bail if we exceed max pump distance and no chemical
           is detected."""
        # TODO: consider a force parameter to prime anyway up to a fixed volume.
        # Bail-early if we're already primed.
        if chemical in self.prime_volumes_ul:
            self.log.warning(f"{chemical} reservoir line already primed. Aborting.")
            return
        # Bail-early if we're already primed.
        if (not SIMULATED) and self.selector_lds_map[chemical].tripped():
            self.log.warning(f"{chemical} reservoir line detected prematurely "
                             f"as primed. Aborting.")
            self.prime_volumes_ul[chemical] = 0
            return
        waste_id = self.get_compatible_waste_vessel_id(chemical)
        self.log.info(f"Priming {chemical} reservoir line.")
        # Configure syringe path to dump air to waste
        self.log.debug(f"Opening pump path to waste.")
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.output_bypass_valves[waste_id].energize()
        syringe_volume_ul = self.pump.syringe_volume_ul
        remaining_volume_ul = max_pump_displacement_ul
        # Withdraw (100%) until reservoir line is tripped.
        # Track how much total volume we displaced so we can bail on fail.
        # Note: add small fudge factor since we can be +/- 1 step (~2.0833uL).
        liquid_detected = False
        while (not liquid_detected) and (remaining_volume_ul > 5):
            if SIMULATED:
                break
            # Withdraw another stroke.
            if self.selector_lds_map[chemical].tripped():
                liquid_detected = True
                break
            stroke_volume_ul = min(remaining_volume_ul, syringe_volume_ul)
            self.log.debug("Polling prime-reservoir sensor while withdrawing up to "
                           f"{stroke_volume_ul}[uL] of {chemical}.")
            # Select chemical line.
            self.selector.move_to_port(chemical)
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
            # Subtract off however much volume we actually withdrew.
            remaining_volume_ul -= self.pump.get_position_ul()
            # Reset syringe stroke by purging displaced air to waste.
            self.log.debug("Removing displaced gas.")
            self.selector.move_to_port("outlet")
            self.pump.move_absolute_in_percent(0) # Plunge to starting position.
        # Ensure we leave with the pump fully plunged.
        if self.pump.get_position_ul() != 0:
            self.log.debug("Post-priming, removing displaced gas.")
            self.selector.move_to_port("outlet")
            # Bugfix. The pump appears to ignore small movement commands near 0.
            # Since priming may put the pump in a position near zero, we reset
            # to ensure we're at 0.
            self.pump.reset_syringe_position()
        self.output_bypass_valves[waste_id].deenergize()
        if not remaining_volume_ul and not liquid_detected:
            raise RuntimeError("Withdrew maximum volume "
                f"({max_pump_displacement_ul}[uL]) and no liquid detected.")
        displaced_volume_ul = max_pump_displacement_ul - remaining_volume_ul
        # Save displaced volume.
        self.prime_volumes_ul[chemical] = displaced_volume_ul
        self.log.info(f"Priming {chemical} complete. Function displaced "
            f"{displaced_volume_ul:.3f}[uL] of volume.")

    @lock_flowpath
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
        syringe_capacity_ul = self.pump.syringe_volume_ul
        remaining_volume_ul = unprime_volume_ul
        # Speed up pump for purging.
        self.pump.set_speed_percent(self.pump_unprime_speed_percent)
        while remaining_volume_ul:
            self.log.debug(f"Remaining volume to displace: {remaining_volume_ul}[uL]")
            # Withdraw another stroke.
            stroke_volume_ul = min(remaining_volume_ul, syringe_capacity_ul)
            self.fast_gas_charge_syringe()
            self.selector.move_to_port(chemical) # Select chemical.
            self.pump.move_absolute_in_percent(0) # Plunge to starting position.
            remaining_volume_ul -= stroke_volume_ul
        self.pump_is_primed_with = None  # Clear prime line state.
        # Reset speed.
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        if chemical in self.prime_volumes_ul:
            del self.prime_volumes_ul[chemical] # Remove record of chemical.
        self.log.info(f"Unpriming {chemical} complete.")

    @lock_flowpath
    @syringe_empty
    def prime_pump_line(self, chemical: str):
        """Fill the selector-to-syringe line flowpath with the specified
            chemical."""
        if SIMULATED:
            self.log.warning(f"Skipping priming pump in simulation.")
            self.pump_is_primed_with = f"{chemical}"
            return
        if chemical not in self.prime_volumes_ul:
            self.prime_reservoir_line(chemical)
        # FIXME: store this state in software in case we are at the edge
        #  of the sensor trip threshold.
        if self.pump_is_primed_with:
            # Edge case: what happens if another chemical is in the line?
            self.log.warning(f"Pump line already primed with "
                             f"{self.pump_is_primed_with}.")
            return
        self.log.debug(f"Priming pump line with {chemical}.")
        self.selector.move_to_port(chemical) # Select chemical.
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

    @lock_flowpath
    def purge_pump_line(self, chemical: str, destination: Vessel,
                        full_cycles: int = 1, gas_cycles: int = 0):
        """Empty selector-to-pump line by purging contents to destination.

        .. Note::
           It is OK if the pump does not enter this function fully-plunged.

        """
        self.log.debug("Purging pump line.")
        # Configure syringe path to dump air to waste
        self.log.debug(f"Opening pump path to waste.")
        waste_id = self.get_compatible_waste_vessel_id(chemical)
        if destination == self.rxn_vessel:
            self.rv_source_valve.energize()
            self.rv_exhaust_valve.energize()
        else:  # Bypass rxn vessel to waste.
            self.rv_source_valve.deenergize()
            self.rv_exhaust_valve.deenergize()
        self.output_bypass_valves[waste_id].energize()
        self.pump.set_speed_percent(self.pump_purge_speed_percent)
        try:
            # Purge all starting contents of the syringe.
            if self.pump.get_position_ul() != 0:
                self.log.warning(f"Directing existing contents to {destination.name}.")
                # Select dest line.
                self.selector.move_to_port("outlet")
                # Fully plunge syringe.
                self.pump.move_absolute_in_percent(0)
            if full_cycles:
                self.log.debug("Pulling residual pump line contents into "
                               "syringe with N2.")
            for cycle in range(full_cycles):
                # Charge pump with N2.
                self.fast_gas_charge_syringe()
                # Select dest line.
                self.log.debug("Purging pump line contents to waste.")
                self.selector.move_to_port("outlet")
                # Fully plunge syringe.
                self.pump.move_absolute_in_percent(0)
            # Optional: Purge with Gas
            #   Create a pressure pocket by squeezing the syringe with the
            #   selector closed and then opening it to relieve the pressure
            #   to waste to blow away droplets.
            # Note: PV = nRT. As we make the total volume smaller, for the same
            # starting pressure, the same pump displacement builds up more
            # pressure, so we must check the pressure to stay under a safe limit.
            for cycle in range(gas_cycles):
                # Charge pump with N2.
                self.fast_gas_charge_syringe()
                # Select dest line.
                self.log.debug("Purging pump line contents to waste.")
                self.selector.move_to_port("outlet")
                remaining_volume_ul = self.pump.get_position_ul()
                while remaining_volume_ul > self.PUMP_APPROX_ZERO_UL:
                    self.log.debug(f"remaining volume: {remaining_volume_ul:.3f} [uL]")
                    self.log.debug("Sealing syringe flowpath")
                    self.selector.close()
                    self.log.debug("Pressurizing syringe volume.")
                    self.pump.move_absolute_in_percent(0, wait=False)
                    while self.pump.is_busy():
                        if (self.pressure_psig > self.MAX_PURGE_PRESSURE_PSIG):
                            self.pump.halt()
                            self.pump.is_busy() # Dump busy state to logs.
                            break  # For some reason halt may not always clear busy?
                        sleep(0.05)
                    remaining_volume_ul = self.pump.get_position_ul()
                    self.log.debug("Releasing pressure to outlet.")
                    self.selector.open()
                    sleep(0.5)
            ## Ensure we're fully reset, not just hovering at the "0" error margin.
            #self.pump.move_absolute_in_percent(0)
            # Bugfix. The pump appears to ignore small movement commands near 0.
            # Since priming may put the pump in a position near zero, we reset
            # to ensure we're at 0.
            self.pump.reset_syringe_position()
        finally:
            # Close waste flowpath.
            self.output_bypass_valves[waste_id].deenergize()
        self.log.debug("Purging pump line complete.")
        self.pump_is_primed_with = None

    @lock_flowpath
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
        waste_id = self.get_compatible_waste_vessel_id(chemical)
        self.prime_pump_line(chemical) # Prime pump line.
        self.log.info(f"Dispensing {microliters}uL of {chemical} to vessel.")
        # Set outlet flowpath starting configuration.
        self.rv_source_valve.energize()
        self.rv_exhaust_valve.energize()
        self.output_bypass_valves[waste_id].energize()
        self.selector.move_to_port(chemical)
        pump_to_common_dv_ul = 10.0 # FIXME: magic number. get this from a graph.
        # Subtract off pump-to-common dead volume because we will introduce
        # this volume back when we fully purge the pump-to-vessel flowpath.
        self.pump.withdraw(microliters - pump_to_common_dv_ul)
        self.selector.move_to_port("outlet")
        # Fully plunge. Note: some liquid will remain in the pump-to-vessel
        # path at this point.
        self.log.debug(f"Plunging initial {microliters - pump_to_common_dv_ul}[uL].")
        self.pump.move_absolute_in_percent(0)
        self.log.debug(f"Plunging remaining {pump_to_common_dv_ul}[uL]"
                       f"(pump-to-vessel dead volume) to clear line and "
                       f"fully dispense {microliters}[uL].")
        # Now push residual liquid out of pump-to-vessel line using gas.
        # This adds pump_to_common_dv_ul and bypasses any dead volume.
        self.purge_pump_line(self.pump_is_primed_with,
                             destination=self.rxn_vessel, gas_cycles=1)
        ## Update State:
        self.rxn_vessel.add_solution(**{chemical: microliters})
        self.pump_is_primed_with = None
        # Seal reaction vessel and all other flowpaths.
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.output_bypass_valves[waste_id].deenergize()
        self.log.debug(f"Dispensed {microliters}[uL] into reaction vessel. "
                       f"Prime line is now cleared.")

    @lock_flowpath
    @syringe_empty
    def drain_vessel(self, drain_volume_ul: float = 40000):
        """Drain the reaction vessel."""
        msg = ("Draining vesssel" +
                f" of {self.rxn_vessel.solution}." if self.rxn_vessel.solution else ".")
        self.log.info(msg)
        # Select chemically-compatible flowpath depending on the waste contents.
        components = set(self.rxn_vessel.solution.keys())
        waste_id = self.get_compatible_waste_vessel_id(*components)
        self.log.debug(f"Waste contents will be discarded to "
                       f"{self.waste_vessels[waste_id].name}.")
        # Set outlet flowpath starting configuration.
        self.rv_source_valve.energize()
        self.rv_exhaust_valve.deenergize()  # Lock out the rv top exhaust port.
        self.waste_drain_valves[waste_id].energize()  # Open rv lower drain path.
        self.pump.set_speed_percent(self.pump_purge_speed_percent)
        # Pump through the specified volume with gas.
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
            self.selector.move_to_port("outlet")
            # Fully plunge syringe.
            self.pump.move_absolute_in_percent(0)
            remaining_volume_ul -= stroke_volume_ul
            sleep(0.5)  # Wait for liquid to finish moving (system to hit equilibrium).
        self.pump.set_speed_percent(self.nominal_pump_speed_percent)
        # Update State:
        self.rxn_vessel.purge_solution()
        # Close valves
        self.rv_source_valve.deenergize()
        self.rv_exhaust_valve.deenergize()
        self.waste_drain_valves[waste_id].deenergize()

    @lock_flowpath
    def fast_gas_charge_syringe(self, percent: float = 100):
        """quickly charge the syringe with gas."""
        self.log.debug(f"Fast-charging pump to {percent}% volume with gas.")
        self.selector.move_to_port("ambient")
        old_speed = self.pump.get_speed_percent()
        self.pump.set_speed_percent(100)  # draw up gas quickly.
        self.pump.move_absolute_in_percent(percent)
        self.pump.set_speed_percent(old_speed) # restore original speed.

    @lock_flowpath
    def run_wash_step(self, duration_s: float = 0, mix_speed_rpm: float = 0,
                      intermittent_mixing_on_time_s: float = None,
                      intermittent_mixing_off_time_s: float = None,
                      start_empty: bool = True, end_empty: bool = False,
                      **solution: dict):
        """Drain (optional), mix, and empty (opt) the reaction vessel to
        complete one wash cycle.

        :param duration_s: time in seconds to mix.
        :param mix_speed_rpm: speed (in rpm) to mix the chemicals during
            the mixing step.
        :param intermittent_mixing_on_time_s: if specified greater-than-0
            along with `intermittent_mixing_off_time_s`,
            the time the mixer will be turned on intermittently.
        :param intermittent_mixing_off_time_s: if specified greater-than-0,
            along with `intermittent_mixing_on_time_s`,
            the time the mixer will be turned off intermittently.
        :param start_empty: if True, drain the vessel before introducing new
            liquids.
        :param end_empty: if True, draing the vessel after mixing.
        :param solution: dict, keyed by chemical name of chemical
            amount in microliters.

        .. note::
           If both `intermittent_mixing_on_time_s` and
           `intermittent_mixing_on_time_s` are specified,
           mixing will cycle between mixing for the
           `intermittent_mixing_on_time_s` and stopping for the
           `intermittent_mixing_off_time_s`.

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
        # Decide if we will use intermittent mixing.
        slow_mix_times = [intermittent_mixing_on_time_s,
                          intermittent_mixing_off_time_s]
        intermittent_mixing = all([i is not None for i in slow_mix_times])
        # Validate chemicals.
        #common_chemicals = self.selector_lds_map.keys() & solution.keys()
        used_chemicals = set(solution.keys())
        common_chemicals = self.plumbed_chemicals & used_chemicals
        if len(common_chemicals) < len(used_chemicals):
            unrecognized_chemicals = common_chemicals ^ used_chemicals
            raise ValueError(f"Unrecognized chemicals: {unrecognized_chemicals}.")
        # Drain if requested.
        if start_empty: # and self.rxn_vessel.curr_volume_ul > 0:
            self.drain_vessel()
        # Fill
        if len(solution):
            self.log.info(f"Filling vessel with solution: {solution}.")
        for chemical_name, ul in solution.items():
            self.dispense_to_vessel(ul, chemical_name)
        if mix_speed_rpm > 0:
            try:
                self.mixer.set_mixing_speed(mix_speed_rpm)
            except NotImplementedError:
                self.log.warning("Mixer does not support speed control. "
                                 "Skipping speed setting.")
                mix_speed_rpm = self.mixer.rpm_range[1]
        # Produce a sensible log message depending on what we're going to do.
        if (mix_speed_rpm > 0) and (duration_s > 0):
            intermittent_mixing_msg = ""
            if intermittent_mixing:
                intermittent_mixing_msg = (f" with intermittent mixing "
                    f"strategy: on for {intermittent_mixing_on_time_s}[sec], "
                    f"off for {intermittent_mixing_off_time_s}[sec]")
            self.log.info(f"Mixing for {duration_s} seconds at {mix_speed_rpm}"
                          f"[rpm]" + intermittent_mixing_msg + ".")
        elif duration_s > 0:
            self.log.info(f"Idling for {duration_s} seconds.")
        start_time_s = now()
        if mix_speed_rpm > 0:
            self.mixer.start_mixing()
        # Wait while implementing intermittent mixing strategy.
        while (now() - start_time_s) < duration_s:
            # Handle pause request if called in a "job" context.
            if self.job_worker and self.job_worker.is_alive() and self.pause_requested.is_set():
                elapsed_time_s = round(now() - start_time_s)
                action_msg = "mixing" if mix_speed_rpm else "idling"
                self.log.warning(f"Aborting after {elapsed_time_s}[s] of {action_msg}.")
                self.resume_state_overrides.update(duration_s=(duration_s - elapsed_time_s))
                return
            if not intermittent_mixing:
                sleep(0.010)
                continue
            sleep(intermittent_mixing_on_time_s)
            self.mixer.stop_mixing()
            sleep(intermittent_mixing_off_time_s)
            self.mixer.start_mixing()
        if mix_speed_rpm > 0:
            self.mixer.stop_mixing()
        # Drain (if required).
        if end_empty:
            self.drain_vessel()

    @lock_flowpath
    def mix(self, duration_s: int, mix_speed_rpm: float = 1000,
            intermittent_mixing_on_time_s: float = None,
            intermittent_mixing_off_time_s: float = None):
        self.run_wash_step(duration_s=duration_s, mix_speed_rpm=mix_speed_rpm,
            intermittent_mixing_on_time_s=intermittent_mixing_on_time_s,
            intermittent_mixing_off_time_s=intermittent_mixing_off_time_s,
            start_empty=False, end_empty=False)

    @lock_flowpath
    def fill(self, empty_first: bool = False, **solution: float):
        self.run_wash_step(duration_s=0, mix_speed_rpm=0, start_empty=empty_first,
                           end_empty=False, **solution)

    def create_job(self, job_path: str, source: str = None):
        """Create a job file from path pointing to a protocol or existing job.
        If not source is specified, create and return an empty job.

        :param job_path: the filepath to save the job
        :param source: the url or path pointing to an existing protocol from which
            to create the job or None to create an empty job file.
        """
        job_path = Path(job_path)
        source_path = Path(source)
        # Create from an empty job (default).
        if not job_path.exists():
            job = Job(name=job_path.stem)  # Name without suffix
            with open(job_path) as job_file:
                yaml.dump(job.model_dump(exclude_none=True), job_file)
            self.log.info(f"Created an empty job file.")
            return
        # Create from an existing job.
        if source_path.suffix.lower() in ["yaml", "yml"]:
            with open(source_path) as source_job, open(job_path) as job_file:
                job_dict = yaml.safe_load(source_job)
                job = Job(**job_dict)  # validate
                job.purge_history()
                job.set_source_protocol(source_path)
                yaml.dump(job.model_dump(exclude_none=True), job_file)
                self.log.info(f"Created job file from an existing job file.")
                return
        # Create from a csv-style protocol.
        if job_path.suffix.lower() == "csv":
            protocol = Protocol(job_path)
            # TODO: create a job from the protocol
            raise NotImplementedError("Cannot convert csv files to jobs yet!")
            #yaml.dump(job.model_dump(exclude_none=True), job_path)

    def validate_job_against_instrument(self, job: Job):
        """Validate that the job can be executed on this instrument configuration"""
        # TODO: validate that we have enough space in the waste vessels to
        #  run the entire job.
        # Ensure all solution volumes fit in reaction vessel
        volume_errors = []
        for index, step in enumerate(job.protocol):
            if step.solution_volume_ul > self.rxn_vessel.max_volume_ul:
                msg = (f"Step {index}: solution total volume "
                       f"({step.solution_volume_ul} [uL]) exceeds reaction "
                       f"vessel volume ({self.rxn_vessel.max_volume_ul} [uL]).")
                self.log.error(msg)
                volume_errors.append(msg)
        if volume_errors:
            raise ValueError("Job volumes are not compatible with the size "
                             "of the instrument reaction vessel: "
                             f"{volume_errors}.")
        # Ensure required chemicals are plumbed.
        if not job.chemicals <= self.plumbed_chemicals:
            raise ValueError(f"Job chemicals are not plumbed on the machine; "
                             f"Job chemicals: {job.chemicals}, "
                             f"loaded chemicals: {self.plumbed_chemicals}.")
        # Ensure each step solution can be dumped to a compatible waste vessel.
        waste_compatibility_errors = []
        for index, step in enumerate(job.protocol):
            components = set(step.solution.keys())
            # Find at least one vessel that the solution can be dumped.
            solution_has_valid_waste = self.get_compatible_waste_vessel_id(*components)
            if solution_has_valid_waste is None:
                msg = f"Step {index} solution has no designated waste. " \
                      f"Solution components: {components}. "
                self.log.error(msg)
                waste_compatibility_errors.append(msg)
        if waste_compatibility_errors:
            raise ValueError("Job is not chemically compatible with waste "
                             f"vessels. The following steps cannot be dumped "
                             f"to any waste vessel: {waste_compatibility_errors}")
        self.log.info(f"Job passed validation against instrument capabilities.")

    def _load_job(self, job_path: str) -> Job:
        job_path = Path(job_path)
        if not job_path.exists():
            raise FileNotFoundError(f"Job does not exist at location: "
                                    f"{job_path.resolve()}")
        with open(job_path) as yaml_stream:
            self.log.debug(f"Loading job from: {job_path.absolute()}")
            job_dict = yaml.safe_load(yaml_stream)
            logging.debug(f"Validating job from file.")
            job = Job(**job_dict)  # validate
            logging.debug(f"Job is a valid job.")
            return job

    def run(self, job_path: str):
        """Run the job specified from the specified filepath."""
        if self.job_worker and self.job_worker.is_alive():
            raise ValueError("Cannot run another job while an existing "
                             "job is running.")
        job = self._load_job(job_path)
        self.validate_job_against_instrument(job)
        logging.debug(f"Launching job worker thread.")
        # Run job in a separate thread to lock out flowpath
        # and support pause/resume control.
        self.job_worker = Thread(target=self._run_job_worker,
                                 name="run_job_worker",
                                 args=[job, Path(job_path)],
                                 daemon=True)
        self.job_worker.start()

    @lock_flowpath
    def _run_job_worker(self, job: Job, job_path: Path):
        """Start or resume a job from job_path"""
        # When starting/resuming, ensure the current rxn vessel solution is
        # either unspecified (assume user filled it with correct starting solution)
        # or matches the job starting solution (user instructed machine to fill
        # it with the correct starting solution).
        if job.resume_state:
            start_step = job.resume_state.step
            start_step_overrides = job.resume_state.overrides
            starting_or_resuming_msg = "Resuming"
            if not self.rxn_vessel.solution: # assume unspecified.
                self.rxn_vessel.add_solution(**job.resume_state.starting_solution)
            if self.rxn_vessel.solution != job.resume_state.starting_solution:
                raise ValueError("When resuming, reaction vessel starting "
                                 "solution does not match the correct resume "
                                 "state starting solution.")
            job.clear_resume_state()
            job.record_resume()
        else:
            start_step = 0
            start_step_overrides = None
            starting_or_resuming_msg = "Starting"
            if not self.rxn_vessel.solution: # assume unspecified.
                self.rxn_vessel.add_solution(**job.starting_solution)
            if  self.rxn_vessel.solution != job.starting_solution:
                raise ValueError("When starting, reaction vessel starting "
                                 "solution does not match the correct resume "
                                 "state starting solution.")
            job.record_start()
        log_msg = f"{starting_or_resuming_msg} job: '{job.name}'"
        if start_step > 0:
            log_msg += f" at step {start_step+1}."  # Steps in logs are 1-indexed.
        else:
            log_msg += ". "
        log_msg += f"Job should take {timedelta(seconds=job.get_duration_s(start_step))}."
        self.log.info(log_msg)
        # Execute the protocol.
        for index, step in enumerate(job.protocol[start_step:], start=start_step):
            resume_step = index # Save resume step in case of unhandled exception.
            try:
                # Apply overrides (recursive) on the first (ie resume) step only.
                if index == start_step and start_step_overrides:
                    step = step.model_copy(update=start_step_overrides)
                    self.log.info(f"Applying overrides to starting step: "
                                  f"{start_step_overrides}.")
                # Convert step parameters to valid function parameters.
                kwargs = step.model_dump(exclude='solution')  # omit **solution
                kwargs.update(step.solution)  # splat **solution
                self.log.info(f"Conducting step: "
                              f"{index + 1}/{len(job.protocol)} with "
                              f"{step.solution}")
                # Run step.
                self.run_wash_step(**kwargs)
                # Handle pause state.
                # Save current step if not completed (overrides present) or
                # next step if the current step completed.
                resume_step = index if self.resume_state_overrides else index + 1
                if self.pause_requested.is_set():
                    # Note: steps are 1-indexed when referenced in logs.
                    self.log.warning(f"Pausing system at step {resume_step+1}.")
                    job.record_pause()
                    self.pause_requested.clear()
                    self.log.info(f"System paused.")
                    return  # Will execute finally block first.
            finally:
                # Always save the current step in case of an unhandled exception
                # or power failure.
                job.save_resume_state(resume_step, step.solution,
                                      **self.resume_state_overrides)
                self.resume_state_overrides = {}
                with open(job_path, "w") as job_file:
                    yaml.dump(job.model_dump(exclude_none=True), job_file)
                self.log.debug(f"Job progress saved to: {job_path}")
        job.clear_resume_state()
        job.record_finish()
        with open(job_path, "w") as job_file:
            yaml.dump(job.model_dump(exclude_none=True), job_file)
        self.log.info(f"Finished job: {job.name} from {job_path}")

    def pause(self):
        """Request that the system pause the currently running protocol and
        save the protocol path and current step to the config."""
        if self.job_worker is None or not self.job_worker.is_alive():
            self.log.error("Ignoring pause request. System is not running a protocol.")
            return
        self.log.info("Requesting system pause.")
        self.pause_requested.set()

    def abort(self):
        raise NotImplementedError

    @lock_flowpath
    def run_leak_checks(self):
        """Leak check the entire system.

        :raises RuntimeError: upon the leak check that failed.
        """
        self.log.info("Running leak checks in order of increasing volume.")
        # Leak checks run in order can isolate leaks down to a small number
        # of fittings/seals that need to be checked.
        self.leak_check_syringe_to_selector_common_path()
        self.leak_check_syringe_to_rv_exaust_normally_open_path()
        self.leak_check_syringe_to_waste_bypass_path()
        self.leak_check_syringe_to_reaction_vessel()

    @lock_flowpath
    @syringe_empty
    def leak_check_syringe_to_selector_common_path(self):
        """Test for leaks between the syringe pump and selector common position.

        :raises LeakCheckError: upon failure.
        """
        # Withdraw N2.
        self.fast_gas_charge_syringe(30)
        try:
            self.log.debug("Creating closed volume.")
            self.deenergize_all_valves()
            self.selector.close()
            # Measure:
            self._squeeze_and_measure()
            self.log.debug("Leak check passed.")
        except LeakCheckError:
            msg = "Flowpath between syringe pump and selector common outlet is leaking."
            self.log.error(msg)
            raise
        finally:
            self.selector.open()
            # Reset syringe
            self._purge_gas_filled_syringe()
        self.log.info("leak check passed: syringe -> <- selector common path.")

    @lock_flowpath
    def leak_check_syringe_to_rv_exaust_normally_open_path(self):
        try:
            self.log.debug("Creating closed volume.")
            self.deenergize_all_valves()
            self.rv_exhaust_valve.energize()
            self.fast_gas_charge_syringe(30)
            self.selector.move_to_port("outlet")
            # Measure:
            self._squeeze_and_measure()
            self.log.debug("Leak check passed.")
        except LeakCheckError:
            msg = "Flowpath between syringe pump and normally-open position of" \
                  "output bypass valve is leaking."
            self.log.error(msg)
            raise
        finally:
            self._purge_gas_filled_syringe()
        self.log.info("leak check passed: syringe -><- reaction vessel exhaust NO path.")

    @lock_flowpath
    def leak_check_syringe_to_waste_bypass_path(self):
        try:
            self.log.debug("Creating closed volume.")
            self.deenergize_all_valves()
            self.fast_gas_charge_syringe(30)
            self.selector.move_to_port("outlet")
            # Measure:
            self._squeeze_and_measure()
            self.log.debug("Leak check passed.")
        except LeakCheckError:
            msg = "Flowpath between syringe pump and closed output bypass valve" \
                  "is leaking."
            self.log.error(msg)
            raise
        finally:
            self._purge_gas_filled_syringe()
        self.log.info("leak check passed: syringe -><- output bypass path.")

    @lock_flowpath
    def leak_check_syringe_to_reaction_vessel(self):
        try:
            self.log.debug("Creating closed volume.")
            self.deenergize_all_valves()
            self.rv_source_valve.energize()
            self.fast_gas_charge_syringe(30)
            self.selector.move_to_port("outlet")
            # Measure:
            self._squeeze_and_measure()
            self.log.debug("Leak check passed.")
        except LeakCheckError:
            msg = "Flowpath between syringe pump and sealed reaction vessel" \
                  "is leaking."
            self.log.error(msg)
            raise
        finally:  # Cleanup. Purge compressed air everywhere.
            self._purge_gas_filled_syringe()
            # Purge reaction vessel.
            self.log.debug("Depressurizing reaction vessel")
            vapor_components = set(self.rxn_vessel.solution.keys())
            waste_vessel_id = self.get_compatible_waste_vessel_id(*vapor_components)
            # TODO: waste_vessel_id could be None but shouldn't be at this point.
            self.output_bypass_valves[waste_vessel_id].energize()
            self.rv_exhaust_valve.energize()
            sleep(0.5)
            self.output_bypass_valves[waste_vessel_id].deenergize()
            self.rv_exhaust_valve.deenergize()
        self.log.info("leak check passed: syringe -><- reaction vessel path.")

    @lock_flowpath
    def _squeeze_and_measure(self, pump_compression_percent: float = None,
                             measurement_time_s: float = 4.0):
        """Compress the syringe by `pump_compression_percent` and
        measure the chnage in pressure to flag if a leak is present.

        :raises LeakCheckError: upon detecting a leak.
        """
        # Apply defaults.
        if pump_compression_percent is None:
            pump_compression_percent = self.LEAK_CHECK_SQUEEZE_PERCENT
        # Get uncompressed pressure volume.
        pump_position_percent = self.pump.get_position_percent()
        pump_compressed_position_percent = (pump_position_percent
                                            - pump_compression_percent)
        if pump_compressed_position_percent < 0:
            raise ValueError("Cannot compress pump beyond full travel range.")
        uncompressed_pressure = self.get_average_psig(1)
        self.log.debug(f"Uncompressed pressure: {uncompressed_pressure:.3f}")
        # Compress N2.
        self.log.debug("Squeezing closed volume.")
        self.pump.move_absolute_in_percent(pump_compressed_position_percent)
        # Monitor starting pressure and pressure change.
        sleep(1)
        compressed_pressure = self.get_average_psig(1)
        self.log.debug(f"Compressed pressure: {compressed_pressure:.3f}")
        if ((compressed_pressure - uncompressed_pressure)
                < self.MIN_LEAK_CHECK_STARTING_PRESSURE_PSIG):
            raise LeakCheckError("Syringe cannot create a positive relative "
                                 "pressure within the starting volume.")
        start_time_s = now()
        while now() - start_time_s < measurement_time_s:
            curr_pressure = self.get_average_psig(0.5)
            delta = abs(compressed_pressure - curr_pressure)
            self.log.debug(f"Pressure delta: {delta:.3f}")
            if delta > self.MAX_LEAK_CHECK_PRESSURE_DELTA_PSIG:
                raise LeakCheckError("Pressure change is significant enough"
                                     "to indicate a leak.")

    @lock_flowpath
    def _purge_gas_filled_syringe(self):
        self.log.debug("Purging gas-filled syringe to waste.")
        self.deenergize_all_valves()
        vapor_components = set(self.rxn_vessel.solution.keys())
        waste_vessel_id = self.get_compatible_waste_vessel_id(*vapor_components)
        # TODO: waste_vessel_id could be None but shouldn't be at this point.
        self.output_bypass_valves[waste_vessel_id].energize()
        self.pump.move_absolute_in_percent(0)
        self.output_bypass_valves[waste_vessel_id].deenergize()
