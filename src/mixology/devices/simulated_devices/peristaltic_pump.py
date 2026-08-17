import logging
from time import sleep

from mixology.devices.peristaltic_pump import PumpDevice
from mixology.devices.serial_device import SerialDevice

class SimPeristalticPump(PumpDevice, SerialDevice):
    """Simulated Peristaltic Pump for testing and offline development."""

    def __init__(self, name: str = "SimPump", flow_rate_mlpm: float = 1.5):
        # Initialize the base class
        super().__init__(name=name)
        
        logger_name = f"{self.__class__.__name__}.{self.name}"
        self.log = logging.getLogger(logger_name)
        
        # Simulated hardware state (single source of truth for the simulator)
        self._speed_ml_per_min = flow_rate_mlpm
        self._is_running = False
        self._connected = False

    def connect(self) -> None:
        self.log.debug("Connecting to simulated serial selector.")
        self._connected = True

    def disconnect(self) -> None:
        self.log.debug("Disconnecting from simulated serial selector.")
        self._connected = False

    def is_connected(self) -> bool:
        """Return True if the device is currently connected."""
        return self._connected

    def is_connected(self) -> bool:
        """Return True if the driver has been initialized."""
        return self.driver is not None

    def initialize(self) -> None:
        """Simulates connection and initialization."""
        self.log.info(f"[{self.name}] Initialized simulated pump.")

    def set_flow_rate(self, flow_rate_mlpm: float) -> bool:
        """Updates the simulated hardware flow rate."""
        if flow_rate_mlpm < 0:
            raise ValueError("Flow rate must be greater or equal to zero.")

        if self._speed_ml_per_min != flow_rate_mlpm:
            self._speed_ml_per_min = flow_rate_mlpm
            self.log.debug(f"[{self.name}] Flow rate updated to {self._speed_ml_per_min} mL/min.")
        
        return True

    def get_speed_ml_per_min(self) -> float:
        """Returns the simulated pump speed."""
        return self._speed_ml_per_min

    def is_running(self) -> bool:
        """Returns the simulated running state."""
        return self._is_running

    def start(self) -> None:
        """Simulates starting the pump."""
        self._is_running = True
        self.log.info(f"[{self.name}] Pump started.")

    def stop(self) -> None:
        """Simulates stopping the pump."""
        self._is_running = False
        self.log.info(f"[{self.name}] Pump stopped.")

    def pump_volume(self, volume_ml: float) -> None:
        """Simulates dispensing a specific volume of fluid at the current rate."""
        # Calculate duration using the shared base class function
        duration = self.get_dispense_duration_s(volume_ml)
        
        current_speed = self.get_speed_ml_per_min()
        self.log.info(f"[{self.name}] Dispensing {volume_ml} mL at {current_speed} mL/min (will take {duration:.2f}s)...")
        
        self.start()
        sleep(0.1) 
        self.stop()
        self.log.debug(f"[{self.name}] Dispense complete.")
