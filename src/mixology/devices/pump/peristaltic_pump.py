"""High-level device wrapper for the Ismatec IPC peristaltic pump.

Provides a simplified API for volume-based pumping on top of the
low-level Ismatec serial driver. Implements the PumpDevice interface.
"""

import logging
import serial
from typing import Optional, Union, Dict
from mixology.devices.pump.ismatec_ipc import Ismatec as IsmatecDriver
from mixology.devices.peristaltic_pump import PumpDevice
from mixology.devices.serial_device import SerialDevice
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class PumpConfig(BaseModel):
    """Configuration dict for IsmatecPumpDevice."""
    name: str
    port: str
    tubingDiameter: float
    pumpID: str
    flowReversed: int


class SerialPeristalticPumpDevice(PumpDevice, SerialDevice):
    """High-level wrapper for Ismatec IPC pump operations.

    Wraps the low-level Ismatec serial driver with a volume-oriented API
    suitable for use by the FluidicSystem orchestrator.

    Args:
        config: Dict with keys 'port', 'tubingDiameter', 'pumpID', 'flowReversed'.
    """

    def __init__(self, name: str, port: str, tubing_diameter: float, pump_id: str, flow_reversed: int) -> None:
        logger_name = self.__class__.__name__ + f".{name}"
        self.log = logging.getLogger(logger_name)
        self.config = PumpConfig(
            name=name,
            port=port,
            tubingDiameter=tubing_diameter,
            pumpID=pump_id,
            flowReversed=flow_reversed
        )
        self.driver: Optional[IsmatecDriver] = None

    # --- SerialDevice interface methods ---

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

    # --- PumpDevice interface methods ---

    def initialize(self) -> None:
        """Connect to the pump, configure tubing, and set initial flow rate."""
        self.driver = IsmatecDriver(serPort=self.config.port, tubingDiameter=self.config.tubingDiameter,
                                    expectedPumpID=self.config.pumpID)
        self.driver.setFlowRate(0.0)
        self.log.info("Pump initialized on %s", self.config.port)

    def pump_volume(self, volume_ml: float) -> None:
        """Dispense a specified volume at a given flow rate."""
        duration_m = self.get_dispense_duration_m(volume_ml)
        self.driver.setFlowVolumeAndRate(volume_ml, duration_m)
        self.driver.startPump()

    def start(self) -> None:
        """Start the pump."""
        self.driver.startPump()

    def stop(self) -> None:
        """Stop the pump."""
        self.driver.stopPump()

    def is_running(self) -> bool:
        """Return True if the pump is currently running.) """
        # Driver Returns 1 (running), 0 (stopped), or -1 (error)
        return self.driver.isPumpRunning() == 1

    def set_flow_rate(self, flow_rate_mlpm: float) -> bool:
        """Set the pump flow rate in mL/min."""
        return self.driver.setFlowRate(flow_rate_mlpm)

    def get_speed_ml_per_min(self) -> float:
        """Return the current pump speed in mL/min."""
        return self.driver.speed

    def get_response(self) -> str:
        """Verify pump communication by requesting its identification."""
        return self.driver.checkPumpIdentification()


if __name__ == "__main__":
    import logging
    from time import sleep

    pump = SerialPeristalticPumpDevice(
        name="TestIsmatecPumpDevice_1",
        port="COM9",
        tubing_diameter=0.51,
        pump_id="IPC_501",
        flow_reversed=0
    )
    
    pump.connect()
    sleep(1)
    pump.set_flow_rate(flow_rate_mlpm = 1.5)
    sleep(1)
    pump.pump_volume(volume_ml = 1.5)  # Example volume
    