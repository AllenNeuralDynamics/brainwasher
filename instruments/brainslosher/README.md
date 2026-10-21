# brainslosher

`brainslosher` is a hardware control package for a reagent-wash instrument that moves fluid between a reaction chamber, a waste vessel, and a set of selector valves. It also has motor control to agitate samples. In practical terms, it automates the routine steps needed to prepare the chamber before and after a wash cycle: prime the line, fill the chamber with a target solution, drain it to waste, and repeat a defined job protocol.

This package is built around the `BrainSlosher` instrument class and is designed to work with the rest of the `mixology` hardware stack, including a syringe pump, reaction vessel, mixer, and waste vessel.

## What the instrument does

The core workflow is:

- select a valve position for the active reagent or flow path
- withdraw a defined volume from the selected source
- dispense that volume into either the chamber or waste vessel
- maintain the reaction chamber volume and waste limits safely
- run repeatable wash jobs through a `BrainSlosherJob` specification

Typical operations include:

- `fill_chamber(solution, volume_ml)`
- `drain_chamber(volume_ml=None)`
- `prime_line(solution)`
- `purge_line()`
- `withdraw_and_dispense_solution(solution, volume_ml, dispense_to)`
- job-level state management via `set_job()`, `get_job()`, and `clear_job()`

## Installation

### Software

Clone package. 

```bash
git clone https://github.com/AllenNeuralDynamics/brainwasher.git
```

To clone only mixology and brainslosher package and omit other instruments.

```bash
git clone --filter=blob:none --sparse https://github.com/AllenNeuralDynamics/brainwasher.git
cd brainwasher
git sparse-checkout set src instruments/brainslosher
```


To initialize environment, from the `instruments/brainslosher` directory:

```bash
uv sync
```

### Mixer

`brainslosher` depends on the Pololu Tic controller command-line utility for mixing. The runtime code invokes `ticcmd` directly to configure, energize, and move the mixer.

Install the official Pololu Tic software so `ticcmd` is available on your PATH:

- Pololu Tic documentation: https://www.pololu.com/docs/0J71
- Pololu Tic software repo: https://github.com/pololu/tic-software
- Pololu product page for the Tic controller family: https://www.pololu.com/category/210/tic-stepper-motor-controllers

On Linux, make sure the USB serial device permissions are configured correctly and that the CLI is installed before starting the instrument. If `ticcmd` cannot be found, you will get a command-not-found error when the mixer tries to initialize.


### Syringe Pump

`brainslosher` depends on the Runze Multi Channel Syringe Pump SY01B. Before using, the pump must be set to the Runze Communication protocol documented [here](https://github.com/AllenNeuralDynamics/runze-control#changing-communication-protocol). If pump fails upon brainslosher initialization, change the communication protocol to Runze, power cycle the pump, and retry.


## Starting the instrument and server

`brainslosher` exposes a small CLI in `src/brainslosher/scripts/brainslosher_main.py`. Running it starts the instrument server and blocks while the server waits for client requests. To initialize an instrument run:

```bash
uv run brainslosher --config /PATH/TO/CONFIG
```

Supported options:

- `--config PATH`: override the YAML config file to use. Defaults to `src\brainslosher\scripts\brainslosher_config.yaml`.
- `--log-level {INFO,DEBUG}`: sets the console log verbosity.
- `--simulated`: loads `src/brainslosher/scripts/sim_brainslosher_config.yaml` instead of the real hardware config.


The server exposes a small ZeroMQ RPC API for clients to start, pause, resume, query, and control the instrument. This is the same interface used by higher-level automation and UI layers, such as [brainslosher-instrument](https://github.com/AllenNeuralDynamics/brainslosher-instrument). A minimal client example is shown below.

```bash
from one_liner.client import RouterClient

client = RouterClient(rpc_port=5555, broadcast_port=5556)

# query config
cfg = client.call("brainslosher", "get_config")
print(cfg)

# update a parameter
client.call("brainslosher", "set_fill_volume", kwargs={"volume_ml": 2.0})

# start a run
job = {"name": "demo_job"}
client.call("brainslosher", "start", kwargs={"job": job})

# pause / resume
client.call("brainslosher", "pause")
client.call("brainslosher", "resume")
```

## Minimal Python usage

```python
from brainslosher.brainslosher import BrainSlosher
from brainslosher.brainslosher_models import BrainSlosherConfig, BrainSlosherJob, Cycle
from mixology.devices.vessels import ReactionVessel, WasteVessel

config = BrainSlosherConfig(
    selector_port_map={
        "air": 0,
        "chamber": 1,
        "waste": 2,
        "PBS": 3,
        "drain": 4,
    },
    drain_volume_buffer_ml=1.0,
    fill_volume_ml=2.0,
)

rxn_vessel = ReactionVessel(name="reaction", max_volume_ul=5000, solution={})
waste_vessel = ReactionVessel(name="waste", max_volume_ul=5000, solution={})

from runze_control.multichannel_syringe_pump import SY01B
from mixology.devices.pololu.pololu_tic_mixer import PololuTicMixer

pump = SY01B(
    position_map=config.selector_port_map,
    com_port="COM4",
    baudrate=9600,
    position_count=6,
    syringe_volume_ul=5000,
)
mixer = PololuTicMixer(serial="00477970", max_rpm=500)

instrument = BrainSlosher(
    config=config,
    rxn_vessel=rxn_vessel,
    pump=pump,
    mixer=mixer,
    waste_vessel=waste_vessel,
)

# define a simple wash job and start it
job = BrainSlosherJob(
    name="demo_job",
    starting_solution={},
    protocol=[
        Cycle(solution="PBS", duration_min=5, washes=3),
    ],
    motor_speed_rpm=20,
)

instrument.set_job(job)
instrument.start_run(job)
```

### Liquid Checks

- Validates reaction-vessel capacity before dispensing so a requested volume cannot overfill the chamber.
- Validates waste-vessel capacity before draining so fluid transfer cannot overflow the waste container.
- Validates waste vessel capacity before starting run. IMPORTANT: The waste check is based on accumulated tracked volume, not a direct real-world sensor reading, so it is a software safety guard rather than a physical validation of the tank state. After the waste vessel is physically emptied, call `waste_emptied()` to reset the tracked waste volume before the next run.

## Development

For testing or development without hardware, start the instrument in simulation mode:

```bash
uv run brainslosher --simulated
```

This is useful for validating config structure, job sequencing, and program flow before connecting real valves and pumps.

## Tests

Run the test suite from the `instruments/brainslosher` directory:

```bash
uv run pytest
uv run pytest tests/test_brainslosher.py
uv run pytest tests/test_models.py
```

These tests cover the core runtime flow for the instrument, including job setup, run validation, overflow protection, and model/config parsing. 


