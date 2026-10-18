# Career Readiness — FastAPI backend for the Lovable frontend

New files only: `api/`, `tests/`, `requirements-api.txt`, `Procfile`, this README.
`app.py`, `database/`, `models/`, `utils/`, `resume_parser/` are **unchanged** —
the Streamlit app still runs as before with `streamlit run app.py`.

## 1. Run the backend locally (Windows / PowerShell, from this folder)

```powershell
.venv\Scripts\activate
pip install -r requirements-api.txt

$env:DB_HOST="localhost"; $env:DB_USER="root"; $env:DB_PASSWORD=""; $env:DB_NAME="career_readiness_db"
$env:JWT_SECRET="replace-with-a-long-random-string-at-least-32-chars"
$env:CORS_ORIGINS="http://localhost:8080"

uvicorn api.main:app --reload --port 8000
```

- Swagger docs: http://localhost:8000/docs · health: http://localhost:8000/api/health
- Same MySQL database as Streamlit — both apps can run at the same time.
- Make an account admin (same as with Streamlit):
  `UPDATE users SET role='admin' WHERE email='you@example.com';`

**Without MySQL (demo only, data is lost on restart):**
`$env:CAREER_API_FAKE_DB="1"; uvicorn api.main:app --port 8000`
(seeds an admin: `admin@careerforge.local` / `admin12345`).

**Smoke test:** `python -m pytest tests -q` (uses the in-memory DB, never touches MySQL).

## 2. Run the frontend locally

```powershell
cd job-horizon-mapper-main
copy .env.example .env        # VITE_API_URL=http://localhost:8000
npm install
npm run dev                   # http://localhost:8080
```

Open http://localhost:8080 → Sign in / Create account.

## 3. Endpoints (all under `/api`; Bearer JWT unless noted)

| Streamlit page | Endpoint |
|---|---|
| Register (public) | `POST /auth/register` `{name,email,password,confirm_password}` |
| Login (public) | `POST /auth/login` `{email,password}` → `access_token` |
| — | `GET /auth/me`, `GET /workflow` (which steps are done / next step) |
| Profile | `GET /profile`, `PUT /profile`, `GET /profile/options` |
| Resume Upload | `GET /resume`, `POST /resume` (multipart `file`, PDF ≤ 5 MB) |
| Career Recommendation | `GET /career`, `POST /career/recommend`, `POST /career/select` `{use_ai, career}` |
| Skill Gap Analysis | `GET /skill-gap`, `POST /skill-gap/run` |
| Roadmap Generator | `GET /roadmap` (preview), `POST /roadmap/generate` (save) |
| Dashboard | `GET /dashboard` |
| Analytics Dashboard | `GET /analytics` |
| PDF Career Report | `GET /report/status`, `GET /report/pdf` |
| Admin Dashboard (admin role) | `GET /admin/overview`, `GET /admin/users?name=&email=&career_role=`, `GET /admin/users.csv` |

Order enforced exactly like app.py: career needs profile + resume → skill gap needs a
career prediction → roadmap needs a skill gap → PDF needs all five. A missing step returns
HTTP 409 `{"detail": "...", "missing_step": "profile|resume|career|skill_gap"}` and the
frontend shows a "One step first" card linking to that page.

## 4. Environment variables

| Var | Default | Notes |
|---|---|---|
| `DB_HOST` `DB_USER` `DB_PASSWORD` `DB_NAME` | localhost / root / "" / career_readiness_db | read by your existing `database/db_connection.py` |
| `DB_PORT` | 3306 | optional; injected by the API layer (db_connection.py has no port option) |
| `JWT_SECRET` | insecure dev default | **must set in production** |
| `JWT_EXPIRE_MINUTES` | 1440 | token lifetime |
| `CORS_ORIGINS` | localhost ports | comma-separated frontend URLs |
| `CORS_ORIGIN_REGEX` | — | e.g. `https://.*\.vercel\.app` for preview deploys |
| `CAREER_API_FAKE_DB` | — | `1` = in-memory SQLite (demo/tests only) |

## 5. Deploying to production

You need three things: **MySQL**, the **FastAPI backend**, the **frontend**.

### MySQL
- **Railway MySQL** (simplest if the backend is on Railway), **Aiven for MySQL** (free tier),
  or any managed MySQL. Set `DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME` from its dashboard.
- The first connection auto-creates the schema via your `schema.sql` + the
  `create_*_table_if_missing()` functions. ⚠ On a **brand-new** database, run this once after the
  first start, then restart the API:
  ```sql
  DROP TABLE IF EXISTS skill_gap, roadmaps;  -- only on a NEW, empty database
  ```
  Why: `schema.sql` creates old versions of `skill_gap` / `roadmaps` (no `user_id`; `roadmaps` has
  required `week_number`/`task` columns the code never fills). `CREATE TABLE IF NOT EXISTS` then
  skips the correct definitions, so saving a skill gap / roadmap fails (MySQL 8 also rejects the
  `ADD COLUMN IF NOT EXISTS` migrations). After the drop, the API recreates both tables correctly.
  Your existing local database that already works with Streamlit needs nothing.

### Backend — Render or Railway
- **Render** → New *Web Service* from your repo, root = this folder.
  Build: `pip install -r requirements-api.txt` · Start: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`
- **Railway** → New service from repo; the included `Procfile` is picked up automatically.
- Set env vars: DB_*, `JWT_SECRET`, `CORS_ORIGINS=https://<your-frontend-domain>`.
- Uploaded PDFs go to `uploads/resumes`, which is **ephemeral** on Render/Railway free plans
  (parsed skills are stored in MySQL, so only the raw file is lost on redeploy). Attach a
  persistent disk/volume if you need to keep the files.
- Other options: Fly.io, a small VPS (`uvicorn` behind nginx), Docker anywhere.

### Frontend — Lovable, Vercel, Netlify or Cloudflare
The frontend reads the backend URL from `VITE_API_URL` **at build time**. The easiest way that
works on every host (including Lovable publish) is a committed `.env.production`:
```
VITE_API_URL=https://your-api.onrender.com
```
- **Lovable**: push the updated code to the repo Lovable is synced with → *Publish*.
  Add your `*.lovable.app` domain to `CORS_ORIGINS` (or `CORS_ORIGIN_REGEX=https://.*\.lovable\.app`).
- **Cloudflare Pages/Workers**: this template's build already targets Cloudflare (`npm run build`).
- **Vercel / Netlify**: it's a TanStack Start (SSR) app built with Nitro; set the build env var
  `NITRO_PRESET=vercel` (or `netlify`) and use `npm run build`. I verified `npm run build` locally
  but did not deploy to these hosts — check the host's TanStack Start guide if the preset differs.
