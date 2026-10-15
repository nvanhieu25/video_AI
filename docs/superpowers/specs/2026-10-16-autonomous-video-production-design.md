# Autonomous video production — design

## 1. Purpose and success criteria

Build a private internal tool that turns one Vietnamese creative brief (normally up to about 4,000 characters) into one finished vertical MP4 without waiting for a human during generation.

The primary launch format is an approximately 120-second drama video made of 10–12 ordered storyboards. A storyboard normally contains one or two shots. Each storyboard receives a nine-image reference pack so its character, wardrobe, setting, lighting, and recurring props remain coherent across its shots.

The human reviews and publishes only after the system delivers the MP4. The system must not pause awaiting approval while it creates the video.

Success means that every completed job produces a playable 9:16 MP4, an audit report, captions, and the inputs needed to reproduce or selectively regenerate any storyboard. Visual quality is scored and reported automatically but remains subject to the human's later review.

## 2. Scope and non-goals

In scope for the first product release:

- Internal web UI for submitting, tracking, and downloading jobs.
- A durable, restart-safe workflow from brief through a rendered MP4.
- Script and storyboard planning; reference-image, speech, and video generation; automatic checks; deterministic rendering.
- Seedance as the first video provider, MiniMax as the first speech provider, and FFmpeg as the required renderer.
- Versioned recipes, provider adapters, per-job budgets, retries, fallbacks, logs, and selective storyboard reruns.

Out of scope:

- A public multi-tenant product, billing, or self-service sign-up.
- A frame-accurate in-browser editor comparable to CapCut.
- Automated publishing to social networks.
- A CapCut API dependency. CapCut may later be an optional adapter if suitable account-level API access is verified.

## 3. Product experience

The MVP has three user-facing screens.

1. **New video**: enter a brief, select a recipe, choose approved character/product assets, and set a budget cap.
2. **Job detail**: display the workflow graph, each storyboard and selected assets, current provider-task state, retries, running cost, and any low-confidence flags. This is observational; it never gates the job.
3. **Result**: play/download `final.mp4`, captions, the render timeline, and the quality report. Users can create a new job version that reruns one or more storyboards without altering completed artifacts.

An internal administration area manages provider credentials, voice profiles, characters, product assets, recipe versions, and default budget policies.

## 4. Architecture

Use a modular monolith rather than microservices. It is a single deployable application with clear module boundaries:

```text
Browser UI
  <-> API application
        |- domain + orchestration engine
        |- durable task queue and workers
        |- provider adapters
        |- renderer adapter (FFmpeg)
        |- PostgreSQL metadata database
        `- object storage for media and artifacts
```

The API never performs long generation work in its request process. It queues idempotent tasks. Workers claim tasks, persist their progress, and can resume after a crash. Jobs are represented as a dependency graph, not a fixed linear script, so independent stages such as reference creation and voice generation can run concurrently.

`n8n` is optional only for notifications, scheduled initiation, or a future operational dashboard. It is not the source of truth and does not contain provider, retry, or rendering logic.

## 5. Stable domain model

The core is provider-neutral. Its principal entities are:

| Entity | Responsibility |
|---|---|
| `Project` | Long-lived brand, character, product, and style library. |
| `RecipeVersion` | Configurable policy: format, storyboard count range, reference-pack policy, provider selection, retry limits, and budget defaults. |
| `Job` / `JobVersion` | One immutable run of a brief and recipe, with an allowed maximum spend. |
| `EpisodePlan` | Structured script, ordered storyboards, dialogue, and intended timing. |
| `Storyboard` / `Shot` | Unit of narrative and regeneration; describes action, references, prompt, audio, and continuity constraints. |
| `Asset` | Immutable media object with hash, storage URI, origin, provider metadata, and lineage. |
| `GenerationAttempt` | A billable provider request, its idempotency key, external task ID, result, error, and cost. |
| `Timeline` | Ordered selected clips, audio placement, subtitles, music, transitions, and render settings. |
| `RenderArtifact` | The final MP4, subtitle file, QC report, and supporting manifest. |

Every generated artifact records the input hashes, prompt-template version, model/provider/version, parameters, seed when available, source asset IDs, and cost. This permits targeted reruns and makes historical jobs reproducible after recipes evolve.

## 6. Configurable workflow

The workflow is selected by a `RecipeVersion`; no code is allowed to assume exactly 12 storyboards or exactly nine references.

The initial `drama_vertical_120s_v1` recipe specifies:

- 9:16 output, target duration about 120 seconds.
- 10–12 storyboards; one or two shots each.
- A nine-image reference pack whose roles are configurable (for example character, wardrobe, location, recurring prop, and product references).
- MiniMax voice synthesis before video creation, so final speech duration drives clip duration and lip-sync input.
- Seedance image-to-video generation for eligible shots. Product close-ups use approved real footage, not AI imagery.
- 720p as the normal generation mode; a later, opt-in hero-shot upgrade recipe may use a higher resolution.
- A default maximum cost, maximum attempts per shot, timeout, and fallback policy.

The generic workflow is:

```text
validate brief and budget
  -> plan episode as JSON
  -> validate plan and reserve budget
  -> create/retrieve reference packs + synthesize voice
  -> create clip candidates per shot
  -> automatic technical/visual QC and candidate selection
  -> construct timeline and subtitles
  -> render and technical-validate final MP4
  -> deliver final artifacts and report
```

## 7. Provider and renderer adapters

The orchestration layer calls capabilities, never vendor SDK code directly:

- `Planner`: create a structured `EpisodePlan` from the brief.
- `ImageGenerator`: generate or retrieve reference images.
- `SpeechGenerator`: synthesize dialogue, return the audio asset and measured duration.
- `VideoGenerator`: submit, poll/webhook, cancel, and retrieve video-generation tasks.
- `VisualEvaluator`: produce a score and reasons for continuity/technical checks.
- `Renderer`: validate source media and render a `Timeline` into an MP4 and captions.

Seedance and MiniMax are concrete adapters; each calls the current supported provider API and stores the provider task ID and returned usage. FFmpeg is the first renderer. A future CapCut integration must implement `Renderer` or a timeline-export adapter without changing the core data model.

## 8. Reliability, quality, and continuity policy

Tasks are idempotent through a stable key derived from job version, stage, storyboard/shot ID, and input hash. A worker restart resumes polling or retrieves a completed provider task rather than submitting a duplicate request.

Automatic QC has two tiers:

- **Hard checks**: schema validity, media readability, 9:16 format, duration, expected audio, no empty frames, and render completion. Failed hard checks cannot enter the timeline.
- **Soft checks**: model/vision scoring for character continuity, motion, lighting, unwanted text/logo, and match to prompt/reference. Scores select the best candidate and flag low confidence.

Each shot receives bounded retries. The system does not wait for a human when retries are exhausted. It chooses the best technically valid candidate; if none exists, it applies the recipe's explicit fallback, such as a reference image animated with a subtle camera movement and the completed voice. The resulting job is marked `delivered_with_flags`, not silently treated as high confidence.

The renderer normalizes source clips, aligns video length to spoken audio, mixes and ducks licensed music under dialogue, produces captions, concatenates in timeline order, and validates the result. It returns a final MP4 even when fallback is used.

## 9. Cost, security, and operations

No provider secret is accepted from the normal job form or stored in prompts/logs. Secrets are supplied to workers through server-side secret management or environment configuration; the database stores only a provider credential alias.

The planner estimates spend before billable work. Workers record actual provider usage, enforce a job hard cap before every new generation attempt, and never retry indefinitely. If the hard cap is reached, the workflow proceeds only with already valid assets and the fallback policy.

The system records structured events for every state transition, external task ID, retry, provider response class, duration, usage, cost, fallback, and render result. It exposes per-job and aggregate metrics: cost per delivered video, cost per accepted second, first-pass acceptance rate, retry rate, fallback rate, and queue latency.

Initial operating estimates use a 720p default and a configurable retry reserve. The application treats pricing as live configuration and calculates actual cost only from provider responses; it does not hard-code public price tables.

## 10. Testing and release criteria

Required test layers:

1. Unit tests for schemas, recipes, duration math, budgeting, DAG transitions, fallback selection, and timeline construction.
2. Adapter contract tests with mocked provider responses, including asynchronous completion, failures, webhooks, and duplicate delivery.
3. Media fixtures for FFmpeg validation and deterministic rendering tests.
4. A fully mocked end-to-end job that produces a playable fixture MP4.
5. A budget-limited staging smoke test using real credentials, run only by explicit operator action.

The first release is accepted when an internal operator can submit a valid brief through the UI; safely interrupt and resume a job; view accumulated cost and task state; selectively regenerate one storyboard; and download a valid vertical MP4, SRT, timeline manifest, and flagged QC report without an approval step during generation.

## 11. Migration from the existing repository

The current CSV-centric, manual-Dreamina process does not match the new scope and will be replaced as the product workflow. Existing brand/product rules remain valuable policy inputs, especially the prohibition on generating product logos/labels and the use of real product footage for close-ups.

Legacy templates and placeholder API scripts should not be extended. The implementation will introduce a new application layout, migrate relevant policy text into versioned recipe/validation assets, and retain the old sample episode only as an explicitly labeled fixture or archive where useful.

