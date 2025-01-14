"""Liquid Detection Sensor abstraction on top of Sequent Microsystems 16-input board"""

from brainwasher.devices.pressure_sensor import PressureSensor as BasePressureSensor
import lib16univin


class PressureSensor(BasePressureSensor):

    def __init__(self, stack: int, i2c_bus: int, channel: int,
                 min_pressure_psia: float, max_pressure_psia: float,
                 min_voltage: float, max_voltage: float):
        super().__init__()
        self.card = lib16univin.SM16univin(stack=stack, i2c_bus=i2c_bus)
        self.channel = channel
        self.slope = ((max_pressure_psia - min_pressure_psia)
                      / (max_voltage - min_voltage))
        self.point = (min_voltage, min_pressure_psia)  # x1, y1

    def get_pressure_psia(self):
        voltage = self.card.get_u_in(self.channel)
        return self.slope * (voltage - self.point[0]) + self.point[1]

    def get_pressure_psig(self):
        pass


class PX409030A5V(PressureSensor):
    """PX409-030A5V Pressure Sensor Class"""

    PSIG_NOMINAL_OFFSET = 14.7

    def __init__(self, stack: int, i2c_bus: int, channel: int,
                 min_voltage: float = 0, max_voltage: float = 5.0):
        """Constructor. Min and Max voltages can be specified per any
        calibration sheet."""
        super().__init__(stack=stack, i2c_bus=i2c_bus, channel=channel,
                         min_pressure_psia=0, max_pressure_psia=30,
                         min_voltage=min_voltage, max_voltage=max_voltage)

    def get_pressure_psig(self):
        return self.get_pressure_psia() + self.PSIG_NOMINAL_OFFSET
