#!/usr/bin/env python3
"""Instantiate objects from list of dicts."""

from datetime import datetime
from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
from coloredlogs import ColoredFormatter, DEFAULT_FIELD_STYLES
from io import StringIO
from time import sleep

from inpromptu.inpromptu_prompt_toolkit import Inpromptu

import brainwasher.devices.instruments.brainwasher  # For SIMULATED flag
import argparse
import traceback
import logging
import logging.config

### Sample Protocol
#demo_protocol_csv_str = \
#    ('"Mix Speed",Chemicals,Solution,Duration\n'
#     '100%,"YELLOW, PURPLE","2500uL PURPLE, 2500uL YELLOW", 1sec\n'
#     '100%,"CLEAR","100% CLEAR", 1sec')
demo_protocol_csv_str = \
    ('"Mix Speed",Chemicals,Solution,Duration\n'
     '100%,"sbip","100% sbip", 1sec\n'
     '100%,"sbip","100% sbip", 1sec')

#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="instrument_config.yaml")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["INFO", "DEBUG"])
    parser.add_argument("--protocol", type=str, default=None,
                        help="Simulate hardware device connections.")

    parser.add_argument("--simulated", default=False, action="store_true",
                        help="Simulate hardware device connections.")

    args = parser.parse_args()
    if args.simulated:
        brainwasher.devices.instruments.brainwasher.SIMULATED = True

    config_name = args.config if not args.simulated else "sim_instrument_config.yaml"

    # Create the instrument config.
    device_config = Config(config_name)
    # Setup logging.
    logging.config.dictConfig(dict(device_config.cfg["logging"]))
    logger = logging.getLogger()
    if args.simulated:
        logger.warning("System running in simulation!")
    # Override console log level if specified.
    for handler in logger.handlers:
        if handler.get_name() == 'console':
            handler.setLevel(args.log_level)

    # Create the instrument.
    device_specs = dict(device_config.cfg)

    factory = DeviceSpinner()
    device_trees = factory.create_devices_from_specs(device_specs["devices"])
    instrument = device_trees["brainwasher"]

    #cam = device_trees['vessel_cam']
    #cam.start_recording("test
    instrument.reset()

    #protocol = args.protocol if args.protocol is not None else StringIO(demo_protocol_csv_str)
    #if args.protocol is None:
    #    logger.info("Running demo protocol")
    prompt = Inpromptu(instrument, methods_to_skip=["purge_pump_line"])
    try:
        prompt.cmdloop()
    except KeyboardInterrupt:
        instrument.halt()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
