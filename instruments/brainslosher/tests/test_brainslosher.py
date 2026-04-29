import pytest
from unittest.mock import MagicMock

from instruments.brainslosher.src.brainslosher.brainslosher import BrainSlosher
from instruments.brainslosher.src.brainslosher.brainslosher_models import (
    BrainSlosherConfig,
    BrainSlosherJob,
    Cycle,
)
from brainwasher.devices.vessels import ReactionVessel


@pytest.fixture
def config():
    return BrainSlosherConfig(
        selector_port_map={"air": 0, "chamber": 1, "waste": 2, "PBS": 3},
        drain_volume_buffer_ml=1.0,
        fill_volume_ml=2.0,
    )


@pytest.fixture
def rxn_vessel():
    v = ReactionVessel(name="test", max_volume_ul=5000, solution={})
    return v


@pytest.fixture
def waste_vessel():
    v = ReactionVessel(name="test", max_volume_ul=5000, solution={})
    return v


@pytest.fixture
def pump():
    return MagicMock()


@pytest.fixture
def mixer():
    return MagicMock()


@pytest.fixture
def brainslosher(config, rxn_vessel, pump, mixer, waste_vessel):
    return BrainSlosher(
        config=config,
        rxn_vessel=rxn_vessel,
        pump=pump,
        mixer=mixer,
        waste_vessel=waste_vessel,
    )


def test_fill_chamber_overfill_raises(brainslosher, rxn_vessel):
    rxn_vessel.add_solution(solution=4900)

    with pytest.raises(ValueError):
        brainslosher.fill_chamber("PBS", 0.2)


def test_withdraw_and_dispense_chunks(brainslosher, pump):
    brainslosher.withdraw_and_dispense_solution("PBS", 10.0, "chamber")

    # 10 ml with 4.5 ml syringe → 3 cycles
    assert pump.withdraw.call_count == 3
    assert pump.dispense.call_count == 3


def test_run_wash_empty_vessel(monkeypatch, brainslosher):
    brainslosher.drain_chamber = MagicMock()
    brainslosher.prime_line = MagicMock()
    brainslosher.fill_chamber = MagicMock()
    brainslosher.purge_line = MagicMock()

    # patch perf_counter
    times = iter([0, 600])
    monkeypatch.setattr(
        "brainwasher.devices.instruments.brainslosher.perf_counter", lambda: next(times)
    )
    brainslosher.run_wash_step(10, "PBS")

    # check chamber was prepped
    assert brainslosher.drain_chamber.call_count == 2
    assert brainslosher.prime_line.call_count == 1
    assert brainslosher.fill_chamber.call_count == 1
    assert brainslosher.purge_line.call_count == 1


def test_run_wash_full_vessel(monkeypatch, brainslosher):
    brainslosher.drain_chamber = MagicMock()
    brainslosher.prime_line = MagicMock()
    brainslosher.fill_chamber = MagicMock()
    brainslosher.purge_line = MagicMock()

    # patch perf_counter
    times = iter([0, 600])
    monkeypatch.setattr(
        "brainwasher.devices.instruments.brainslosher.perf_counter", lambda: next(times)
    )
    brainslosher.rxn_vessel.add_solution(something_else=10)
    brainslosher.run_wash_step(10, "PBS")

    # check chamber was prepped
    assert brainslosher.drain_chamber.call_count == 2
    assert brainslosher.prime_line.call_count == 1
    assert brainslosher.fill_chamber.call_count == 1
    assert brainslosher.purge_line.call_count == 1


def test_run_wash_pause(monkeypatch, brainslosher):
    brainslosher.drain_chamber = MagicMock()
    brainslosher.prime_line = MagicMock()
    brainslosher.fill_chamber = MagicMock()
    brainslosher.purge_line = MagicMock()

    # patch perf_counter
    times = iter([0, 376, 382])
    monkeypatch.setattr(
        "brainwasher.devices.instruments.brainslosher.perf_counter", lambda: next(times)
    )

    # setup conditions to pause
    brainslosher.job_worker = MagicMock()
    brainslosher.job_worker.is_alive.return_value = True
    brainslosher.prime_line.side_effect = (
        lambda solution: brainslosher.pause_requested.set()
    )

    brainslosher.run_wash_step(10.6, "PBS")

    # check chamber was prepped
    assert brainslosher.resume_state_overrides["duration_min"] == 4.2


def test_run_step(brainslosher):
    brainslosher.purge_line = MagicMock()
    brainslosher.prime_line = MagicMock()
    brainslosher.run_wash_step = MagicMock()

    brainslosher.run_step("PBS", 10, 5)

    assert brainslosher.purge_line.call_count == 1
    assert brainslosher.prime_line.call_count == 5
    assert brainslosher.run_wash_step.call_count == 5
    assert brainslosher.resume_state_overrides["washes"] == 0


def test_pause_run_step(brainslosher):
    brainslosher.purge_line = MagicMock()
    brainslosher.prime_line = MagicMock()

    def pause_on_second_wash(*args, **kwargs):
        if brainslosher.run_wash_step.call_count == 2:
            raise RuntimeError("Simulated pause")

    brainslosher.run_wash_step = MagicMock(side_effect=pause_on_second_wash)
    with pytest.raises(RuntimeError):
        brainslosher.run_step(solution="PBS", duration_min=5, washes=5)

    assert brainslosher.resume_state_overrides["washes"] == 3


def test_run_job(brainslosher, tmp_path):
    job = BrainSlosherJob(
        name="test_job",
        starting_solution={},
        protocol=[
            Cycle(solution="PBS", duration_min=10, washes=3),
            Cycle(solution="PBS", duration_min=10, washes=3),
        ],
        motor_speed_rpm=20,
    )

    brainslosher.run_step = MagicMock(
        side_effect=lambda **kwargs: brainslosher.resume_state_overrides.update(
            {"duration_min": 0, "washes": 0}
        )
    )
    brainslosher._run_job_worker(job=job, job_path=tmp_path / "job.yaml")
    assert brainslosher.run_step.call_count == 2


def test_pause_job(brainslosher, tmp_path):
    job = BrainSlosherJob(
        name="test_job",
        starting_solution={},
        protocol=[
            Cycle(solution="PBS", duration_min=10, washes=3),
            Cycle(solution="PBS", duration_min=10, washes=3),
        ],
        motor_speed_rpm=20,
    )

    def fake_run_step(**kwargs):
        brainslosher.resume_state_overrides.update({"duration_min": 5, "washes": 1})
        brainslosher.pause_requested.set()

    brainslosher.run_step = MagicMock(side_effect=fake_run_step)
    brainslosher._run_job_worker(job=job, job_path=tmp_path / "job.yaml")
    assert brainslosher.run_step.call_count == 1


def test_resume_job(brainslosher, tmp_path, config):
    # pause job
    job = BrainSlosherJob(
        name="test_job",
        starting_solution={},
        protocol=[
            Cycle(solution="PBS", duration_min=10, washes=3),
            Cycle(solution="PBS", duration_min=10, washes=3),
        ],
        motor_speed_rpm=20,
    )

    def fake_run_step(**kwargs):
        brainslosher.resume_state_overrides.update({"duration_min": 5, "washes": 1})
        brainslosher.rxn_vessel.add_solution(**{"PBS": config.fill_volume_ml * 1000})
        brainslosher.pause_requested.set()

    brainslosher.run_step = MagicMock(side_effect=fake_run_step)
    brainslosher._run_job_worker(job=job, job_path=tmp_path / "job.yaml")

    # resume paused job
    def fake_run_step(solution: str, duration_min: float, washes: int):
        brainslosher.resume_state_overrides.update({"duration_min": 0, "washes": 0})

    brainslosher.run_step = MagicMock(side_effect=fake_run_step)
    brainslosher._run_job_worker(job=job, job_path=tmp_path / "job.yaml")
