"""Simulated Peristaltic Pump"""

import logging
from time import sleep


class SimPeristalticPump:
    def __init__(self, name: str = "", flow_rate_mlpm: float = 1.5):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.flow_rate_mlpm = flow_rate_mlpm  # Initial default flow rate
        self.log = logging.getLogger(logger_name)

    def set_flow_rate(self, flow_rate_mlpm: float):
        """
        Updates the hardware flow rate
        """
        if flow_rate_mlpm < 0:
            raise ValueError("Flow rate must be greater or equal to zero.")

        if self.flow_rate_mlpm != flow_rate_mlpm:
            self.flow_rate_mlpm = flow_rate_mlpm
            self.log.debug(f"Flow rate updated to {self.flow_rate_mlpm} mL/min.")

    def dispense(self, volume_ml: float):
        """Simulates dispensing a specific volume of fluid."""
        self.log.info(f"[{self.log.name}] Dispensing {volume_ml} mL at {self.flow_rate_mlpm} mL/min...")
        sleep(0.1) 
        self.log.debug(f"[{self.log.name}] Dispense complete.")

    def dispense_by_time(self, duration_s: float):
        """Simulates dispensing for a specific duration."""
        if duration_s <= 0.0 or self.flow_rate_mlpm <= 0.0:
            return
        self.log.info(f"[{self.log.name}] Dispensing for {duration_s:.2f} seconds at {self.flow_rate_mlpm} mL/min...")

    def get_dispense_duration_s(self, volume_ml: float) -> float:
        """Calculates how long a dispense will take at the current flow rate."""
        if self.flow_rate_mlpm <= 0:
            return 0.0
        return (volume_ml / self.flow_rate_mlpm) * 60.0
    
    def stop(self):
        """Simulates stopping the pump."""
        self.log.info(f"[{self.log.name}] Pump stopped.")

    def start(self):
        """Simulates starting the pump."""
        self.log.info(f"[{self.log.name}] Pump started.")
