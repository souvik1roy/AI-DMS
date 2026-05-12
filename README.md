# OrganiseAI (web)

Web document organiser. Users drag-and-drop PDFs / images into the browser; the
backend parses them with OpenAI, organises them into an entity / type / date
folder tree, and stores everything in Supabase Storage. Metadata (jobs,
documents, taxonomy) lives in Supabase Postgres.

## Status

Migrated from a Tauri desktop bundle to a pure web stack. Single-tenant
(bearer-token auth — share the token with whoever should use the app).

## Architecture in one paragraph

The browser UI ([ui/](ui/), React + Vite) talks to the sidecar
([sidecar/](sidecar/), FastAPI) over plain HTTPS with a bearer token. The user
drag-and-drops files into the New Job page; the UI POSTs them as multipart to
`/runs/upload`. The sidecar streams each file into the Supabase **staging**
bucket, records it in Postgres, and kicks off the orchestrator
([sidecar/dms/pipeline/job.py](sidecar/dms/pipeline/job.py)) on a worker
thread. The orchestrator renders the first/last page of each PDF to PNG (via
PyMuPDF) — image inputs pass through — uploads those pages back to staging,
and feeds short-lived **signed URLs** to **OpenAI Vision** (`gpt-4o`) for
metadata extraction. Once every doc has metadata, the reasoner step asks
OpenAI to produce a filing plan that extends the existing taxonomy (never
renames). The filer copies each doc from `staging/` to `organized/<prefix>/…`,
verifies SHA-256 round-trips, and updates the document row. The UI gets a
short-lived signed URL whenever the user clicks a filed document.

## Repository layout

| Path | Purpose |
|---|---|
| [ui/](ui/) | React + Vite frontend deployed to Vercel |
| [sidecar/](sidecar/) | Python FastAPI backend, runs as a container on Render |
| [sidecar/dms/storage/](sidecar/dms/storage/) | Supabase Storage REST wrapper |
| [sidecar/dms/db/schema_pg.sql](sidecar/dms/db/schema_pg.sql) | Postgres schema (apply once via Supabase SQL editor) |
| [scripts/](scripts/) | Dev launcher + SQLite→Postgres migrator |
| [render.yaml](render.yaml) | Render service definition for the sidecar |
| [.github/workflows/deploy.yml](.github/workflows/deploy.yml) | UI → Vercel, sidecar → Render |

## Prerequisites (one-time)

1. **Supabase project**
   - Create the project; from *Settings → API* note `SUPABASE_URL` and the
     service-role key (`SUPABASE_SERVICE_ROLE_KEY`).
   - From *Settings → Database* copy the **connection pooler** URI as
     `DATABASE_URL`.
   - In *SQL Editor* run [sidecar/dms/db/schema_pg.sql](sidecar/dms/db/schema_pg.sql).
   - In *Storage* create two **private** buckets: `staging`, `organized`.

2. **OpenAI**
   - Create an API key; this is `OPENAI_API_KEY`.

3. **Bearer token**
   - Generate a long random string for `DMS_BEARER_TOKEN` (used by the UI to
     authenticate against the sidecar). Keep it secret; share only with people
     allowed to upload.

Copy [.env.example](.env.example) and fill in the values for local dev.

## Running locally (no deploy needed)

```bash
# 1. Sidecar venv
python3.11 -m venv sidecar/.venv
sidecar/.venv/bin/pip install -e ./sidecar
cp .env.example sidecar/.env   # fill in DATABASE_URL, OPENAI_API_KEY, SUPABASE_*

# 2. UI deps
cd ui && pnpm install && cd ..

# 3. Boot both with the dev script (Vite + sidecar, handshake JSON wired up)
./scripts/dev-browser.sh

# Open http://127.0.0.1:5173/
```

`scripts/dev-browser.sh` boots the sidecar with a random bearer token, writes
the handshake to `ui/public/_dms_dev_handshake.json`, and starts Vite. The UI
reads that file on first call — no env vars required for local dev.

For Vite to load the sidecar config explicitly (e.g. against a deployed
Render service), set in `ui/.env.local`:

```
VITE_DMS_BASE_URL=https://your-sidecar.onrender.com
VITE_DMS_TOKEN=<the bearer token>
```

## Migrating from the old SQLite desktop build

If you had the desktop app running, run the migrator once to copy your
existing jobs / documents / taxonomy into Postgres:

```bash
DATABASE_URL=postgresql://... \
sidecar/.venv/bin/python scripts/migrate_sqlite_to_pg.py \
    "$HOME/Library/Application Support/AI DMS/dms.db"
```

The script is idempotent (`ON CONFLICT DO NOTHING`), so it's safe to re-run.

> **Note:** the migrator copies *metadata only* — the filed PDFs themselves
> still live on your old machine. Re-upload anything you want managed by the
> web build through the New Job page.

## Deploying

### Sidecar → Render

1. New *Web Service* → "Build and deploy from a Git repo" → select this repo.
2. Render picks up [render.yaml](render.yaml) and uses `sidecar/Dockerfile`.
3. Fill in the env vars listed at the top of `render.yaml` from the Supabase /
   OpenAI / bearer-token values you captured above.
4. After the first deploy, copy the service URL (e.g.
   `https://ai-dms-sidecar.onrender.com`) — that's `VITE_DMS_BASE_URL`.

Render auto-redeploys on push to `main`. The GitHub Action also POSTs the
deploy hook if you set the `RENDER_DEPLOY_HOOK_URL` secret.

### UI → Vercel

Vercel hosts the static React build; the sidecar stays on Render. Five-minute
flow:

1. Go to [vercel.com/new](https://vercel.com/new) → **Import Git Repository** →
   pick `souvik1roy/AI-DMS` (you may need to grant Vercel access first).
2. On the project setup screen:
   - **Framework Preset:** `Vite` (auto-detected)
   - **Root Directory:** `ui` ← required, since the app lives in a subdirectory
   - **Build Command:** leave default (`pnpm run build`)
   - **Output Directory:** leave default (`dist`)
   - **Install Command:** leave default (`pnpm install --frozen-lockfile`)
3. Expand **Environment Variables** and add two:

   | Key | Value |
   |---|---|
   | `VITE_DMS_BASE_URL` | the Render service URL, e.g. `https://ai-dms-sidecar.onrender.com` |
   | `VITE_DMS_TOKEN`    | the same string set as `DMS_BEARER_TOKEN` on Render |

   Apply to **Production**, **Preview**, and **Development** (or just Production
   if you don't want PR previews to share the same key).

4. Click **Deploy**. First build runs `pnpm install` + `pnpm run build` against
   the `ui/` directory. The static `dist/` is published behind Vercel's CDN.
5. Once the deployment URL is live (e.g.
   `https://ai-dms-souvik1roy.vercel.app`), copy that URL.
6. **Allow it through the sidecar's CORS** on Render:
   - Render → your service → **Environment** →
     edit `WEB_ORIGIN` to a comma-separated list including the new Vercel URL,
     e.g. `https://ai-dms-souvik1roy.vercel.app,https://ai-dms.vercel.app`.
   - Save → Render restarts the service automatically.

That's it — open the Vercel URL and you should see the AllysAI dashboard
pulling live data from your Render-hosted sidecar.

Every `git push origin main` auto-deploys via Vercel's GitHub integration —
no GitHub Actions workflow file required.

The repo includes [ui/vercel.json](ui/vercel.json) for the SPA rewrite rules
and asset cache headers, plus a [.vercelignore](.vercelignore) that excludes
the backend / scripts / engine assets from the Vercel build.

#### Local production preview

To rehearse what Vercel will serve before you push:

```bash
cd ui
cp .env.example .env.local            # fill in real values
pnpm install
pnpm run build
pnpm run preview                      # serves dist/ on http://localhost:4173
```

## Cost / capacity notes

- **OpenAI:** every page parsed is one `gpt-4o` Vision call; expect roughly
  $0.01–0.05 per page. A 100-page batch ≈ $1–5. Cap concurrent uploads if you
  want to bound spend.
- **Render starter ($7/mo):** keeps the sidecar warm so long-running jobs
  don't get killed by the free-tier idle shutdown. **Do not scale to more
  than one instance** — the orchestrator's in-memory cancel tokens are
  per-process and there's no queue.
- **Supabase free tier:** 1 GB storage + 500 MB database. Plenty for testing;
  upgrade for production volume.

## Auth model

A single bearer token authenticates every request. Anyone who knows the
token can:

- upload files (and incur OpenAI cost)
- read, cancel, or delete every job and its files
- see all parsed metadata

Keep the token secret. To upgrade to per-user auth, swap the
`_require_bearer` dependency in [sidecar/dms/server.py](sidecar/dms/server.py)
for a Supabase JWT verifier — the schema is already RLS-ready.
