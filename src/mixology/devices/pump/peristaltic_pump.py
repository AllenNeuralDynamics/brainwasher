"""High-level device wrapper for the MasterSense peristaltic pump.

Provides a simplified API for volume-based pumping on top of the
low-level MasterSense serial driver. Implements the PumpDevice interface.
"""

import logging
import time
from typing import Optional
from mixology.devices.pump.ismatec_master_sense import MasterSense as PumpDriver
from mixology.devices.peristaltic_pump import PumpDevice
from mixology.devices.serial_device import SerialDevice
from pydantic import BaseModel


class PumpConfig(BaseModel):
    """Configuration dict for SerialPeristalticPumpDevice."""

    name: str
    port: str
    baudrate: int
    tubingDiameter: float
    tubingYield: float  # Added to handle mL/rev conversion
    pumpID: str
    flowReversed: int
    max_rpm: float
    min_rpm: float


class SerialPeristalticPumpDevice(PumpDevice, SerialDevice):
    """High-level wrapper for MasterSense pump operations."""

    def __init__(
        self,
        name: str,
        port: str,
        baudrate: int,
        tubing_diameter: float,
        tubing_yield: float,
        pump_id: str,
        flow_reversed: int,
        max_rpm: float,
        min_rpm: float,
    ) -> None:
        logger_name = self.__class__.__name__ + f".{name}"
        self.log = logging.getLogger(logger_name)
        self.config = PumpConfig(
            name=name,
            port=port,
            baudrate=baudrate,
            tubingDiameter=tubing_diameter,
            tubingYield=tubing_yield,
            pumpID=str(pump_id),
            flowReversed=flow_reversed,
            max_rpm=max_rpm,
            min_rpm=min_rpm,
        )
        self.driver: Optional[PumpDriver] = None
        self._current_speed_mlpm = 0.0

    # --- SerialDevice interface methods ---

    def connect(self) -> None:
        self.initialize()

    def disconnect(self) -> None:
        if self.driver:
            self.driver.pumpDisconnect()

    def is_connected(self) -> bool:
        return self.driver is not None

    # --- PumpDevice interface methods ---

    def initialize(self) -> None:
        """Connect to the pump and verify communication."""
        # Extract numeric address from pumpID (e.g., "IPC_501" -> "1" default)
        address = "".join(filter(str.isdigit, self.config.pumpID)) or "1"
        self.driver = PumpDriver(
            serPort=self.config.port, baudrate=self.config.baudrate, pumpAddress=address
        )

        self.set_flow_rate(0.0)
        self.log.info(f"Pump initialized on {self.config.port} at address {address}")

    def pump_volume(self, volume_ml: float) -> None:
        """Dispense a specified volume using exact timing."""
        if self._current_speed_mlpm <= 0:
            self.log.error(
                "Cannot dispense volume: Flow rate is set to 0 or uninitialized."
            )
            return

        # Calculate how long the pump needs to run to hit the target volume
        duration_s = (volume_ml / self._current_speed_mlpm) * 60.0

        self.log.info(f"Dispensing {volume_ml} mL over {duration_s:.2f} seconds.")
        self.driver.startPump()
        time.sleep(duration_s)
        self.driver.stopPump()

    def start(self) -> None:
        self.driver.startPump()

    def stop(self) -> None:
        self.driver.stopPump()

    def is_running(self) -> bool:
        return self.driver.isPumpRunning() == 1

    def set_flow_rate(self, flow_rate_mlpm: float) -> bool:
        """Translates mL/min request to an RPM command based on tubing yield."""
        if flow_rate_mlpm == 0:
            self._current_speed_mlpm = 0.0
            return self.driver.stopPump()

        # Calculate target RPM
        target_rpm = flow_rate_mlpm / self.config.tubingYield
        if target_rpm > self.config.max_rpm:
            self.log.warning(
                f"Requested flow rate ({flow_rate_mlpm} mL/min) requires {target_rpm:.2f} RPM, "
                f"exceeding the max limit of {self.config.max_rpm} RPM. Clamping to max speed."
            )
        if target_rpm < self.config.min_rpm:
            self.log.warning(
                f"Requested flow rate ({flow_rate_mlpm} mL/min) requires {target_rpm:.2f} RPM, "
                f"below the min limit of {self.config.min_rpm} RPM. Clamping to min speed."
            )
        target_rpm = max(self.config.min_rpm, min(target_rpm, self.config.max_rpm))

        # Sync the software state to the actual physical output
        self._current_speed_mlpm = target_rpm * self.config.tubingYield

        # Send the calculated RPM to the pump
        return self.driver.setSpeedRPM(target_rpm)

    def get_speed_ml_per_min(self) -> float:
        return self._current_speed_mlpm

    def get_response(self) -> str:
        """Verify pump communication."""
        status = self.driver.isPumpRunning()
        return "Connected" if status != -1 else "Disconnected"
