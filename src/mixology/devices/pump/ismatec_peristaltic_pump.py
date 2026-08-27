import logging
import serial
from typing import Optional
from pydantic import BaseModel

from mixology.devices.pump.peristaltic_pump import PumpDevice
from mixology.devices.serial_device import SerialDevice


class PumpConfig(BaseModel):
    name: str
    port: str
    baudrate: int
    tubing_diameter: float
    tubing_yield: float
    max_rpm: float
    min_rpm: float
    pump_id: str
    flow_reversed: int


class IsmatecPeristalticPumpDevice(PumpDevice, SerialDevice):
    """Integrated 1-file driver for Masterflex MasterSense pumps."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name=kwargs.get("name", "MasterSense"))
        self.config = PumpConfig(**kwargs)
        
        self.log = logging.getLogger(f"{self.__class__.__name__}.{self.config.name}")
        
        self.serial: Optional[serial.Serial] = None
        self._current_speed_mlpm = 0.0
        self.pump_address = "".join(filter(str.isdigit, self.config.pump_id)) or "1"

    # --- SerialDevice Interface Methods ---
    def connect(self) -> None:
        self.initialize()

    def disconnect(self) -> None:
        if self.is_connected():
            self.stop()
            self._send_command("RE0")  # Disable remote control
            self.serial.close()
            self.serial = None
            self.log.debug("Disconnected pump and closed serial port.")

    def is_connected(self) -> bool:
        return self.serial is not None and self.serial.is_open

    # --- PumpDevice Interface Methods ---
    def initialize(self) -> None:
        self.serial = serial.Serial(
            port=self.config.port,
            baudrate=self.config.baudrate,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )
        
        if self._send_command("RE1"):
            self.log.info(f"Pump initialized on {self.config.port} (address {self.pump_address})")
        else:
            self.log.warning("Remote control command rejected.")
        self.set_flow_rate(0.0)

    def start(self) -> None:
        self._send_command("H")

    def stop(self) -> None:
        if self._check_status(self._send_command("I")):
            self._current_speed_mlpm = 0.0

    def is_running(self) -> bool:
        response = self._send_command("RC")
        try:
            if "," in response:
                return int(response.split(",")[1].strip()) == 1
        except ValueError:
            pass
            
        return False

    def set_flow_rate(self, flow_rate_mlpm: float) -> bool:
        if flow_rate_mlpm == 0:
            self.stop()
            return True

        target_rpm = flow_rate_mlpm / self.config.tubing_yield
        if target_rpm > self.config.max_rpm:
            self.log.warning(
                f"Requested {flow_rate_mlpm} mL/min requires {target_rpm:.2f} RPM. "
                f"Clamping to max ({self.config.max_rpm})."
            )
        elif target_rpm < self.config.min_rpm:
            self.log.warning(
                f"Requested {flow_rate_mlpm} mL/min requires {target_rpm:.2f} RPM. "
                f"Clamping to min ({self.config.min_rpm})."
            )
        target_rpm = max(self.config.min_rpm, min(target_rpm, self.config.max_rpm))

        rpm_int = int(round(target_rpm * 100))
        cmd = f"R{rpm_int:03d}"

        if self._send_command(cmd):
            self._current_speed_mlpm = target_rpm * self.config.tubing_yield
            return True
        return False

    def get_speed_ml_per_min(self) -> float:
        return self._current_speed_mlpm


    # --- Private Serial Helpers ---
    
    def _send_command(self, cmd: str) -> str:
        """Sends a command to the pump and returns the raw string response."""
        if not self.is_connected():
            self.log.error(f"Cannot send command '{cmd}': serial port is closed.")
            return ""

        full_command = f"{self.pump_address}{cmd}\r"
        self.serial.write(full_command.encode("ascii"))
        
        response = self.serial.readline().decode("ascii", errors="ignore").strip()
        
        # Handle known pump error codes
        if response == "~":
            self.log.error("Pump is not in Serial Communications mode.")
        elif response == "#":
            self.log.error(f"Incorrect serial command string sent: {cmd}")
            
        return response

    def _check_status(self, response: str) -> bool:
        """Evaluates if the raw response indicates a successful command."""
        return response == "*"
