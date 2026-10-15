# CLAUDE.md — Agent instructions

Project: richesse-video, an internal autonomous pipeline that renders a 9:16 MP4 from a submitted brief. The CSV/Dreamina handoff workflow is retired. Do not extend `scripts/`, `templates/`, or prompt-library tooling as the product path.

## Active rules

- A job must not wait for human approval between submission and delivery. Use bounded retries and explicit fallbacks.
- Do not call paid APIs or require live credentials. Provider adapters stay unconfigured unless an operator explicitly supplies server-side secrets.
- Never write API keys into code, chat, the database, logs, prompts, or commits. The database stores credential aliases only.
- Product close-ups use approved real media. AI must not generate RICHESSE logo, text, labels, or packaging. Spoken product claims must be explicitly approved.
- Provider-specific requests belong only in adapter modules.
- Do not hard-code a price table as a billing source. Record actual provider usage when a response includes it.
- Persist input hashes, recipe version, prompt/template version, provider parameters, lineage, task IDs, and costs.

## Legacy policy, retained as migration input

The old manual gates (script, character lock, storyboard, clip, final cut) are not runtime gates. The same brand constraints above are the inputs to recipe and domain validation.
