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
| `scheduled-report.yml` | Daily inbox → PDF → email (cron) |

View runs: **GitHub repo → Actions** tab.

## Scheduled automation (Azure Graph only)

`scheduled_job.py` runs on a **cron schedule** and uses **only Microsoft Graph** (no SendGrid):

1. Checks the inbox for mail **received today** (timezone `MAILBOX_TIMEZONE`, default `Asia/Kolkata`) from `MAIL_SENDER_FILTER` with an Excel/CSV attachment  
2. **If found:** loads data, generates PDF, emails `REPORT_RECIPIENTS` via Graph `Mail.Send`  
3. **If not found:** emails recipients **“No data found”** for that day (no PDF)  

### Azure app permissions (IT)

Application permissions (admin consent required):

| Permission | Purpose |
|------------|---------|
| `Mail.Read` | Read inbox and download attachments |
| `Mail.Send` | Send report and no-data notifications |

### Required env vars (Render cron or GitHub secrets)

| Variable | Example |
|----------|---------|
| `INBOX_PROVIDER` | `graph` |
| `EMAIL_PROVIDER` | `graph` |
| `AZURE_TENANT_ID` | tenant ID |
| `AZURE_CLIENT_ID` | app client ID |
| `AZURE_CLIENT_SECRET` | app secret |
| `MAILBOX_USER` | `you@payufin.com` (inbox + send-as) |
| `MAIL_SENDER_FILTER` | `reports@payufin.com` |
| `REPORT_RECIPIENTS` | `a@payufin.com,b@payufin.com` |
| `MAILBOX_TIMEZONE` | `Asia/Kolkata` |
| `INBOX_TODAY_ONLY` | `true` (only today’s mail) |

### Cron time

Default in `render.yaml` and GitHub Actions: **`30 6 * * *` UTC** ≈ **12:00 IST**.

To run at another time, change the cron expression:

| Local time (IST) | UTC cron (`render.yaml` / GitHub) |
|------------------|-----------------------------------|
| 09:00 IST | `30 3 * * *` |
| 12:00 IST | `30 6 * * *` |
| 18:00 IST | `30 12 * * *` |

Cron uses UTC. Formula: **UTC hour = IST hour − 5:30** (e.g. 9:00 IST → 03:30 UTC → `30 3 * * *`).

### Run manually

```bash
export INBOX_PROVIDER=graph EMAIL_PROVIDER=graph
export AZURE_TENANT_ID=... AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=...
export MAILBOX_USER=you@payufin.com MAIL_SENDER_FILTER=sender@payufin.com
export REPORT_RECIPIENTS=you@payufin.com

# Dry run (no email)
SCHEDULE_DRY_RUN=true python scheduled_job.py

# Full run
python scheduled_job.py
```

### Schedule options

| Method | Config |
|--------|--------|
| **Render Cron** | `gnani-scheduled-report` in `render.yaml` |
| **GitHub Actions** | `.github/workflows/scheduled-report.yml` |
| **Local cron** | `30 6 * * * cd /path/to/gnanni && .venv/bin/python scheduled_job.py` |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `INBOX_ONLY_UNREAD` | `true` | Only unread messages |
| `REPORT_TIME_GROUPING` | `daily` | PDF chart grouping |
| `REPORT_STATUS_FILTER` | `ALL` | Status filter in PDF |
| `MARK_PROCESSED` | `true` | Mark message read after processing |

Supported attachments: `.xlsx`, `.xls`, `.csv`

## CSV / Excel format

The dashboard expects columns such as:

- `Last Updated (IST)`
- `Overall Status`
- `SF Final Problem`, `SF Final Detail`, `SF Final SubDetail`
- `SF Final Category`, `SF Final Action`, `CTA Status`, `SF Error Type`
