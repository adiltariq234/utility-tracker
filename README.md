# Residential Utility Usage Tracker

A full-stack web app for tracking residential utility usage: meter readings,
cumulative units, billing, and paid/unpaid dues — with chain recalculation on
every edit or delete, plus Excel/CSV reporting.

## Features

- **Properties** — create homes, bulk-generate property IDs, rename IDs
  (usage history moves along automatically)
- **Meter readings & manual units** — reading-chain validation (a new reading
  must exceed the previous one), opening balances, cumulative totals
- **Billing & payments** — paid/unpaid tracking, pay-all per property
- **Chain recalculation** — editing or deleting any entry recomputes all
  later entries and property totals
- **Dashboard** — total homes, active homes, units, billed, paid, pending
- **Exports** — Excel workbook (homes summary, full history, unpaid dues)
  and CSV, with Excel-friendly formatting
- **Frontend** — Tailwind / GSAP / Three.js single-page UI in `public/`

## Tech stack

| Layer    | Technology                              |
|----------|-----------------------------------------|
| Backend  | FastAPI, SQLAlchemy, Pydantic v2        |
| Database | SQLite (local) / PostgreSQL (production)|
| Frontend | Tailwind CSS, GSAP, Three.js            |
| Export   | openpyxl, csv                           |

## Run locally

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
uv run uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. Locally the app uses a SQLite file
(`utility_tracker.db`).

## Configuration

| Variable       | Required | Description                                              |
|----------------|----------|----------------------------------------------------------|
| `DATABASE_URL` | On Vercel| PostgreSQL connection string, e.g. Neon (with `sslmode=require`). Locally optional — SQLite is used when unset. |

See `.env.example`. Never commit a real `.env` file.

## Deploy on Vercel

Vercel's filesystem is ephemeral, so SQLite cannot be used in production —
PostgreSQL (free: Neon) is required.

1. Create a free project at [Neon](https://neon.tech) and copy the
   connection string.
2. Import this GitHub repo at [Vercel](https://vercel.com) → Add New → Project.
3. Before deploying: Settings → Environment Variables → add `DATABASE_URL`
   with the connection string.
4. Deploy. Tables are created automatically on the first request.

The `api/index.py` entrypoint and `vercel.json` rewrite route all traffic
through the FastAPI app, which also serves the `public/` frontend.

## API overview

- `POST /properties/`, `GET /properties/`, `PUT /properties/{id}`,
  `PUT /properties/{id}/rename`, `POST /properties/bulk-generate/`
- `POST /usage/add/`, `PUT /usage/{id}`, `DELETE /usage/{id}`,
  `DELETE /usage/undo-last/{property_id}`, `PATCH /usage/{id}/payment`
- `GET /usage/unpaid/`, `GET /logs/`, `GET /dashboard/summary`
- `GET /export/excel`, `GET /export/csv`

Interactive docs (when running): `/docs`.

## Project structure

```text
main.py            FastAPI app, routes, chain recalculation, exports
models.py          SQLAlchemy models (Property, UsageLog)
schemas.py         Pydantic request/response schemas
database.py        Engine/session (SQLite locally, Postgres via DATABASE_URL)
public/index.html  Frontend (Tailwind / GSAP / Three.js)
api/index.py       Vercel serverless entrypoint
vercel.json        Vercel rewrites
requirements.txt   Python dependencies
.env.example       Environment variable template
```
