#!/usr/bin/env python3

from brainwasher.devices.ika.rct_basic import RCTBasic
from time import sleep

# Uncomment for some prolific log statements.
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
logger.handlers[-1].setFormatter(
   logging.Formatter(fmt='%(asctime)s:%(levelname)s: %(message)s'))


stir_plate = RCTBasic("/dev/ttyACM0")

print(f"device name: {stir_plate.get_device_name()}")
print(f"hotplate temp: {stir_plate.get_hotplate_temperature_c()}")
print(f"external sensor temp: {stir_plate.get_external_temperature_c()}")
print(f"stir speed setpoint: {stir_plate.get_stir_speed_setpoint()}")
print()
rpm = 600
print(f"set stir speed to {rpm} [rpm]")
stir_plate.set_stir_speed(rpm)
print(f"Enabling stirring.")
stir_plate.enable_stirring()
sleep(3.0)
print(f"Disabling stirring.")
stir_plate.disable_stirring()
