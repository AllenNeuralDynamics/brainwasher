"""Boolean Liquid Detection Sensor base classes."""


class BooleanLiquidDetectionSensor:
    def tripped(self):
        raise NotImplementedError

    def untripped(self):
        raise NotImplementedError


class BubbleDetectionSensor(BooleanLiquidDetectionSensor):
    pass

class LeakDetectionSensor(BooleanLiquidDetectionSensor):
    pass
