"""Harp Valve Controller PWM-based Mixer"""

from brainwasher.devices.mixer import PWMMixer


class PWMMixer(PWMMixer):
    """An open loop mixing device."""

    def __init__(self, com_port: str, channel: int,
                 min_rpm: float = 333., max_rpm: float = 6000.,
                 frequency_hz: float = 20000,
                 min_duty_cycle_percent: float = 40,
                 max_duty_cycle_percent: float = 100,
                 name: str = None):
        self.device = Device(com_port)
        self.channel = channel
        # FIXME: set frequency on the board.
        super().__init__(min_rpm=min_rpm, max_rpm=max_rpm,
                         frequency_hz=frequency_hz,
                         min_duty_cycle_percent=min_duty_cycle_percent,
                         max_duty_cycle_percent=max_duty_cycle_percent,
                         name=name)

    def _send(self, msg_type, register, data):
        reply = self.device.send(msg_type(register, data).frame)
        data_fmt = "<ffL"
        if reply.message_type == MessageType.WRITE_ERROR:
            raise RuntimeError(f"Sending: {msg_type}({register}, {data}) "
                                "replied with a WRITE_ERROR.")
        return reply


    def _set_mixing_speed(self, rpm: float):
        # Point Slope Formula. Convert RPM to duty cycle.
        percent = ((rpm - self.rpm_range[0])
                   / (self.rpm_range[1] - self.rpm_range[0])
                   * (self.percent_range[1] - self.percent_range[0])
                   + self.percent_range[0])
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

    def _start_mixing(self):
        self._send(HarpMessage.WriteU16, AppRegs.ValvesSet , 1 << self.channel)

    def _stop_mixing(self):
        self._send(HarpMessage.WriteU16, AppRegs.ValvesClear , 1 << self.channel)


if __name__ == "__main__":
    mixer = PWMMixer("/dev/ttyACM0", 0, 333, 6000,
                     20000, 40, 100)
    mixer.set_mixing_speed(1200)
    mixer.start_mixing()
    input()
    mixer.stop_mixing()
