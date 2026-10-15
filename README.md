# richesse-video

Private internal tool that turns one Vietnamese creative brief into a vertical MP4. This repository is migrating from the retired CSV/Dreamina handoff workflow to an autonomous base: submit a brief, and a worker renders the video without waiting for approval during generation.

The human reviews and publishes only after delivery.

## Run the health check

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
export DATABASE_URL=sqlite:///./richesse.db
uv run pytest tests/test_app.py -v
uv run uvicorn app.main:create_app --factory --reload
```

`GET /health` returns `{"status": "ok", "service": "richesse-video"}`.

Settings come from the process environment only. The app does not read a `.env` file. See `.env.example` for the non-secret names: `DATABASE_URL`, `MEDIA_ROOT`, and `SERVICE_NAME`.

## Local services

`docker-compose.yml` defines three boundaries:

- `app` — HTTP API and internal UI
- `worker` — claims durable tasks and runs generation (`python -m app.worker`, added with the dispatcher)
- `postgres` — metadata, with a shared `media` volume mounted at `/media`

The Compose database password is a published local default, not a provider credential. Do not put provider secrets in the job form, the database, logs, or git.

```bash
docker compose up --build
```

## Migration inputs, not operating instructions

The previous manual workflow is retired as the product process. These product rules still constrain the new recipe and domain validation:

- Product close-ups use approved real media, never AI-generated footage.
- AI must not generate RICHESSE logo, text, labels, or packaging.
- Spoken product claims must be explicitly approved.

Those rules belong in versioned recipes and tests. Do not produce `shots.csv` handoffs or create clips by hand as the delivery path.
