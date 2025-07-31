from brainwasher.job import Job
from brainwasher.job import WashStep


def make_dummy_job():
    my_model = Job(name="test_brian",  # source_protocol=".",
                   starting_solution={"pbs": 10000},
                   protocol=[WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"thf": 1000, "di_water": 4000}),
                             WashStep(mix_speed_rpm=1000, duration_s=1800,
                                      solution={"dcm": 5000})])
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
