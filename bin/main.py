#!/usr/bin/env python3
"""Instantiate objects from list of dicts."""

from datetime import datetime
from device_spinner.config import Config
from device_spinner.device_spinner import DeviceSpinner
from coloredlogs import ColoredFormatter, DEFAULT_FIELD_STYLES
from io import StringIO
from time import sleep

import argparse
import traceback
import logging

### Sample Protocol
#csv_str = \
#    ('"Mix Speed",Chemicals,Solution,Duration\n'
#     '100%,"YELLOW, CLEAR","500uL YELLOW, 3500uL CLEAR", 3sec\n'
#     '100,"CLEAR","100% CLEAR", 3sec')
csv_str = \
    ('"Mix Speed",Chemicals,Solution,Duration\n'
     '100%,"YELLOW, PURPLE","2500uL PURPLE, 2500uL YELLOW", 1sec\n'
     '100%,"CLEAR","100% CLEAR", 1sec')
sample_protocol = StringIO(csv_str)


#import matplotlib.pyplot as plt
#import igraph as ig
#fig, ax = plt.subplots()
#ig.plot(device_trees['tube_length_graph'], target=ax)
#plt.show()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="proof_of_concept_config.yaml")
    parser.add_argument("--log_level", type=str, default="INFO",
                        choices=["INFO", "DEBUG"])
    parser.add_argument("--simulated", default=False, action="store_true",
                        help="Simulate hardware device connections.")

    args = parser.parse_args()

    # Setup logging.
    fmt='%(asctime)s:%(name)s:%(levelname)s: %(message)s'
    datefmt="%Y-%m-%d %H:%M:%S.%f"
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    # Add file handler
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d-%H:%M:%S")
    logger.addHandler(logging.FileHandler(filename=f"logs-{date_str}.log", mode="a"))

    # Add file handler formatter.
    log_file_formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)
    logger.handlers[-1].setFormatter(log_file_formatter)

    # Add stream handler
    logger.addHandler(logging.StreamHandler())
    # Add stream handler formatter.
    field_styles = DEFAULT_FIELD_STYLES
    field_styles["levelname"]["color"] = "magenta"
    log_formatter = ColoredFormatter(fmt=fmt, datefmt=datefmt,
                                     field_styles=field_styles)
    logger.handlers[-1].setFormatter(log_formatter)

    # Create the instrument
    device_config = Config(args.config)
    device_specs = dict(device_config.cfg)

    factory = DeviceSpinner()
    device_trees = factory.create_devices_from_specs(device_specs["devices"])
    instrument = device_trees['flow_chamber']
    instrument.reset()

    logger.setLevel(args.log_level)

    #instrument.leak_check_syringe_to_selector_common_path() # TODO
    #instrument.leak_check_syringe_to_drain_exaust_normally_open_path()  # works
    #instrument.leak_check_syringe_to_drain_waste_path()  # works
    #instrument.leak_check_syringe_to_reaction_vessel()  # works

    try:
        instrument.run_protocol(sample_protocol)
    except KeyboardInterrupt:
        instrument.halt()
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
