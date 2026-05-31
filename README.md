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

## CSV format

The dashboard expects columns such as:

- `Last Updated (IST)`
- `Overall Status`
- `SF Final Problem`, `SF Final Detail`, `SF Final SubDetail`
- `SF Final Category`, `SF Final Action`, `CTA Status`, `SF Error Type`
