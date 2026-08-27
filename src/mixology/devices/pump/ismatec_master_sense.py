#!/usr/bin/python
"""
Low-level serial driver for Masterflex MasterSense peristaltic pumps.

Communicates over RS-232 serial at 115200 baud, 8N1.
Command format: <pump_address><command><parameter><CR>.
Standard Success Response: '*'.
Error Response: '#' (Invalid command) or '~' (Not in remote mode).
"""

import serial
import logging


class MasterSenseError(Exception):
    """Base exception for MasterSense communication errors."""

    pass


class MasterSense:
    """Serial driver for Masterflex MasterSense pumps."""

    def __init__(self, serPort: str, baudrate: int, pumpAddress: str = "1") -> None:
        self.log = logging.getLogger(f"{self.__class__.__name__}.{serPort}")
        self.pump_address = str(pumpAddress)  # Default address is 1
        self.log.debug("Opening serial port %s at %d baud", serPort, baudrate)

        # MasterSense requires 115200 baud rate, 8 bit, 1 stop bit, no parity
        self.serial = serial.Serial(
            port=serPort,
            baudrate=baudrate,
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.5,
        )

        # Initialize pump and put into Remote mode
        if self.enable_remote_control(True):
            self.log.info("Pump connected and remote control enabled.")
        else:
            self.log.warning(
                "RE1 command rejected. (This is normal if Serial mode is forced via the pump's touchscreen)."
            )

    def pumpDisconnect(self) -> None:
        """Stop the pump, return to manual control, and close port."""
        if self.serial.is_open:
            self.stopPump()
            self.enable_remote_control(False)  # Disable remote mode
            self.serial.close()
            self.log.debug("Disconnected pump and closed serial port.")

    def enable_remote_control(self, enable: bool) -> bool:
        """
        Toggle serial communications remote mode.
        1 = enable, 0 = disable.
        """
        cmd = "RE1" if enable else "RE0"
        return self.status_check(self.send_to_pump(cmd))

    def is_pump_running(self) -> int:
        """
        Display current pump status.
        Returns 1 if running, 0 if stopped, -1 on error.
        """
        # RC command returns integers (address, running status, direction)
        response = self.send_to_pump("RC")
        try:
            # Example response: "1, 0, 1" -> split by comma
            parts = response.split(",")
            if len(parts) >= 2:
                status = int(parts[1].strip())
                return status
        except ValueError:
            self.log.warning(f"Failed to parse pump status: {response}")
        return -1

    def set_speed_percent(self, percent: float) -> bool:
        """
        Set pump speed in % of max rotation speed.
        Requires 5 digits representing percent to one decimal point (e.g., 50.0% -> 00500).
        """
        if not (0.0 <= percent <= 100.0):
            self.log.warning("Percent must be between 0.0 and 100.0")
            return False

        # Format to 5 digits, 1 decimal place stripped of the '.'
        # Example: 53.2 -> 00532
        formatted_pct = f"{percent * 10:05.0f}"
        cmd = f"S{formatted_pct}"
        return self.status_check(self.send_to_pump(cmd))

    def set_speed_rpm(self, rpm: float) -> bool:
        """
        Set pump speed in RPM.
        Requires 'R' followed by 3 or more digits representing RPM with
        two decimal points (e.g., 100.00 RPM -> R10000).
        """
        if rpm < 0:
            self.log.warning("RPM cannot be negative.")
            return False

        # Multiply by 100 to shift the two decimal places into the integer
        # Example: 300.50 * 100 = 30050
        rpm_int = int(round(rpm * 100))

        formatted_rpm = f"{rpm_int:03d}"
        cmd = f"R{formatted_rpm}"

        self.log.debug(f"Setting pump speed to {rpm} RPM (command: {cmd})")
        return self.status_check(self.send_to_pump(cmd))

    def start_pump(self) -> bool:
        """Start Pump dispensing."""
        return self.status_check(self.send_to_pump("H"))

    def stop_pump(self) -> bool:
        """Stop pump dispensing."""
        return self.status_check(self.send_to_pump("I"))

    def set_flow_direction(self, clockwise: bool) -> bool:
        """
        Change pump revolution direction.
        J = clockwise, K = counterclockwise.
        """
        cmd = "J" if clockwise else "K"
        return self.status_check(self.send_to_pump(cmd))

    def reset_volume_counter(self) -> bool:
        """Reset cumulative volume."""
        return self.status_check(self.send_to_pump("W"))

    def inquire_cumulative_volume(self) -> str:
        """Display current cumulative volume."""
        return self.send_to_pump(":")

    def send_to_pump(self, cmd: str) -> str:
        """
        Format: (Address) (Serial Command) (ASCII 13 Carriage Return).
        """
        # ASCII 13 is \r
        full_command = f"{self.pump_address}{cmd}\r"
        self.serial.write(full_command.encode("ascii"))
        self.log.debug(f"Sent: {full_command.strip()}")
        return self.get_response()

    def get_response(self) -> str:
        """Reads response from pump until carriage return or timeout."""
        # Responses end with ASCII 13 and sometimes ASCII 10 (\r\n)
        response = self.serial.readline().decode("ascii", errors="ignore").strip()

        if response == "~":
            self.log.error("Pump is not in Serial Communications mode.")
        elif response == "#":
            self.log.error("Incorrect serial command string sent.")

        return response

    def status_check(self, response: str) -> bool:
        """The pump confirms valid serial commands by returning an asterisk (*)."""
        return response == "*"


if __name__ == "__main__":
    import logging
    from time import sleep

    # Configure logging to output to the console during the test
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s:%(name)s:%(levelname)s: %(message)s"
    )

    log = logging.getLogger("MasterSenseTest")
    log.info("Starting low-level driver test...")

    try:
        # Initialize the pump
        pump = MasterSense(serPort="COM4", baudrate=115200, pumpAddress="1")
        sleep(1)

        # Test setting the speed to 50 RPM
        log.info("Commanding pump to 50.00 RPM...")
        if pump.set_speed_rpm(25.0):
            log.info("Speed successfully set.")
        else:
            log.error("Failed to set speed.")

        sleep(1)

        # Test starting the pump
        log.info("Starting motor for 5 seconds...")
        if pump.start_pump():
            log.info("Motor running...")
            sleep(5)
        else:
            log.error("Failed to start motor.")

        # Test stopping the pump
        log.info("Stopping motor...")
        pump.stop_pump()

    except Exception as e:
        log.error(f"Test failed due to an exception: {e}")

    finally:
        log.info("Cleaning up and disconnecting...")
        if "pump" in locals():
            pump.pump_disconnect()
        log.info("Test finished.")
