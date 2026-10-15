from app.application.redaction import redact
from app.infrastructure.repositories import JobRepository


def test_redacts_api_key_fields_and_secret_shaped_text():
    cleaned = redact(
        {
            "api_key": "sk-live-secretvalue",
            "note": "provider said sk-live-secretvalue",
            "status": "ok",
        }
    )
    assert cleaned["api_key"] == "[REDACTED]"
    assert "sk-live-secretvalue" not in str(cleaned)
    assert cleaned["status"] == "ok"


def test_persisted_event_does_not_keep_a_provider_secret(services):
    bundle, video = services
    video.interrupt = False
    from app.application.commands import SubmitJob
    from app.application.dispatcher import submit_job

    job_id = submit_job(
        SubmitJob(brief="Brief sk-live-secretvalue", recipe_id="drama_vertical_120s_v1"),
        services=bundle,
    )
    job = JobRepository(bundle.session).get_job(job_id)
    JobRepository(bundle.session).record_event(
        job.version_id,
        "provider.response",
        {"api_key": "sk-live-secretvalue", "status": "ok"},
    )
    bundle.session.commit()
    events = JobRepository(bundle.session).list_events(job.version_id)
    assert "sk-live-secretvalue" not in str(events)
    assert job.brief != "Brief sk-live-secretvalue" or "sk-live" not in job.brief
