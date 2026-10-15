from collections.abc import Iterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.application.commands import SubmitJob
from app.application.dispatcher import submit_job
from app.application.workflow import Services
from app.infrastructure.repositories import ArtifactRecord
from app.worker import build_services


def open_services(request: Request) -> Iterator[Services]:
    session = request.app.state.session_factory()
    services = build_services(session, request.app.state.store)
    request.state.services = services
    try:
        yield services
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


router = APIRouter(dependencies=[Depends(open_services)])


def _services(request: Request) -> Services:
    services = getattr(request.state, "services", None)
    if not isinstance(services, Services):
        raise TypeError("services are not on the request")
    return services


def _page(request: Request, name: str, context: dict[str, object] | None = None) -> HTMLResponse:
    response = request.app.state.templates.TemplateResponse(request, name, context or {})
    if not isinstance(response, HTMLResponse):
        raise TypeError("expected an HTML response")
    return response


def _final_asset_id(services: Services, version_id: UUID) -> UUID | None:
    for artifact in services.jobs.list_artifacts(version_id):
        if artifact.lineage.get("kind") == "mp4" or artifact.role == "final":
            return artifact.asset_id
    return None


def _owned_artifact(services: Services, job_id: UUID, asset_id: UUID) -> ArtifactRecord | None:
    latest = services.jobs.get_job(job_id)
    for number in range(1, latest.version_number + 1):
        version = services.jobs.get_version(job_id, number)
        for artifact in services.jobs.list_artifacts(version.version_id):
            if artifact.asset_id == asset_id:
                return artifact
    return None


@router.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    return _page(request, "index.html")


@router.get("/jobs/new", response_class=HTMLResponse)
def new_job(request: Request) -> HTMLResponse:
    return _page(request, "jobs/new.html")


@router.post("/jobs")
async def create_job(request: Request) -> RedirectResponse:
    form = await request.form()
    if "api_key" in form:
        raise HTTPException(status_code=422, detail="credentials are not accepted")
    brief = str(form.get("brief") or "")
    recipe_id = str(form.get("recipe_id") or "")
    budget = str(form.get("budget_cap") or "") or None
    raw_assets = str(form.get("approved_asset_ids") or "")
    approved = [UUID(item) for item in raw_assets.split(",") if item.strip()]
    job_id = submit_job(
        SubmitJob(
            brief=brief,
            recipe_id=recipe_id,
            approved_asset_ids=approved,
            budget_cap=budget,
        ),
        services=_services(request),
    )
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: UUID, request: Request) -> HTMLResponse:
    services = _services(request)
    job = services.jobs.get_job(job_id)
    return _page(
        request,
        "jobs/detail.html",
        {
            "job": job,
            "final_asset_id": _final_asset_id(services, job.version_id),
        },
    )


@router.get("/jobs/{job_id}/status", response_class=HTMLResponse)
def job_status(job_id: UUID, request: Request) -> HTMLResponse:
    job = _services(request).jobs.get_job(job_id)
    return _page(request, "jobs/status.html", {"job": job})


@router.get("/jobs/{job_id}/result", response_class=HTMLResponse)
def job_result(job_id: UUID, request: Request) -> HTMLResponse:
    services = _services(request)
    job = services.jobs.get_job(job_id)
    return _page(
        request,
        "jobs/result.html",
        {
            "job": job,
            "final_asset_id": _final_asset_id(services, job.version_id),
        },
    )


@router.post("/jobs/{job_id}/reruns")
async def rerun_job(job_id: UUID, request: Request) -> RedirectResponse:
    form = await request.form()
    if "api_key" in form:
        raise HTTPException(status_code=422, detail="credentials are not accepted")
    services = _services(request)
    current = services.jobs.get_job(job_id)
    revised = services.jobs.add_version(
        job_id=job_id,
        brief=current.brief,
        recipe_id=current.recipe_id,
        recipe_hash=current.recipe_hash,
        budget_cap=current.budget_cap,
    )
    storyboards = str(form.get("storyboard_ids") or "")
    services.jobs.record_event(
        revised.version_id,
        "job.rerun",
        {"storyboard_ids": [item for item in storyboards.split(",") if item]},
    )
    services.session.commit()
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@router.get("/jobs/{job_id}/artifacts/{asset_id}")
def download_artifact(job_id: UUID, asset_id: UUID, request: Request) -> FileResponse:
    services = _services(request)
    try:
        artifact = _owned_artifact(services, job_id, asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404) from exc
    if artifact is None:
        raise HTTPException(status_code=404)
    try:
        path = services.store.get_path(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404) from exc
    return FileResponse(path, media_type=artifact.media_type, filename=path.name)
