from uuid import UUID, uuid4

from app.domain.models import AssetOrigin
from app.infrastructure.repositories import ArtifactWrite, JobRepository


def _job_id(location: str) -> UUID:
    return UUID(location.rstrip("/").split("/")[-1])


def test_form_submission_rejects_api_key_and_shows_status(client):
    page = client.get("/jobs/new")
    assert page.status_code == 200
    assert "brief" in page.text

    rejected = client.post(
        "/jobs",
        data={
            "brief": "Hai người gặp lại dưới mưa.",
            "recipe_id": "drama_vertical_120s_v1",
            "budget_cap": "5.00",
            "api_key": "sk-live-secret",
        },
    )
    assert rejected.status_code == 422
    assert "sk-live-secret" not in rejected.text

    created = client.post(
        "/jobs",
        data={
            "brief": "Hai người gặp lại dưới mưa.",
            "recipe_id": "drama_vertical_120s_v1",
            "budget_cap": "5.00",
            "approved_asset_ids": "",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    detail = client.get(created.headers["location"])
    assert detail.status_code == 200
    assert "Hai người gặp lại dưới mưa." in detail.text
    assert 'id="job-status"' in detail.text
    fragment = client.get(created.headers["location"] + "/status")
    assert fragment.status_code == 200
    assert "queued" in fragment.text


def test_download_is_limited_to_the_job_and_rerun_keeps_the_old_version(client):
    created = client.post(
        "/jobs",
        data={"brief": "Một buổi sáng.", "recipe_id": "drama_vertical_120s_v1"},
        follow_redirects=False,
    )
    job_id = _job_id(created.headers["location"])
    session = client.app.state.session_factory()
    jobs = JobRepository(session)
    record = jobs.get_job(job_id)
    asset = client.app.state.store.put_bytes(b"fake-mp4", "video/mp4", AssetOrigin.generated, role="final")
    jobs.save_artifact(
        ArtifactWrite(
            version_id=record.version_id,
            asset_id=asset.asset_id,
            sha256=asset.sha256,
            uri=asset.uri,
            media_type=asset.media_type,
            origin=asset.origin,
            role="final",
            lineage={"stage": "render", "kind": "mp4"},
            cost="0",
        )
    )
    session.commit()

    assert client.get(f"/jobs/{job_id}/artifacts/{uuid4()}").status_code == 404
    downloaded = client.get(f"/jobs/{job_id}/artifacts/{asset.asset_id}")
    assert downloaded.status_code == 200
    assert downloaded.content == b"fake-mp4"

    rerun = client.post(
        f"/jobs/{job_id}/reruns",
        data={"storyboard_ids": "b0"},
        follow_redirects=False,
    )
    assert rerun.status_code == 303
    assert jobs.get_job(job_id).version_number == 2
    assert jobs.get_version(job_id, 1).recipe_id == "drama_vertical_120s_v1"
    assert jobs.get_artifact(asset.asset_id).role == "final"
    session.close()
