# DataRoot Demo — Railway Deployment

Deployed as **two Railway services** (no Docker), both auto-built by Railway's
Nixpacks builder, plus a managed PostgreSQL database:

| Service | Source folder | Builder | Role |
|---|---|---|---|
| **backend** | `demo-site/backend` | Nixpacks (Python) | FastAPI API |
| **frontend** | `demo-site/frontend` | Nixpacks (Node) | Static React SPA |
| **Postgres** | — | Railway plugin | Database |

The frontend calls the backend cross-origin; the backend allows the frontend's
origin via CORS. The demo runs in open mode (`AUTH_DISABLED=1`).

## One-time setup

### 0. Push the code

Commit and push `demo-site/` to GitHub — Railway deploys from the repo.

### 1. Create the project + database

[railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
→ select the **DataRoot** repo. Then **New** → **Database** → **PostgreSQL**.

### 2. Backend service

1. Add a service from the repo. Rename it **`backend`**.
2. **Settings → Root Directory** → `demo-site/backend`
   (Railway then finds `requirements.txt` and `railway.toml` there automatically.)
3. **Settings → Networking** → **Generate Domain**.
4. **Variables**:

   | Variable | Value |
   |---|---|
   | `AUTH_DISABLED` | `1` |
   | `SECRET_KEY` | output of `python -c "import secrets; print(secrets.token_hex(32))"` |
   | `FRONTEND_ORIGIN` | `https://${{frontend.RAILWAY_PUBLIC_DOMAIN}}` |
   | `DATABASE_URL` | _auto-injected by the Postgres service_ |

### 3. Frontend service

1. Add a second service from the **same repo**. Rename it **`frontend`**.
2. **Settings → Root Directory** → `demo-site/frontend`
3. **Settings → Networking** → **Generate Domain**.
4. **Variables**:

   | Variable | Value |
   |---|---|
   | `VITE_API_URL` | `https://${{backend.RAILWAY_PUBLIC_DOMAIN}}` |

   > `VITE_API_URL` is read at **build time** — Vite bakes it into the bundle.
   > Changing it later requires a redeploy of the frontend service.

### 4. Redeploy both

The `${{backend.*}}` / `${{frontend.*}}` references resolve once both services
have domains. Redeploy both services so each picks up the other's URL.

> Service **names** must be exactly `backend` and `frontend` for the reference
> variables above to resolve. Rename them differently? Update the references to match.

## How each service builds

- **backend** — Nixpacks detects Python from `requirements.txt`, pins Python via
  `.python-version`, and runs the start command from `backend/railway.toml`:
  `python -m uvicorn main:app --host 0.0.0.0 --port $PORT`. Health check: `/health`.
- **frontend** — Nixpacks detects Node from `package.json`, runs `npm run build`
  (→ `dist/`), then `npm run start` (`serve -s dist`, which binds `$PORT`).

## Local development

```powershell
# Backend  — http://localhost:3282
cd demo-site\backend
$env:AUTH_DISABLED = "1"; $env:SECRET_KEY = "demo-secret"
python -m uvicorn main:app --reload --port 3282

# Frontend — http://localhost:7668  (Vite dev server, proxies /api etc. to :3282)
cd demo-site\frontend
npm run dev
```

To preview the production build locally: `npm run build; npm run start`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Frontend loads but API calls fail | Check `VITE_API_URL` on the frontend service points at the backend domain; rebuild the frontend |
| CORS error in the browser console | Set `FRONTEND_ORIGIN` on the backend to the exact frontend URL (`https://…`), then redeploy backend |
| `500` on first request | Postgres still starting — the app retries DB init 10×; wait ~30s |
| Sessions lost on redeploy | Set a fixed `SECRET_KEY` |
| Data gone after redeploy | No Postgres attached — SQLite is ephemeral; add the Postgres service |
| Backend build can't find `requirements.txt` | Root Directory must be `demo-site/backend`, not `demo-site` |
