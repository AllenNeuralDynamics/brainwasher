"""Simulated Peristaltic Pump"""

import logging
from time import sleep

class SimPeristalticPump:
    def __init__(self, name: str = ""):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)

    def dispense(self, volume_ml: float, rate_ml_min: float):
        """Simulates dispensing a specific volume of fluid."""
        self.log.info(f"[{self.log.name}] Dispensing {volume_ml} mL at {rate_ml_min} mL/min...")

        sleep(0.1) 
        
        self.log.debug(f"[{self.log.name}] Dispense complete.")