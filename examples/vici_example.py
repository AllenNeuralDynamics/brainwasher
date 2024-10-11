#!/usr/bin/env python3

from ftdi_serial import Serial
from time import sleep
from vicivalve import VICI

# Uncomment for some prolific log statements.
import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())
logger.handlers[-1].setFormatter(
   logging.Formatter(fmt='%(asctime)s:%(levelname)s: %(message)s'))


#ser = Serial("/dev/ttyUSB0", baudrate="9600")
ser = Serial("/dev/serial/by-id/usb-FTDI_FT230X_Basic_UART_DP046FT7-if00-port0",
             baudrate="9600")
vici = VICI(serial=ser, positions=10)

print(f"Current vici position is: {vici.current_position()}")
vici.move_to_position(10)
print(f"Current vici position is: {vici.current_position()}")
