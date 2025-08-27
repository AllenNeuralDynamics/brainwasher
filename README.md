# brainwasher

[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Python](https://img.shields.io/badge/python->=3.10-blue?logo=python)

Note that this package is intended to run on a Raspberry Pi with a particular hardware configuration.

## Quick Links
* [Reaction Vessel CAD model](https://cad.onshape.com/documents/f1bf5f3ce34b965e5212d1ac/w/45b1dd7d9365ece513829b77/e/7736ee8ab9b2b1e217084778)
* [P&ID Diagram Source link](https://alleninstitute.sharepoint.com/:u:/s/Instrumentation/EToUz-sNb_NOhtTetyjH3GUBfrVqOR7EBPKXOnT8-eHf-Q?e=GkewAP)
* [Project Design Folder](https://alleninstitute.sharepoint.com/:f:/s/Instrumentation/Emw6bMGQgo5Pgin2Gb3EXEcBvJux_NXnwFN3A5khlz1pbA?e=NgBTAY)

## Wiring Setup
See the [hardware configuration](https://github.com/AllenNeuralDynamics/brainwasher/blob/main/bin/proof_of_concept_config.yaml) for the device's wiring configuration.


## Raspberry Pi Setup
Enable I2C interface via Raspi-Config under *Interface Options*.
````bash
sudo raspi-config
````

Ensure virtual environments can be created
````bash
sudo apt install python3-venv
````
**Recommended(!!)**: Create a new environment.
````bash
python3 -m venv brainwasher
````
Enter the environment.
````bash
source ~/brainwasher/bin/activate
````

## Package Installation
To use the software, in the root directory, run
```bash
pip install -e .
```

To develop the code, run
```bash
pip install -e .[dev]
```

If Python drivers were not installed automatically with the first command, you can install them manually from their respective repositories here:
* [Eight Mosfets Hat](https://github.com/SequentMicrosystems/8mosind-rpi/tree/main/python)
* [16x Optoisolated Inputs Hat](https://github.com/SequentMicrosystems/16inpind-rpi/blob/main/python/README.md)
* [16x Universal Inputs Hat](https://github.com/SequentMicrosystems/16univin-rpi/blob/main/python/README.md)


## Developing
There are two strategies for editing code on the Raspberry Pi.

### Developing Remotely
Since the Raspberry Pi doesn't have all the text editing bells-and-whistles of your PC, you can develop all the code on your PC and synchronize the code folder with the Pi to execute the result.
To do so, in Linux, use the `rsync` command

```
rsync -a /path/to/brainwasher/ pi@raspberrypi.local:/path/to/destination_folder --exclude=".*"
```

Note that the slash at the end of the source directory path is required.

Then run
```
uv sync
```

Now you can avoid installing Github credentials to push code from the device itself, and simply develop entirely on your PC!

### Developing Locally

The Raspberry Pi 4 and 5 are fast enough that you can develop code on the Pi itself if needed.
To do so, login to the Pi, setup Git, and edit files on the device itself.


## Deploying

TODO: systemd setup.

## Job Files

A job file is a sequence of wash steps along with some metadata.

A sample job file looks like the following: 

```yaml

history:
  events: []
name: test_thf_and_dcm
protocol:
- duration_s: 3.0
  mix_speed_rpm: 1200.0
  solution:
    deionized_water: 7000.0
    thf: 3000.0
- duration_s: 3.0
  mix_speed_rpm: 1200.0
  solution:
    deionized_water: 1000.0
    thf: 9000.0
- duration_s: 3.0
  mix_speed_rpm: 1200.0
  solution:
    thf: 10000.0
- duration_s: 3.0
  mix_speed_rpm: 1200.0
  solution:
    dcm: 10000.0
- duration_s: 3.0
  mix_speed_rpm: 1200.0
  solution:
    dcm: 10000.0
- duration_s: 0.0
  mix_speed_rpm: 0.0
  solution:
    deionized_water: 10000.0
source_protocol:
  path: /home/brainwasher/protocols/demo_protocol.csv # This value is ignored right now.
starting_solution:
  pbs: 10000.0

```


A step in the `protocol` has the following required steps:
```yaml
- duration_s: 60  # [seconds]. How long to remain in this step.
  mix_speed_rpm: 0.0 # [rpm]. 0 for "no mixing." Minimum on-speed: 360; max: 6000.
  solution:  # a dictionary, keyed by solution name, of volumes in microliters.
    deionized_water: 10000.0
```
These additional steps are optional:
```yaml
  start_empty: true # If true, empty the reaction vessel before filling with solution for this step. Default is true. 
  end_empty: false  # If true, empty the reaction vessel before exiting this step. Default is false.
  intermittent_mixing_on_time: None # Float. If specified, duty cycle of leaving the motor on at the specified RPM.
  intermittent_mixing_off_time: None # Float. If specified, duty cycle of of leaving the motor off at the specified RPM.
```

Once the job file is executed, extra (computed) fields will be added afterwards.
These fields are not required will be recomputed if the required fields change.
