"""Harp Valve Controller PWM-based Mixer"""

from brainwasher.devices.mixer import PWMMixer
from rpi_hardware_pwm import HardwarePWM



class PWMMixer(PWMMixer):
    """An open loop mixing device."""
    PI5_GPIO_PIN_TO_CHANNEL = \
    {
        12: 0,
        13: 1,
        18: 2,
        19: 3
    }

    def __init__(self, gpio_pin: str, frequency_hz: float = 20000,
                 min_rpm: float = 333., max_rpm: float = 6000.,
                 frequency_hz: float = 20000,
                 min_duty_cycle_percent: float = 40,
                 max_duty_cycle_percent: float = 100,
                 name: str = None):
        self.pwm = HardwarePWM(pwm_channel=0, hz=frequency_hz, chip=0)
        self.duty_cycle_percent = 0
        super().__init__(min_rpm=min_rpm, max_rpm=max_rpm,
                         frequency_hz=frequency_hz,
                         min_duty_cycle_percent=min_duty_cycle_percent,
                         max_duty_cycle_percent=max_duty_cycle_percent,
                         name=name)

    def _set_mixing_speed(self, rpm: float):
        # Point Slope Formula. Convert RPM to duty cycle.
        self.duty_cycle_percent = self.rpm_to_percent(rpm)
        self.pwm.change_duty_cycle(self.duty_cycle_percent)

    def _start_mixing(self):
        self.pwm.start(self.duty_cycle_percent)

    def _stop_mixing(self):
        self.pwm.stop()


if __name__ == "__main__":
    mixer = PWMMixer(12, 20000,
                     333, 6000, 40, 100)
    mixer.set_mixing_speed(1200)
    mixer.start_mixing()
    input()
    mixer.stop_mixing()
