#!/usr/bin/env python3
"""Instantiate objects from list of dicts."""

from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
from coloredlogs import ColoredFormatter
from io import StringIO
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
device_specs = dict(device_config.cfg)

#import pprint
#pprint.pprint(device_specs)

# Create the objects
factory = DeviceSpinner()
device_trees = factory.create_devices_from_specs(device_specs["devices"])
instrument = device_trees['flow_chamber']
instrument.reset()

logger.setLevel(logging.DEBUG)

### Sample Protocol
csv_str = \
    ('"Mix Speed",Chemicals,Solution,Duration\n'
     '100%,"YELLOW, CLEAR","500uL YELLOW, 3500uL CLEAR", 3sec\n'
     '100,"CLEAR","100% CLEAR", 3sec')
sample_protocol = StringIO(csv_str)

#instrument.start_pressure_monitor()
#while True:
#    sleep(1)
input("Press enter to run the sample_protocol.")
instrument.run_protocol(sample_protocol)
# Purge
instrument.run_wash_step(duration_s=0, start_empty=False, end_empty=True)

#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()
