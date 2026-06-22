"""Simulated Peristaltic Pump"""

import logging

class SimPeristalticPump:
    def __init__(self, name: str):
        logger_name = self.__class__.__name__ + (f".{name}" if name else "")
        self.log = logging.getLogger(logger_name)

    def start(self, rate_ml_min: float):
        self.log.debug(f"[{self.log.name}] Peristaltic pump started at {rate_ml_min} mL/min")

    def stop(self):
        self.log.debug(f"[{self.log.name}] Peristaltic pump stopped.")