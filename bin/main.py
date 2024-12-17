#!/usr/bin/env python3
"""Instantiate objects from list of dicts."""

from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
from coloredlogs import ColoredFormatter
from time import sleep

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
#logger.setLevel(logging.INFO)
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

# run prime routine.
instrument = device_trees['flow_chamber']
logger.info("Success!")
logger.info("Resetting Instrument.")
instrument.reset()
instrument.prime_reservoir_line("CLEAR")
sleep(1.0)
instrument.unprime_reservoir_line("CLEAR")

#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()
