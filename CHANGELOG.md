# Changelog

# main
* Rework Brainslosher `run_wash_step` function to drain -> fill -> mix, similar to the Brainwasher's `run_wash_step` function.

# v1.0.0
* Refactors structure to have instruments as uv workspaces
* Renames project to mixology

# v0.3.0
* Drains chamber in thread in initialization function to unblock interaction during draining


# v0.1.0
* Tease out common functionality from brainwasher class into a base `Instrument` class.
* Create Brainslosher class deriving from base `Instrument` class
* Create dependency groups in *pyproject.toml* to simplify installation process for distinct instruments: `brainwasher_group` and `brainslosher_group`
* Create launch script for the Brainslosher in *scripts* folder.

# v0.0.0
* Stable point of core Brainwasher functionality. Features include:
  * Instantiate instrument from `device-spinner` yaml file
  * Run in simulation mode option by using a different yaml file with specific instruments mocked as simulated versions.
  * Ensure thread-safety with a `@lock_flowpath` decorator that makes specific functions that use shared hardware thread safe.
  * Take instructions from a "job" file, a yaml encoding a list of steps.
    * Include a pydantic model for the job file.
  * Implement *pause*, *resume*, *abort* functionality.
  * Track pause state in job file.
    * Functionality is abstracted up so that calling `run` on a job file auto-resumes if the job was previously paused.
  * Track execution history in the job file.
