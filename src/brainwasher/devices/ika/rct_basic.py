"""TigerController Serial Port Abstraction"""
from brainwasher.devices.ika.rct_basic_device_codes import *
from enum import Enum
from serial import Serial, SerialException
from time import sleep, perf_counter
from typing import Union
import logging


class RCTBasic:
    """Magnetic Stirrer/Heater interface."""

    # Constants
    BAUD_RATE = 9600
    TIMEOUT = 1

    def __init__(self, com_port: str):
        """Init. Creates serial port connection and connects to hardware.

        :param com_port: serial com port.

        .. code-block:: python

            stir_plate = RCTBasic('/dev/ttyACM0')

        """
        self.ser = None
        self.log = logging.getLogger(__name__)
        self.skipped_replies = 0
        try:
            self.ser = Serial(com_port, RCTBasic.BAUD_RATE,
                              timeout=RCTBasic.TIMEOUT)
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
        except SerialException as e:
            logging.error("Error: could not open connection to the RCT Basic"
                  "device. Is the device plugged in and powered on? Is "
                  "another program using it?")
            raise
        self._last_cmd_send_time = perf_counter()

    def get_device_name(self):
        return self.send(self._format_cmd(Cmd.get_device_name))

    def get_hotplate_temperature_c(self):
        return self.send(self._format_cmd(Cmd.get_hotplate_sensor_value))

    def get_external_temperature_c(self):
        return self.send(self._format_cmd(Cmd.get_external_sensor_value))

    def get_stir_speed_setpoint(self):
        return self.send(self._format_cmd(Cmd.get_stir_speed_setpoint))

    def set_stir_speed(self, rpm: int):
        rpm = round(rpm)
        return self.send(self._format_cmd(Cmd.set_stir_speed_setpoint, rpm))

    def enable_heater(self):
        return sel.send(self._format_cmd(Cmd.enable_heater))

    def disable_heater(self):
        return self.send(self._format_cmd(Cmd.disable_heater))

    def enable_stirring(self):
        return self.send(self._format_cmd(Cmd.enable_motor))

    def disable_stirring(self):
        return self.send(self._format_cmd(Cmd.disable_motor))

    def reset(self):
        return self.send(self._format_cmd(Cmd.reset))

    def set_operating_mode(self, mode: Union[OperatingMode, str]):
        self.send(self._format_cmd(Cmd.set_operating_mode, mode))

    # Missing: watchdog safety limits on temperature.

    # Low-Level Commands.
    def send(self, cmd_str: str, wait: bool = True):
        """Send a command and wait for the reply.
        :param cmd_str: command string with parameters and the proper line
            termination (usually '\r') to send to the tiger controller.
        """

        msg_termination = "\r\n"

        self.log.debug(f"Sending: {repr(cmd_str)}")
        self.ser.write(cmd_str.encode('ascii'))
        self._last_cmd_send_time = perf_counter()
        while self.ser.out_waiting:
            pass
        reply = \
            self.ser.read_until(msg_termination.encode("ascii")).decode("utf8")
        self.log.debug(f"Reply: {repr(reply)}")
        try:
            self._check_reply_for_errors(reply)
        except RuntimeError as e:
            self.log.error("Error occurred when sending: "
                           f"{repr(cmd_str)}")
            raise
        return reply

    def _format_cmd(self, cmd: Cmd, *args: str):
        """Flag a parameter or set a parameter with a specified value.

        .. code-block:: python

            rpm = 100
            stir_plate._set_cmd_args_and_kwds(Cmd.set_stir_speed_setpoint, speed)

        """
        cmd_with_args = cmd.format(*args)
        cmd_str = f"{cmd_with_args}\r\n"
        return cmd_str

    @staticmethod
    def _check_reply_for_errors(reply: str):
        try:
            # Try to convert the reply to Error code enum.
            error_enum = ErrorCode(reply.rstrip('\r\n'))
            raise RuntimeError("Error: device replied with error code "
                               f"{error_num.name}, code: {error_num.value}.")
        except ValueError:
            pass

