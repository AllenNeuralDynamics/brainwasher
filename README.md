# Mixology

[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
![Python](https://img.shields.io/badge/python->=3.11-blue?logo=python)

Mixology is the core library for fluidic instruments. It provides the shared data models and protocol parsing used by the instrument packages in this repository, including:

- CSV protocol parsing via `mixology.protocol.Protocol`
- job and history models via `mixology.job.Job`
- the base instrument runner in `mixology.instrument.Instrument`
- hardware-facing device adapters under `mixology.devices`

The repository also contains the instrument packages that build on top of Mixology:

- `instruments/brainwasher`
- `instruments/brainslosher`
- `instruments/seqflow`

## Install

This project uses `uv`.

```bash
uv sync
```

To install the optional Brainwasher hardware extras from the root package:

```bash
uv sync --extra brainwasher
```

If you want an editable development environment for a specific instrument package, run `uv sync` from that package directory as well.

## Quick Start

### Work with a job model
Job files are step-based documents that describe a sequence of steps for an instrument to run.
Each job contains a list of steps plus the metadata needed to start, stop, pause, and resume execution.

The `mixology.job.Job` model stores the job data, while `mixology.instrument.Instrument` provides the runtime behavior that can pause a running job and later resume it from the saved state.

```python
from mixology.job import Job

job = Job(
    name="demo",
    starting_solution={"pbs": 10000.0},
    protocol=[],
)
print(job.model_dump(exclude_none=True))
```


## Repository Layout

```text
src/mixology/            Core library code
instruments/             Workspace packages built on mixology
README.md                This overview
CHANGELOG.md             Release notes maintained manually
```

## Development

Run the test suite from the repository root:

```bash
uv run pytest
```

Build the library wheel and sdist:

```bash
uv build
```

Format and lint with Ruff:

```bash
uv run ruff format
uv run ruff check
```

## Release Strategy

Releases are automated from [.github/release.yml](https://github.com/AllenNeuralDynamics/brainwasher/blob/main/.github/release.yml) and are handled per package instead of as one monolithic project release.

- A push to `main` or `dev` starts the release workflow.
- The workflow checks which package roots changed in the commit range.
- If the root package changes, it creates a `mixology` release.
- If `instruments/brainwasher` changes, it creates a `brainwasher` release.
- If `instruments/brainslosher` changes, it creates a `brainslosher` release.
- If `instruments/seqflow` changes, it creates a `seqflow` release.
- Each release name follows `<package>-v<version>` using the version from that package's `pyproject.toml`.
- Before publishing, the workflow checks that the release name does not already exist.
- Only the matching package's built artifacts from its `dist/` directory are uploaded.

This means a commit can produce more than one release if it touches more than one package. It also means release notes remain manual in `CHANGELOG.md`, while the GitHub release workflow publishes the built artifacts for the changed package only.

## Notes

- The root package name is `mixology`.
- The repository targets Python 3.11 and newer.
