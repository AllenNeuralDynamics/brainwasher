"""Elveflow fluid selector multiplexer device."""

import logging
import math
import time
from typing import Optional, List, Dict, Union
from mixology.devices.selector.selector import SerialSelector, SerialSelectorConfig
from mixology.devices.simulated_devices.selector import SimSelector
import serial
from pydantic import BaseModel, Field


class ElveflowMuxConfig(BaseModel):
    """Configuration for a cascaded Elveflow MUX."""
    selectors: List[SerialSelectorConfig]
    position_map: Dict[str, int]
    unit_port_count: int
    passthrough_port: int
    settle_seconds: float


class ElveflowMux(SimSelector):
    """Cascaded Elveflow fluid selector multiplexer.

    Manages a scalable number of serial-connected Elveflow rotary valves
    to select reagent sources by name.
    """

    def __init__(self, selectors: List[SerialSelector], position_map: Dict[str, int],
                 unit_port_count: int = 11, passthrough_port: int = 12,
                 settle_seconds: float = 2) -> None:
        """
        Args:
            selectors: List[SerialSelector] objects for each selector.
            position_map: Dictionary mapping reagent names to port addresses.
            unit_port_count: Number of reagent ports on a single selector.
            passthrough_port: Port used for cascading to the next selector.
            settle_seconds: Time to wait for the valve to settle after moving.
        """
        total_positions = len(selectors) * unit_port_count
        SimSelector.__init__(self, positions=total_positions, position_map=position_map)
        self.port_map = position_map

        self.log = logging.getLogger(self.__class__.__name__)
        self.config = ElveflowMuxConfig(
            selectors=[s.config for s in selectors],
            position_map=position_map,
            unit_port_count=unit_port_count,
            passthrough_port=passthrough_port,
            settle_seconds=settle_seconds,
        )
        if not self.config.selectors:
            raise ValueError("ElveflowMux configuration requires at least one selector.")

        if self.port_map:
            max_port = max(self.port_map.values())
            num_selectors_needed = math.ceil(max_port / self.config.unit_port_count)
            if num_selectors_needed > len(self.config.selectors):
                raise ValueError(
                    f"Port map requires {num_selectors_needed} selectors, but only "
                    f"{len(self.config.selectors)} are configured."
                )

        self.sub_selectors: List[SerialSelector] = selectors

    def connect(self) -> None:
        """Open serial connections to all selectors."""
        self.log.info(f"Connecting to {len(self.sub_selectors)} Elveflow selectors.")
        for selector in self.sub_selectors:
            try:
                selector.connect()
            except serial.SerialException as e:
                self.log.error(f"Connection failed during MUX setup. Disconnecting all.")
                self.disconnect()
                raise

    def disconnect(self) -> None:
        """Close serial connections to all selectors."""
        self.log.info(f"Disconnecting {len(self.sub_selectors)} Elveflow selectors.")
        for selector in self.sub_selectors:
            selector.disconnect()

    def is_connected(self) -> bool:
        """Return True if all selectors are connected and open."""
        if not self.sub_selectors:
            return False
        return all(s.is_connected() for s in self.sub_selectors)

    def move_to_position(self, position: Union[int, str]) -> None:
        """Route the selector to the specified reagent source.

        Uses cascaded addressing. For a unit port count of 11:
        - Addresses 1-11 go directly through selector 1.
        - Addresses 12-22 engage the passthrough on selector 1 and route through selector 2.
        - And so on for additional selectors.

        Args:
            position: Reagent name or port number.

        Raises:
            ValueError: If the reagent is not in the port map or its address
                        exceeds the available selector range.
        """
        if not self.is_connected():
            raise RuntimeError("Selectors are not connected.")

        reagent_name = str(position)

        if reagent_name not in self.port_map:
            raise ValueError(f"Reagent '{reagent_name}' not found in port map.")

        selector_port = self.port_map[reagent_name]
        self.log.info("Selecting reagent '%s' -> port %d", reagent_name, selector_port)

        # Determine which selector the port is on
        target_selector_index = (selector_port - 1) // self.config.unit_port_count

        if target_selector_index >= len(self.sub_selectors):
            raise ValueError(
                f"Reagent '{reagent_name}' port {selector_port} exceeds the range "
                f"of {len(self.sub_selectors)} configured selectors."
            )

        # Set passthrough on all selectors before the target selector
        for i in range(target_selector_index):
            self.log.debug(f"Moving selector {i + 1} to passthrough port {self.config.passthrough_port}")
            self.sub_selectors[i].move(self.config.passthrough_port)
            time.sleep(self.config.settle_seconds)

        # Set the target port on the target selector
        port_on_target_selector = ((selector_port - 1) % self.config.unit_port_count) + 1
        self.log.debug(f"Moving selector {target_selector_index + 1} to port {port_on_target_selector}")
        self.sub_selectors[target_selector_index].move(port_on_target_selector)
        time.sleep(self.config.settle_seconds)

    def config_selector(self) -> None:
        """Test the selector by connecting and cycling through known reagent paths."""
        self.log.info("Running selector configuration test.")
        self.connect()
        try:
            if "incorporation_buffer" in self.port_map:
                self.move_to_position("incorporation_buffer")
            if "gene_primer_mix" in self.port_map:
                self.move_to_position("gene_primer_mix")
            if "incorporation_buffer" in self.port_map:
                self.move_to_position("incorporation_buffer")
        finally:
            self.disconnect()
        self.log.info("Selector configuration test finished.")
