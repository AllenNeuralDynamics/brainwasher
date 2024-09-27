"commands for IKA RCT Basic device."""

from enum import Enum

try
    from enum import StrEnum # 3.11+
except ImportError:
    class StrEnum(str, Enum):
        pass

class Cmd(StrEnum):
    """Stirrer/Heater commands."""

    get_device_name = "IN_NAME"
    get_external_sensor_value = "IN_PV_1"
    get_hotplate_sensor_value = "IN_PV_2"
    get_stir_speed = "IN_PV_4"

    get_temperature_setpoint = "IN_SP_1"
    get_safety_limit_temperature_setpoint = "IN_SP_3"
    get_stir_speed_setpoint = "IN_SP_4"

    set_temperature_setpoint = "OUT_SP_1 {}"
    set_stir_speed_setpoint = "OUT_SP_4 {}"

    enable_heater = "START_1"
    disable_heater = "STOP_1"

    enable_motor = "START_4"
    disable_motor = "STOP_4"

    reset = "RESET"

    set_operating_mode = f"SET_MODE_{}"


class OperatingMode(StrEnum):
    "Operating Mode Options"

    DEFAULT = "A"
    RESUME = "b"
    LOCKED_RESUME = "c"
    USER_VALIDATION = "d"


class ErrorCode(StrEnum):

    WatchdogError = "E2"
    InternalTemperatureExceeded = "E3"
    MotorControlUnavailable = "E4"
    TemperatureControlFailure = "E5"
    SafetyCircuitTripped = "E6"
    HotplateSafetyCircuitOpen = "E13"
    ExternalTemperatureSensorShortCircuit = "E14"
    HeatingSafetyRelayFault = "E21"
    HeatingSetpointFailure = "E22"  # Unsure how to describe this one.
    HotplateTemperatureLimitExceeded = "E24"
    HeatingElementFault = "E25"
    PlateTemperatureExceededLimit = "E26"
    HeaterSwitchFault = "E31"
    HotplateSafetyTempExceedsSetSafetyTemp = "E44"
    PlateSafetyTempExceedsPlateTemperature = "E46"  # ?

