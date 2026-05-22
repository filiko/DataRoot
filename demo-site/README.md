# DataRoot — Demo Site

The DataRoot pitch demo: a rebranded copy of the DFDMaker app. The landing page
and an **Ask | Edit** workspace tell the DataRoot story — scattered files become
a traversable, cited knowledge base.

- **Ask** — customer-facing, fully scripted Q&A with cited source trails. No
  backend or LLM call.
- **Edit** — the full ERD/DFD editor, loaded with a real City of Austin permits
  schema (permits, plan_reviews, code_complaints, code_tasks).

Built by copying `DFDMaker/frontend` + `DFDMaker/backend` here, then adding the
Ask view and rebranding. The original DFDMaker repo is untouched.

## Ports

Ports encode the product name on a phone keypad:

| Service  | Port | Key  |
|----------|------|------|
| Backend  | 3282 | DATA |
| Frontend | 7668 | ROOT |

## Run the demo

Two processes. Start the backend first.

### 1. Backend (port 3282)

```powershell
cd demo-site/backend
$env:AUTH_DISABLED = "1"          # no-login demo mode (auto dev user)
$env:SECRET_KEY = "demo-secret"
python -m uvicorn main:app --host 127.0.0.1 --port 3282
```

`AUTH_DISABLED=1` makes `/auth/me` return a local dev user, so the demo skips
login entirely. Backend deps: `pip install -r requirements.txt` if needed.

### 2. Frontend (port 7668)

```powershell
cd demo-site/frontend
npm install        # first run only (node_modules is gitignored)
npm run dev        # → http://localhost:7668
```

## Demo flow

1. Open `http://localhost:7668` — DataRoot landing page (chalkboard theme).
2. Click **Run the demo →** — loads the Austin Permits knowledge base.
3. Workspace opens on the **Ask** tab — pick a scripted question, see the answer
   and its cited source trail.
4. Click **See these tables in Edit** (or the **Edit** tab) — the full ERD of
   the linked permit tables. DFD / Schema / Export tabs all work.

## Notes

- The Edit project is served from `austin_permits.dfd.json` via the
  `/schema/example` endpoint. The backend's `apply_rules_gate` auto-generates the
  DFD and review proposals from the ERD on load.
- Ask content is scripted in `frontend/src/components/datademo/demoData.ts`.
- The chalkboard (dark forest green) theme is the DataRoot brand default.
