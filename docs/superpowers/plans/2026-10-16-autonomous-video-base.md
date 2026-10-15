# Autonomous Video Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the CSV/manual-production repository with a private internal web application whose mocked development pipeline reliably renders a vertical MP4 from a submitted brief.

**Architecture:** Build a Python modular monolith. FastAPI serves a Jinja/HTMX internal UI and JSON endpoints; SQLAlchemy persists versioned jobs, artifacts, attempts, and durable tasks; a separate worker claims database tasks and runs a provider-neutral DAG. Local filesystem storage and deterministic fake providers make the complete base testable without credentials; Seedance, MiniMax, object storage, and CapCut remain swappable adapter ports.

**Tech Stack:** Python 3.12, uv, FastAPI, Jinja2, HTMX, SQLAlchemy 2, Pydantic 2, SQLite for development/tests, PostgreSQL-compatible database URL for deployment, FFmpeg, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-16-autonomous-video-production-design.md`

## Global Constraints

- Work directly on `main`; do not create a worktree.
- Do not call paid APIs, require live credentials, or expose credentials in the UI, database, logs, test data, or commits.
- A job must never wait for human approval between submission and delivery; bounded retries and explicit fallbacks are mandatory.
- All source media entering the renderer must be validated; close-up product media must be real approved assets, never AI-generated branding.
- Provider-specific requests belong only in adapter modules; domain, workflow, and timeline code must be provider-neutral.
- Use actual provider usage when available for costs; no price table may be hard-coded as a billing source.
- Preserve reproducibility: persist input hashes, recipe version, prompt/template version, provider/model parameters, lineage, task IDs, and costs.
- The base supports the `drama_vertical_120s_v1` recipe: 9:16, 10–12 storyboards, one/two shots per storyboard, configurable nine-image reference pack, 720p default.

## Review Focus

- A worker crash after an external task submission must resume/poll the same `GenerationAttempt`, not submit and bill a duplicate task; test in Task 5.
- A job at its hard budget cap must finish through only existing valid media/fallbacks, never launch another paid attempt; test in Task 6.
- A failed or malformed clip must not enter the final timeline; test in Task 7.
- A recipe that changes reference count or storyboard count must run without code changes; test in Task 3.
- A secrets-looking form value, prompt, or provider response must not appear in persisted events or rendered HTML; test in Task 9.

---

## Repository audit — 2026-10-16

**Current position:** Task 1 has been started locally but is not yet a usable or committed baseline. The following files are present only as untracked work: `pyproject.toml`, `uv.lock`, `app/`, `tests/`, `Dockerfile`, and `docker-compose.yml`. No implementation for Tasks 2–10 exists yet.

**Verified:** the two intended Task-1 tests pass with an explicit database URL when invoked as `DATABASE_URL=sqlite:///test.db uv run python -m pytest tests/test_app.py -v`.

**Blocking gaps before Task 2:**

- The plan's required command, `uv run pytest tests/test_app.py -v`, fails during collection with `ModuleNotFoundError: app`; make the application importable under the standard pytest invocation.
- `Settings` reads `.env`, which conflicts with the stated environment-only configuration policy. Decide and document one configuration contract, and make the test suite independent of any developer `.env` file.
- `README.md`, `.env.example`, `.gitignore`, and `CLAUDE.md` still document the retired CSV/Dreamina workflow. `.env.example` lacks `DATABASE_URL`; the Docker image does not install from the lockfile; and Compose has no worker/media-volume design yet.
- Baseline checks are not clean: Ruff reports legacy `scripts/future_api/_common.py` is executable without a shebang, and mypy reports `app/main.py` constructs `Settings` without the required `database_url` argument.
- Preserve the existing RICHESSE rules during migration: product close-ups use approved real media, AI must not generate logo/text/labels/packaging, and spoken product claims must be explicitly approved. These become recipe/domain validation fixtures in Tasks 2 and 10.

### Task 0: Stabilize and commit the existing scaffold

**Purpose:** turn the current untracked starting point into a reproducible baseline before introducing domain or persistence code. This prevents subsequent work from being built on a test command that differs between developer machines.

**Files:**
- Modify: `pyproject.toml`, `app/main.py`, `app/core/settings.py`, `tests/test_app.py`, `Dockerfile`, `docker-compose.yml`, `README.md`, `.env.example`, `.gitignore`, `CLAUDE.md`
- Add to version control: current untracked Task-1 files and `uv.lock`

- [ ] **Step 1: Write a regression test that executes under `uv run pytest` without relying on a developer `.env`; keep the missing-`DATABASE_URL` validation test.**
- [ ] **Step 2: Configure the project/package path and application factory so imports and settings behave consistently in tests, Uvicorn, and Docker.**
- [ ] **Step 3: Align configuration and deployment files:** document every non-secret setting, add a non-secret `DATABASE_URL` development example, install from `uv.lock`, and define the intended database/media/worker service boundaries without adding credentials.
- [ ] **Step 4: Rewrite the short operator and agent introduction to identify the autonomous-base migration; retain the legacy policies only as migration inputs, not active operating instructions.**
- [ ] **Step 5: Run `uv run pytest tests/test_app.py -v`, `uv run ruff check .`, and `uv run mypy app`; record clean output and commit the baseline.**

**Exit criteria:** a fresh checkout can run the health test with the exact documented command; no hidden `.env` is required; the active documentation no longer directs operators to produce CSV/Dreamina handoffs; and the resulting baseline is committed before Task 2 begins.

---

## File Structure

```text
app/
  api/                 # FastAPI routes and form/JSON request translation
  application/         # commands, workflow runner, task dispatcher
  domain/              # Pydantic value objects, enums, validation, ports
  infrastructure/      # SQLAlchemy models/repos, local storage, settings
  providers/           # fake implementations and future Seedance/MiniMax ports
  rendering/           # timeline compiler and FFmpeg renderer
  web/                 # Jinja templates, static CSS, HTMX fragments
  worker.py             # durable worker process entrypoint
  main.py               # web application entrypoint
tests/                  # mirrors app modules; no live network tests
docker-compose.yml      # app, worker, PostgreSQL, mounted media volume
pyproject.toml          # locked Python project/development tools
README.md               # product setup and internal-operator guide
.env.example            # non-secret aliases/configuration only
```

### Task 1: Replace legacy scaffold with a runnable Python application skeleton

**Files:**
- Create: `pyproject.toml`, `app/__init__.py`, `app/main.py`, `app/core/settings.py`, `tests/test_app.py`, `docker-compose.yml`, `Dockerfile`
- Modify: `README.md`, `.env.example`, `.gitignore`
- Delete: obsolete CSV-only scripts, templates, prompt library, and manual-only skills after their product policies have been migrated in Task 3

**Interfaces:**
- Produces `create_app() -> FastAPI` and `Settings` loaded exclusively from environment variables.
- Later tasks mount routes on `create_app` and request paths through its test client.

- [ ] **Step 1: Write failing app-health and settings tests**

```python
def test_health_endpoint_reports_application_name(client):
    assert client.get("/health").json() == {"status": "ok", "service": "richesse-video"}

def test_settings_rejects_missing_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError):
        Settings()
```

- [ ] **Step 2: Run `uv run pytest tests/test_app.py -v` and verify the imports/endpoints fail**
- [ ] **Step 3: Create the uv/FastAPI project, explicit environment-only settings, health route, development Docker services, and operator README**
- [ ] **Step 4: Run `uv run pytest tests/test_app.py -v` and verify it passes**
- [ ] **Step 5: Commit the scaffold**

### Task 2: Define durable domain contracts and recipe validation

**Files:**
- Create: `app/domain/models.py`, `app/domain/ports.py`, `app/domain/recipes.py`, `tests/domain/test_models.py`, `tests/domain/test_recipes.py`, `app/recipes/drama_vertical_120s_v1.yaml`

**Interfaces:**
- Produces `Recipe`, `EpisodePlan`, `Storyboard`, `Shot`, `AssetRef`, `Timeline`, `JobStatus`, and `TaskStatus` value objects.
- Produces `load_recipe(path: Path) -> Recipe` and `EpisodePlan.validate_for(recipe: Recipe) -> None`.

- [ ] **Step 1: Write failing tests for a 10-storyboard valid plan, a configurable five-reference recipe, and invalid 9:16/storyboard-count/AI-product-closeup plans**
- [ ] **Step 2: Run `uv run pytest tests/domain -v` and verify failure**
- [ ] **Step 3: Implement typed Pydantic contracts and YAML recipe validation; make reference count a recipe field, never a constant**
- [ ] **Step 4: Run `uv run pytest tests/domain -v` and verify pass**
- [ ] **Step 5: Commit domain contracts and default recipe**

### Task 3: Persist jobs, artifacts, attempts, events, and durable tasks

**Files:**
- Create: `app/infrastructure/database.py`, `app/infrastructure/orm.py`, `app/infrastructure/repositories.py`, `tests/infrastructure/test_repositories.py`

**Interfaces:**
- Produces `JobRepository.create_job(...)`, `get_job(job_id)`, `record_event(...)`, `save_artifact(...)`, `save_attempt(...)`, and `TaskRepository.enqueue(...)`, `claim(worker_id, now)`, `complete(task_id)`, `release_expired(now)`.
- Consumes all domain value objects from Task 2.

- [ ] **Step 1: Write failing repository tests that create an immutable job version, persist artifact lineage/cost, and atomically claim one task once**
- [ ] **Step 2: Run `uv run pytest tests/infrastructure/test_repositories.py -v` and verify failure**
- [ ] **Step 3: Implement SQLAlchemy tables and repositories, with SQLite tests and PostgreSQL-compatible URLs; persist only credential aliases**
- [ ] **Step 4: Add and pass a test that a changed recipe produces a new `JobVersion` rather than mutating its predecessor**
- [ ] **Step 5: Commit persistence layer**

### Task 4: Implement local artifact storage and provider-neutral fake adapters

**Files:**
- Create: `app/infrastructure/storage.py`, `app/providers/fake.py`, `app/providers/seedance.py`, `app/providers/minimax.py`, `tests/providers/test_fake.py`, `tests/infrastructure/test_storage.py`

**Interfaces:**
- Produces `ArtifactStore.put_bytes(...) -> AssetRef`, `get_path(asset_id) -> Path`.
- Implements port methods `Planner.plan(...)`, `ImageGenerator.generate(...)`, `SpeechGenerator.synthesize(...)`, `VideoGenerator.submit/poll/retrieve(...)`, and `VisualEvaluator.evaluate(...)`.
- Seedance/MiniMax classes must expose configuration validation only and raise a clear `ProviderNotConfigured` before any HTTP call when credentials are absent.

- [ ] **Step 1: Write failing tests for content-addressed storage, deterministic fake plan/reference/voice/video results, and unconfigured provider behavior**
- [ ] **Step 2: Run `uv run pytest tests/providers tests/infrastructure/test_storage.py -v` and verify failure**
- [ ] **Step 3: Implement local storage, deterministic fake adapters, and credential-gated Seedance/MiniMax adapter shells without live calls**
- [ ] **Step 4: Run the adapter/storage test subset and verify pass**
- [ ] **Step 5: Commit storage and adapters**

### Task 5: Add idempotent task dispatch and resumable workflow orchestration

**Files:**
- Create: `app/application/commands.py`, `app/application/workflow.py`, `app/application/dispatcher.py`, `app/worker.py`, `tests/application/test_workflow.py`, `tests/application/test_dispatcher.py`

**Interfaces:**
- Produces `submit_job(command: SubmitJob) -> UUID`, `advance_job(job_id: UUID) -> None`, and `run_once(worker_id: str) -> int`.
- Consumes repositories, recipe, provider ports, and store from Tasks 2–4.

- [ ] **Step 1: Write failing tests for the queued→planning→references/voice parallel stages, stable idempotency keys, and resume after an attempt has an external task ID**
- [ ] **Step 2: Run `uv run pytest tests/application -v` and verify failure**
- [ ] **Step 3: Implement the database-backed dispatcher, task leases, explicit job transitions, and worker command; never perform long generation in a route handler**
- [ ] **Step 4: Add and pass a test that a re-run dispatches no duplicate generation attempt after simulated worker interruption**
- [ ] **Step 5: Commit dispatcher and workflow**

### Task 6: Enforce budget/retry/fallback policy and automatic candidate selection

**Files:**
- Create: `app/application/policy.py`, `app/application/qc.py`, `tests/application/test_policy.py`, `tests/application/test_qc.py`
- Modify: `app/application/workflow.py`

**Interfaces:**
- Produces `BudgetPolicy.can_start_attempt(job, estimate) -> bool`, `RetryPolicy.next_action(...) -> RetryAction`, and `select_candidate(candidates) -> CandidateSelection`.
- Workflow emits `delivered_with_flags` only after every timeline position has technically valid media or a recipe fallback.

- [ ] **Step 1: Write failing tests for hard-cap denial, max-attempt fallback, invalid-candidate rejection, highest-soft-score selection, and low-confidence flags**
- [ ] **Step 2: Run `uv run pytest tests/application/test_policy.py tests/application/test_qc.py -v` and verify failure**
- [ ] **Step 3: Implement policy objects and integrate them before each provider attempt and timeline selection**
- [ ] **Step 4: Add and pass a test that cap exhaustion still reaches delivery through existing valid assets/fallback without a new generation call**
- [ ] **Step 5: Commit quality/cost policy**

### Task 7: Compile and render a validated final timeline

**Files:**
- Create: `app/rendering/timeline.py`, `app/rendering/ffmpeg.py`, `app/rendering/subtitles.py`, `tests/rendering/test_timeline.py`, `tests/rendering/test_ffmpeg.py`, `tests/fixtures/`
- Modify: `app/application/workflow.py`

**Interfaces:**
- Produces `build_timeline(plan, selections, voices) -> Timeline` and `FfmpegRenderer.render(timeline, output_dir) -> RenderArtifact`.
- `MediaInspector.validate(path, required_duration, aspect_ratio) -> MediaMetadata` prevents invalid assets from rendering.

- [ ] **Step 1: Write failing tests for ordered storyboards, voice-driven timing, SRT generation, rejection of a wrong-aspect/unreadable fixture, and a tiny playable MP4 render**
- [ ] **Step 2: Run `uv run pytest tests/rendering -v` and verify failure**
- [ ] **Step 3: Implement timeline compilation, FFprobe validation, FFmpeg normalization/concat/audio mix/subtitle output, and deterministic reference-image fallback motion**
- [ ] **Step 4: Run `uv run pytest tests/rendering -v` and verify pass when FFmpeg is available; document the skip reason otherwise**
- [ ] **Step 5: Commit renderer**

### Task 8: Expose internal job API and browser UI

**Files:**
- Create: `app/api/routes/jobs.py`, `app/api/routes/health.py`, `app/web/templates/base.html`, `app/web/templates/jobs/new.html`, `app/web/templates/jobs/detail.html`, `app/web/templates/jobs/result.html`, `app/web/static/app.css`, `tests/api/test_jobs.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces `POST /jobs`, `GET /jobs/{job_id}`, `POST /jobs/{job_id}/reruns`, `GET /jobs/{job_id}/artifacts/{asset_id}`, and HTML routes `/`, `/jobs/new`, `/jobs/{job_id}`.
- `POST /jobs` accepts only a brief, recipe ID, approved-asset IDs, and an optional budget cap; it never accepts provider credentials.

- [ ] **Step 1: Write failing API/browser tests for form submission, status polling fragment, result download access, a selective storyboard rerun, and rejected `api_key` input**
- [ ] **Step 2: Run `uv run pytest tests/api/test_jobs.py -v` and verify failure**
- [ ] **Step 3: Implement routes, Jinja/HTMX templates, an accessible status view, and output download authorization for the internal app**
- [ ] **Step 4: Run API tests and verify pass**
- [ ] **Step 5: Commit API and UI**

### Task 9: Add operational safeguards, docs, and end-to-end verification

**Files:**
- Create: `app/application/redaction.py`, `tests/application/test_redaction.py`, `tests/e2e/test_fake_job.py`
- Modify: `README.md`, `.env.example`, `docker-compose.yml`, `.gitignore`

**Interfaces:**
- Produces `redact(value: object) -> object` used before all persisted/logged provider payloads.
- The e2e fixture invokes `submit_job` and `run_once` until a delivered job exposes MP4, SRT, timeline manifest, cost, and flags.

- [ ] **Step 1: Write failing redaction and mocked end-to-end tests, including a provider response containing an API-key-shaped value**
- [ ] **Step 2: Run `uv run pytest tests/application/test_redaction.py tests/e2e/test_fake_job.py -v` and verify failure**
- [ ] **Step 3: Implement redaction, health/readiness guidance, Docker startup instructions, media lifecycle/retention configuration, and the complete fake-job test**
- [ ] **Step 4: Run `uv run pytest -v`, `uv run ruff check .`, and `uv run mypy app`; verify all pass**
- [ ] **Step 5: Commit operational base and documentation**

### Task 10: Retire the legacy manual workflow and verify the rebuilt baseline

**Files:**
- Delete: legacy `bible/`, `episodes/`, `prompt_lib/`, `scripts/`, `skills/`, `templates/`, and old manual-flow README content once equivalent product policies are represented in the recipe/domain tests
- Modify: `README.md`, `CLAUDE.md`
- Test: all test suites from Tasks 1–9

**Interfaces:**
- Produces a repository whose public operator documentation describes only the autonomous-base system and marks the old model as retired in Git history.

- [ ] **Step 1: Write a failing repository-layout/documentation test that rejects references to the retired CSV/manual Dreamina workflow**
- [ ] **Step 2: Run the test and verify failure while legacy materials exist**
- [ ] **Step 3: Migrate indispensable brand/product policy to the new recipe/domain fixtures, remove retired source artifacts, and rewrite operator/agent instructions**
- [ ] **Step 4: Run the full test/lint/type suite and a Docker Compose mocked job smoke test**
- [ ] **Step 5: Commit the migration and inspect `git status --short` before handoff**

## Self-review

- **Spec coverage:** Tasks 2–7 implement the stable model, configurable recipe, DAG, adapters, retries/fallbacks, and renderer. Task 8 implements the three internal screens. Tasks 3, 5, 6, and 9 cover durability, cost, security, observability, and tests. Task 10 replaces the retired scope.
- **Step scan:** Each task follows a red/green/commit cycle and declares a concrete test command and public interfaces.
- **Type consistency:** `Recipe`, `EpisodePlan`, ports, repositories, `submit_job`, `advance_job`, `run_once`, `build_timeline`, and `FfmpegRenderer.render` are defined before consuming tasks.
- **Review focus:** Each of the five listed failure modes is assigned to Tasks 3, 5, 6, 7, 2, and 9 with an explicit test.
- **Proportion:** The plan describes a complete, testable base but intentionally defers authenticated live provider calls, object-store deployment, CapCut integration, social publishing, and a full timeline editor.

