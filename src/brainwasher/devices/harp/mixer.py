"""PWM Mosfet based Mixer"""

from brainwasher.devices.mixer import Mixer
from enum import IntEnum
from pyharp.device import Device, DeviceMode
from pyharp.messages import HarpMessage, WriteU8ArrayMessage
from pyharp.messages import MessageType
from struct import pack, unpack

class AppRegs(IntEnum):
    ValvesState = 32
    ValvesSet = 33
    ValvesClear = 34
    ValveConfigs0 = 35
    ValveConfigs1 = 36
    ValveConfigs2 = 37
    ValveConfigs3 = 38
    ValveConfigs4 = 39
    ValveConfigs5 = 40
    ValveConfigs6 = 41
    ValveConfigs7 = 42
    ValveConfigs8 = 43
    ValveConfigs9 = 44
    ValveConfigs10 = 45
    ValveConfigs11 = 46
    ValveConfigs12 = 47
    ValveConfigs13 = 48
    ValveConfigs14 = 49
    ValveConfigs15 = 50
    AuxGPIODir = 51
    AuxGPIOState = 52
    AuxGPIOSet = 53
    AuxGPIOClear = 54

    AuxGPIOInputRiseEvent = 55
    AuxGPIOInputFallEvent = 56
    AuxGPIOInputRisingInputs = 57
    AuxGPIOFallingInputs = 58


class PWMMixer(Mixer):
    """An open loop mixing device."""

    def __init__(self, com_port: str, channel: int,
                 min_rpm: float = 333., max_rpm: float = 6000.,
                 min_duty_cycle_percent: float = 40, max_duty_cycle_percent: float = 100,
                 name: str = None):
        super().__init__(max_rpm=max_rpm, name=name)
        self.duty_cycle_percent_range =  (min_duty_cycle_percent,
                                          max_duty_cycle_percent)
        self.rpm_range = (min_rpm, max_rpm)
        self.device = Device(com_port)
        self.channel = channel
        self.rpm = 0
        self.set_mixing_speed(max_rpm)  # Default to max speed.

    def _send(self, msg_type, register, data):
        reply = self.device.send(msg_type(register, data).frame)
        data_fmt = "<ffL"
        if reply.message_type == MessageType.WRITE_ERROR:
            raise RuntimeError(f"Sending: {msg_type}({register}, {data}) "
                                "replied with a WRITE_ERROR.")
        return reply


    def set_mixing_speed_percent(self, percent):
        # Clamp percent range.
        if percent < self.duty_cycle_percent_range[0]:
            self.rpm = self.rpm_range[0]
            self.log.warning("Clamping speed to {self.rpm} [rpm].")
            percent = self.duty_cycle_percent_range[0]
        if percent > self.duty_cycle_percent_range[1]:
            self.rpm = self.rpm_range[1]
            self.log.warning("Clamping speed to {self.rpm} [rpm].")
            percent = self.duty_cycle_percent_range[1]
        normalized_percent = percent/100.
        valve_cfg = (normalized_percent, normalized_percent, 0)
        data_fmt = "<ffL"
        reply = self.device.send(WriteU8ArrayMessage(
                    AppRegs.ValveConfigs0 + self.channel, data_fmt,
                        valve_cfg).frame)
        self.log.debug(f"Received reply data: "
                       f"{unpack(data_fmt, bytes(reply.payload))}")
        if reply.message_type == MessageType.WRITE_ERROR:
            raise RuntimeError(f"Sending: {msg_type}({register}, {data}) "
                                "replied with a WRITE_ERROR.")

    def set_mixing_speed(self, rpm: float):
        super().set_mixing_speed(rpm)
        # Point Slope Formula. Convert RPM to Percent
        percent = ((rpm - self.rpm_range[0])
                   / (self.rpm_range[1] - self.rpm_range[0])
                   * (self.duty_cycle_percent_range[1]
                      - self.duty_cycle_percent_range[0])
                  + self.duty_cycle_percent_range[0])
        self.rpm = rpm
        self.set_mixing_speed_percent(percent)

    def start_mixing(self):
        self.log.debug(f"Starting mixer at {self.rpm} [rpm].")
        self._send(HarpMessage.WriteU16, AppRegs.ValvesSet , 1 << self.channel)

    def stop_mixing(self):
        super().stop_mixing()
        self._send(HarpMessage.WriteU16, AppRegs.ValvesClear , 1 << self.channel)


if __name__ == "__main__":
    mixer = PWMMixer("/dev/ttyACM0", 0, 333, 6000, 40, 100)
    mixer.set_mixing_speed(1200)
    mixer.start_mixing()
    input()
    mixer.stop_mixing()
