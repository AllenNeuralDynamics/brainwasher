"""High-level device wrapper for the Ismatec IPC peristaltic pump.

Provides a simplified API for volume-based pumping on top of the
low-level Ismatec serial driver. Implements the PumpDevice interface.
"""

import logging
import serial
from typing import Optional, Union, Dict
from mixology.devices.pump.ismatec_ipc import Ismatec as IsmatecDriver
from mixology.devices.peristaltic_pump import PumpDevice
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class PumpConfig(BaseModel):
    """Configuration dict for IsmatecPumpDevice."""
    pump_name: str
    port: str
    tubingDiameter: float
    pumpID: str
    flowReversed: int

class IsmatecPumpDevice(PumpDevice):
    """High-level wrapper for Ismatec IPC pump operations.

    Wraps the low-level Ismatec serial driver with a volume-oriented API
    suitable for use by the FluidicSystem orchestrator.

    Args:
        config: Dict with keys 'port', 'tubingDiameter', 'pumpID', 'flowReversed'.
    """

    def __init__(self, config: PumpConfig) -> None:
        logger_name = self.__class__.__name__
        self.log = logging.getLogger(logger_name)
        self.config = config
        self.driver: Optional[IsmatecDriver] = None

    def initialize(self) -> None:
        """Connect to the pump, configure tubing, and set initial flow rate."""
        IPD_COM_CONFIG = self.config['port']
        self.driver = IsmatecDriver(serPort=IPD_COM_CONFIG, tubingDiameter=self.config['tubingDiameter'],
                                    expectedPumpID=self.config['pumpID'])
        self.driver.setFlowRate(1.2)
        self.log.info("Pump initialized on %s", IPD_COM_CONFIG)
        print("initialized ismatecdriver!")

    # --- PumpDevice interface methods ---

    def connect(self) -> None:
        """Open serial connection (alias for initialize)."""
        self.initialize()

    def disconnect(self) -> None:
        """Disconnect pump and close serial port."""
        if self.driver:
            self.driver.pumpDisconnect()

    def is_connected(self) -> bool:
        """Return True if the driver has been initialized."""
        return self.driver is not None

    def pump_volume(self, volume_ml: float, rate_ml_per_min: float) -> None:
        """Dispense a specified volume at a given flow rate."""
        self.pumpVolume(volume_ml, rate_ml_per_min)

    def start(self) -> None:
        """Start the pump."""
        self.driver.startPump()

    def stop(self) -> None:
        """Stop the pump."""
        self.driver.stopPump()

    def is_running(self) -> bool:
        """Return True if the pump is currently running."""
        return self.driver.isPumpRunning() == 1

    def set_flow_rate(self, ml_per_min: float) -> bool:
        """Set the pump flow rate in mL/min."""
        return self.driver.setFlowRate(ml_per_min)

    def get_speed(self) -> float:
        """Return the current pump speed in mL/min."""
        return self.driver.speed

    # --- Legacy methods (for backward compatibility) ---

    def pumpVolume(self, volumeToPump: float, rate: Optional[float] = None) -> None:
        """Pump a specified volume at a given flow rate.

        Args:
            volumeToPump: Volume to pump in mL.
            rate: Flow rate in mL/min.
        """
        self.log.info("Pumping %.2f mL at %.2f mL/min", volumeToPump, rate)
        self.driver.setFlowVolumeAndRate(volumeToPump, (1.0 * float(volumeToPump) / (rate)))
        self.driver.startPump()

    def setFlowRate_ml_per_min(self, flowRate: float) -> bool:
        """Set the pump flow rate in mL/min."""
        return self.driver.setFlowRate(flowRate)

    def stopPump(self) -> None:
        """Stop the pump immediately."""
        self.driver.stopPump()

    def startPump(self) -> None:
        """Start the pump."""
        self.driver.startPump()

    def isPumpRunning(self) -> int:
        """Check if the pump is running. Returns 1 (running), 0 (stopped), or -1 (error)."""
        return self.driver.isPumpRunning()

    def PumpDisconnect(self) -> None:
        """Disconnect the pump (stop, return to manual, close serial port)."""
        return self.driver.pumpDisconnect()

    def GetResponse(self) -> str:
        """Verify pump communication by requesting its identification."""
        return self.driver.checkPumpIdentification()
