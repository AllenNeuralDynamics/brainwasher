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
logger.setLevel(logging.DEBUG)
instrument.reset()


### Sample Protocol
csv_str = \
    ('"Mix Speed",Chemicals,Solution,Duration\n'
     '100%,"YELLOW, CLEAR","500uL YELLOW, 3500uL CLEAR", 3sec\n'
     '100,"CLEAR","100% CLEAR", 3sec')
sample_protocol = StringIO(csv_str)

#input("Press enter to run the sample_protocol.")
instrument.unprime_reservoir_line("YELLOW")
instrument.unprime_reservoir_line("CLEAR")
instrument.unprime_reservoir_line("PURPLE")

instrument.drain_vessel()
#instrument.run_protocol(sample_protocol)
#instrument.run_wash_step(duration_s=0, start_empty=False, end_empty=True)

#instrument.leak_check_syringe_to_selector_common_path() # TODO
#instrument.leak_check_syringe_to_drain_exaust_normally_open_path()  # works
#instrument.leak_check_syringe_to_drain_waste_path()  # works
#instrument.leak_check_syringe_to_reaction_vessel()  # works

#while True:
    #input("press enter to toggle the drain waste valve.")
    #instrument.drain_waste_valve.energize()
    #sleep(.5)
    #instrument.drain_waste_valve.deenergize()

    #input("press enter to toggle the drain exhaust valve.")
    #instrument.drain_exhaust_valve.energize()
    #sleep(.5)
    #instrument.drain_exhaust_valve.deenergize()

    #input("press enter to toggle the rv source valve.")
    #instrument.rv_source_valve.energize()
    #sleep(1.0)
    #instrument.rv_source_valve.deenergize()

    #input("press enter to toggle the rv exhaust valve.")
    #instrument.rv_exhaust_valve.energize()
    #sleep(.5)
    #instrument.rv_exhaust_valve.deenergize()


#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()
