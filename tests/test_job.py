from brainwasher.brainwasher_job import BrainwasherJob as Job
from brainwasher.brainwasher_job import WashStep


def make_dummy_job():
    """return a simple job"""
    my_model = Job(name="simple_wash",  # source_protocol=".",
                   starting_solution={"pbs": 10000},
                   protocol=[WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"thf": 1000, "di_water": 4000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"dcm": 5000})])
    return my_model


def make_long_dummy_job():
    """return another job with a few extra steps"""
    my_model = Job(name="power_wash",  # source_protocol=".",
                   starting_solution={"pbs": 10000},
                   protocol=[WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"thf": 1000, "di_water": 4000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"dcm": 5000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"dcm": 8000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"thf": 9000, "di_water": 1000})])
    return my_model


def test_get_job_duration():
    """Ensure the job duration property is correct."""
    job = make_dummy_job()
    assert job.get_duration_s() == 3600
    # Start halfway through:
    assert job.get_duration_s(1) == 1800

def test_disappearing_resume_state():
    """Resume state field should only appear in the output dict if it has been
    specified."""
    job = make_dummy_job()
    # Resume state should not appear in the output dict unless it was specified.
    assert job.resume_state is None
    assert "resume_state" not in job.model_dump()
    # Resume field should appear in the output dict because it was specified.
    job.save_resume_state(2, starting_solution={"pbs": 10000}, duration_s=1000)
    assert "resume_state" in job.model_dump()
    # Resume field should not appear in the output dict because it was cleared.
    job.clear_resume_state()
    assert job.resume_state is None
    assert "resume_state" not in job.model_dump()

def test_used_chemical_names():
    job = make_dummy_job()
    # Should include starting solution.
    assert job.chemicals == {"pbs", "thf", "dcm", "di_water"}

def test_stock_chemical_volumes():
    job = make_dummy_job()
    # Should not include starting solution.
    assert job.stock_chemical_volumes_ul == {"thf": 1000, "di_water": 4000, "dcm": 5000}
    job2 = make_long_dummy_job()
    assert job2.stock_chemical_volumes_ul == {"thf": 10000, "di_water": 5000, "dcm": 13000}