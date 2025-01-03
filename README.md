# brainwasher

[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Python](https://img.shields.io/badge/python->=3.7-blue?logo=python)

Note that this package is intended to run on a Raspberry Pi with a particular hardware configuration.
This package can only be simulated if running on a different system.

## Quick Links
* [Reaction Vessel CAD model](https://cad.onshape.com/documents/f1bf5f3ce34b965e5212d1ac/w/45b1dd7d9365ece513829b77/e/7736ee8ab9b2b1e217084778)
* [P&ID Diagram Source link](https://alleninstitute.sharepoint.com/:u:/s/Instrumentation/ERyxjmhmVwZOke5AnwQ4NG0Bue9zIMbGMNcaT-wdS2hT9w?e=ZHAdRq)
* [Project Design Folder](https://alleninstitute.sharepoint.com/:f:/s/Instrumentation/Emw6bMGQgo5Pgin2Gb3EXEcBvJux_NXnwFN3A5khlz1pbA?e=NgBTAY)


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
rsync -a /path/to/source_folder pi@raspberrypi.local:/path/to/destination_folder
```

Now you can avoid installing Github credentials to push code from the device itself, and simply develop entirely on your PC!

### Developing Locally

The Raspberry Pi 4 and 5 are fast enough that you can develop code on the Pi itself if needed.
To do so, login to the Pi, setup Git, and edit files on the device itself.


## Deploying

TODO: systemd setup.


## Contributing

### Linters and testing

There are several libraries used to run linters, check documentation, and run tests.

- Please test your changes using the **coverage** library, which will run the tests and log a coverage report:

```bash
coverage run -m unittest discover && coverage report
```

- Use **interrogate** to check that modules, methods, etc. have been documented thoroughly:

```bash
interrogate .
```

- Use **flake8** to check that code is up to standards (no unused imports, etc.):
```bash
flake8 .
```

- Use **black** to automatically format the code into PEP standards:
```bash
black .
```

- Use **isort** to automatically sort import statements:
```bash
isort .
```

### Pull requests

For internal members, please create a branch. For external members, please fork the repository and open a pull request from the fork. We'll primarily use [Angular](https://github.com/angular/angular/blob/main/CONTRIBUTING.md#commit) style for commit messages. Roughly, they should follow the pattern:
```text
<type>(<scope>): <short summary>
```

where scope (optional) describes the packages affected by the code changes and type (mandatory) is one of:

- **build**: Changes that affect build tools or external dependencies (example scopes: pyproject.toml, setup.py)
- **ci**: Changes to our CI configuration files and scripts (examples: .github/workflows/ci.yml)
- **docs**: Documentation only changes
- **feat**: A new feature
- **fix**: A bugfix
- **perf**: A code change that improves performance
- **refactor**: A code change that neither fixes a bug nor adds a feature
- **test**: Adding missing tests or correcting existing tests

### Semantic Release

The table below, from [semantic release](https://github.com/semantic-release/semantic-release), shows which commit message gets you which release type when `semantic-release` runs (using the default configuration):

| Commit message                                                                                                                                                                                   | Release type                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| `fix(pencil): stop graphite breaking when too much pressure applied`                                                                                                                             | ~~Patch~~ Fix Release, Default release                                                                          |
| `feat(pencil): add 'graphiteWidth' option`                                                                                                                                                       | ~~Minor~~ Feature Release                                                                                       |
| `perf(pencil): remove graphiteWidth option`<br><br>`BREAKING CHANGE: The graphiteWidth option has been removed.`<br>`The default graphite width of 10mm is always used for performance reasons.` | ~~Major~~ Breaking Release <br /> (Note that the `BREAKING CHANGE: ` token must be in the footer of the commit) |

### Documentation
To generate the rst files source files for documentation, run
```bash
sphinx-apidoc -o doc_template/source/ src 
```
Then to create the documentation HTML files, run
```bash
sphinx-build -b html doc_template/source/ doc_template/build/html
```
More info on sphinx installation can be found [here](https://www.sphinx-doc.org/en/master/usage/installation.html).
