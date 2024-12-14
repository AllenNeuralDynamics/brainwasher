#!/usr/bin/env python3
"""Instantiate objects from list of dicts."""

from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner

import logging
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
#logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())
logger.handlers[-1].setFormatter(
    logging.Formatter(fmt='%(asctime)s:%(name)s:%(levelname)s: %(message)s'))


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
#logger.info("priming DI WATER.")
#instrument.prime_reservoir_line("CLEAR")

#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()
