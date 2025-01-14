"""Pressure Sensor Base Class"""


class PressureSensor:

    def get_pressure_psig(self):
        raise NotImplementedError

    def get_pressure_psia(self):
        raise NotImplementedError
