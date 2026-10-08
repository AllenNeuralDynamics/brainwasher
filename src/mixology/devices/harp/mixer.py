"""Harp Valve Controller PWM-based Mixer"""
from mixology.devices.mixer import PWMMixer
from pyharp.device import Device, MessageType
from pyharp.messages import HarpMessage, WriteU8HarpMessage
from struct import unpack
from enum import IntEnum

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

class HarpPWMMixer(PWMMixer):
    """An open loop mixing device."""

    def __init__(
        self,
        com_port: str,
        channel: int,
        min_rpm: float = 333.0,
        max_rpm: float = 6000.0,
        frequency_hz: float = 20000,
        min_duty_cycle_percent: float = 40,
        max_duty_cycle_percent: float = 100,
        name: str = None,
    ):
        self.device = Device(com_port)
        self.channel = channel
        # FIXME: set frequency on the board.
        super().__init__(
            min_rpm=min_rpm,
            max_rpm=max_rpm,
            frequency_hz=frequency_hz,
            min_duty_cycle_percent=min_duty_cycle_percent,
            max_duty_cycle_percent=max_duty_cycle_percent,
            name=name,
        )

    def _send(self, msg_type, register, data):
        reply = self.device.send(msg_type(register, data).frame)
        data_fmt = "<ffL"
        if reply.message_type == MessageType.WRITE_ERROR:
            raise RuntimeError(
                f"Sending: {msg_type}({register}, {data}) replied with a WRITE_ERROR."
            )
        return reply

    def _set_mixing_speed(self, rpm: float):
        # Point Slope Formula. Convert RPM to duty cycle.
        percent = (rpm - self.rpm_range[0]) / (
            self.rpm_range[1] - self.rpm_range[0]
        ) * (self.percent_range[1] - self.percent_range[0]) + self.percent_range[0]
        normalized_percent = percent / 100.0
        valve_cfg = (normalized_percent, normalized_percent, 0)
        data_fmt = "<ffL"
        reply = self.device.send(
            WriteU8HarpMessage(
                AppRegs.ValveConfigs0 + self.channel, data_fmt, valve_cfg
            ).frame
        )
        self.log.debug(f"Received reply data: {unpack(data_fmt, bytes(reply.payload))}")
        if reply.message_type == MessageType.WRITE_ERROR:
            raise RuntimeError(
                f"Sending: {HarpMessage.WriteU8}({AppRegs.ValveConfigs0}, {valve_cfg}) replied with a WRITE_ERROR."
            )

    def _start_mixing(self):
        self._send(HarpMessage.WriteU16, AppRegs.ValvesSet, 1 << self.channel)

    def _stop_mixing(self):
        self._send(HarpMessage.WriteU16, AppRegs.ValvesClear, 1 << self.channel)


if __name__ == "__main__":
    mixer = HarpPWMMixer("/dev/ttyACM0", 0, 333, 6000, 20000, 40, 100)
    mixer.set_mixing_speed(1200)
    mixer.start_mixing()
    input()
    mixer.stop_mixing()
