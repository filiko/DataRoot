# DataRoot Demo Site

The active DataRoot demo site is a Nexus-first ERD/DFD application built from
the best DFDMaker editor/generator pieces plus DataRoot's behavioral metadata
layer.

## What Is Here

- `backend/`: FastAPI backend for project import/save, diagram rules, typed ops,
  repo analysis, exports, and Ask.
- `frontend/`: React/Vite editor with ERD, DFD, Business Rules, Connectors,
  Schema, and Export tabs.
- `frontend/public/nexus/`: Nexus Ag master map and 11 module-specific
  `.dfd.json` examples.
- `frontend/public/*.dfd.json`: Austin, store, DataRoot schema, and candidate
  exercise fixtures.

## Ports

| Service | Port | Key |
| --- | ---: | --- |
| Backend | 3282 | DATA |
| Frontend | 7668 | ROOT |

## Run Locally

Start the backend first:

```bash
cd demo-site/backend
AUTH_DISABLED=1 SECRET_KEY=demo-secret python -m uvicorn main:app --host 127.0.0.1 --port 3282
```

Then start the frontend:

```bash
cd demo-site/frontend
npm install
npm run dev
```

Open:

- `http://localhost:7668/nexusag` for the Nexus Ag master and module carousel.
- `http://localhost:7668/demo` for the smaller demo fixture switcher.
- `http://localhost:7668` for the landing page.

## Nexus Acceptance Flow

1. Load `/nexusag`.
2. Confirm the master map opens first.
3. Switch through Identity, Control Numbers, Genetics, Cultivation/Harvest,
   Refinement/Packaging, QA/Lab, Quality/Batch, Product Master, Consumer
   Profile, Sales/CRM, and Finance/AI.
4. For modules with metadata, verify Business Rules and Connectors tabs show
   their records after backend import/save.
5. Verify ERD/DFD layout changes persist and SQL/Mermaid/DBML exports still
   ignore behavioral metadata.

## Notes

- The backend `apply_rules_gate` preserves `dfd.business_rules` and
  `dfd.connectors` when regenerating derived DFD objects.
- Nexus entity `domain` and `connects` fields drive neutral domain rendering
  and highlighted connection-point styling in the ERD canvas.
- External board rendering is not part of this demo app.
