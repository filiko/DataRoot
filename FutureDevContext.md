# Future Development Context

This file is a handoff for the DataRoot Miro demo work as of 2026-05-09.

## Current Status

The Miro renderer is implemented and live-tested. DataRoot can profile a company workspace, link records into a markdown knowledge base, answer a deterministic research question with provenance, persist the inquiry/provenance docs, and render the provenance graph onto a Miro board as header plus swimlanes.

The local Miro panel/backend is now implemented:

- `GET /miro/` serves the panel UI.
- `POST /api/ask-render` profiles/links a selected company, answers a question, persists inquiry/provenance docs, and renders to Miro.
- `dataroot serve --host 127.0.0.1 --port 8001` runs the local panel.
- The local dev server was started at `http://127.0.0.1:8001/miro/`.

Known live proof:

- Miro board URL: `https://miro.com/app/board/uXjVHVqV-rs=/`
- Evidence folder: `artifacts/miro_live_run_20260509_121133/`
- Live run summary: `artifacts/miro_live_run_20260509_121133/live_miro_summary.json`
- The run created a CompanyA provenance render with header frame, swimlane frames, shapes, citation stickies, and connectors.

Important security note: Miro app credentials and access tokens were pasted during local testing. Those secrets must be rotated in Miro before any shared demo, Railway deployment, commit, recording, or judge access. Do not store tokens in the repo.

## Local Demo vs Railway

For local development, the Miro app panel can point to a server running on the same laptop, for example `http://localhost:8000/miro/`. This works when the same person is using Miro and running the backend locally.

Railway or another public HTTPS host is needed when:

- Someone else needs to use the Miro app from their own computer.
- Judges need to click the Miro app without running the backend locally.
- Miro iframe/app configuration rejects a local URL for the intended install flow.

The recommended path is:

1. Build and validate the local FastAPI panel/backend.
2. Confirm it can ask a question and render to Miro from the laptop.
3. Rotate Miro secrets.
4. Deploy the same backend to Railway.
5. Update the Miro app panel URL to the Railway HTTPS URL.

The user mentioned a Railway helper repo at:

`C:\Users\ajfil\Documents\Github\DevTools\RailwayBot`

Use it only after the local end-to-end flow is confirmed.

## Target Architecture

The near-term demo architecture is:

1. Miro app panel loads a small web UI served by DataRoot.
2. User selects a company dataset and asks a question.
3. Backend profiles/links the selected company into a cached KB if needed.
4. Backend answers the question and persists an inquiry plus provenance trace.
5. Backend renders the provenance trace onto the target Miro board.
6. Panel displays the answer, provenance slug, and Miro board URL.

The first backend can run locally. Later the same service can run on Railway.

## Board Strategy

Use separate boards for polished examples and interactive asks:

- CompanyA example board: curated tomato readiness proof.
- CompanyA ask board: live user questions about tomato lines, genes, inventory, and readiness.
- CompanyB example board: curated fermentation/scale-up proof.
- CompanyB ask board: live user questions about runs, compounds, bioreactors, QC, and release timing.

The existing renderer appends each render group below prior content. This preserves history and makes repeated asks visible on the same board.

Useful environment variables:

- `MIRO_ACCESS_TOKEN`
- `MIRO_BOARD_ID`
- `MIRO_COMPANY_A_EXAMPLE_BOARD_ID`
- `MIRO_COMPANY_A_ASK_BOARD_ID`
- `MIRO_COMPANY_B_EXAMPLE_BOARD_ID`
- `MIRO_COMPANY_B_ASK_BOARD_ID`
- `OPENAI_API_KEY` if model-backed asking is enabled
- `DATAROOT_USE_MODEL_ASK=1` to opt into the model path once it is stable

## Current Gaps

- The local Miro app panel/backend exists, but it has not been deployed to Railway yet.
- The deterministic `dataroot ask` path works for the original demo questions plus targeted follow-up asks for powdery mildew genes and upcoming/near-term availability.
- The model-backed agent loop exists in the repo, but the local demo should default to deterministic handlers until the panel flow is stable.
- Git-backed KB storage is not required for the Miro demo. The Windows environment previously lacked `gitkb`, so local markdown storage is the safer default.
- Railway deployment should happen only after local panel testing passes.
- The local panel reached Miro from `/api/ask-render`, but the current `.env` Miro access token is not a usable live token. The API returned `401 tokenNotProvided` on 2026-05-09. Replace it with a rotated token before the next live render.

## Immediate Development Plan

Completed locally:

1. FastAPI server serving `/miro/` and `/api/ask-render`.
2. `dataroot serve` command.
3. Company KB cache under `.dataroot/server_cache/`.
4. Deterministic follow-up answers for tomato PMR genes and near-term availability.
5. API wiring for persist plus Miro render.
6. Mocked server tests.

Remaining:

1. Rotate Miro credentials and update local `.env`.
2. Rerun a live `/api/ask-render` call and confirm the panel renders to Miro.
3. Deploy the same FastAPI app to Railway.
4. Update the Miro app panel URL to the Railway HTTPS URL for judges/shared users.
