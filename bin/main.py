#!/usr/bin/env python3
"""Instantiate objects from list of dicts."""

from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
from coloredlogs import ColoredFormatter
from time import sleep

import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

fmt='%(asctime)s.%(msecs)03d:%(name)s:%(levelname)s: %(message)s'
datefmt = '%Y-%m-%d,%H:%M:%S'
log_formatter = ColoredFormatter(fmt=fmt, datefmt=datefmt)
logger.handlers[-1].setFormatter(log_formatter)


device_config = Config("proof_of_concept_config.yaml")
# TODO: make a to_dict function.
device_specs = dict(device_config.cfg)

#import pprint
#pprint.pprint(device_specs)

# Create the objects
factory = DeviceSpinner()
device_trees = factory.create_devices_from_specs(device_specs["devices"])

instrument = device_trees['flow_chamber']
instrument.reset()

logger.setLevel(logging.DEBUG)


input("Press enter to mix for 1 second")
instrument.mixer.start_mixing()
sleep(1)
instrument.mixer.stop_mixing()
sleep(1)



#input("Press enter to dispense liquid into the reaction vessel.")
#instrument.dispense_to_vessel(5000, "CLEAR")
#input("Press enter to purge reaction vessel.")
#instrument.drain_vessel()

#input("Press enter to purge.")
#instrument.purge_pump_line()

#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()
