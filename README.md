# Gnani Dashboard

Interactive analytics dashboard for CSV case data. Upload one or more CSV files and explore trends, status breakdowns, and SF hierarchy metrics.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python dashboard.py
```

Open http://127.0.0.1:8050

## Deploy publicly (Render — free tier)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) and sign in with GitHub.
3. Click **New → Web Service** and select `Gnani-Dashboard`.
4. Render will detect Python automatically. Use:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn dashboard:server --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
5. Click **Create Web Service**. Render assigns a public URL like `https://gnani-dashboard.onrender.com`.

Alternatively, import the repo using the included `render.yaml` blueprint.

## Deploy with GitHub Actions

GitHub cannot run a Dash server itself. Actions can **test your code** and **trigger a deploy** to Render on every push to `main`.

### One-time setup

1. **Create the Render service** (steps above) so the app exists at a public URL.
2. In Render, open your service → **Settings** → **Deploy Hook** → copy the hook URL.
3. On GitHub, open **Gnani-Dashboard** → **Settings** → **Secrets and variables** → **Actions**.
4. Click **New repository secret**:
   - Name: `RENDER_DEPLOY_HOOK`
   - Value: paste the Render deploy hook URL
5. Push to `main`. Actions runs automatically.

### Workflows in this repo

| Workflow | What it does |
|----------|----------------|
| `ci.yml` | Installs deps and verifies `dashboard.py` imports (on push/PR) |
| `deploy-render.yml` | Runs tests, then POSTs to Render deploy hook |

View runs: **GitHub repo → Actions** tab.

### Push workflow files with your PAT

```bash
cd /Users/dylan.dias/PycharmProjects/gnanni
git add .github/workflows/
git commit -m "Add GitHub Actions for CI and Render deploy"
git push origin main
```

Use GitHub username + PAT (`ghp_...`) when prompted for password.

## CSV format

The dashboard expects columns such as:

- `Last Updated (IST)`
- `Overall Status`
- `SF Final Problem`, `SF Final Detail`, `SF Final SubDetail`
- `SF Final Category`, `SF Final Action`, `CTA Status`, `SF Error Type`
