# Apprenticeship OTJ Helper

A Flask web app for tracking Off-the-Job (OTJ) training activities for the **Systems Thinking Practitioner Level 7 (ST0787)** apprenticeship.

It lets you log training activities, track hours, and map your work to the Knowledge, Skills, and Behaviours (KSBs) required by the standard — so you always know where you stand against each competency.

## Features

- **Dashboard** — total hours logged, breakdown by activity type, recent activities, and KSB coverage at a glance
- **Activity log** — create, edit, and delete training entries with date, duration, type, and free-text notes
- **KSB mapping** — tag each activity against one or more KSBs (K1–K5, S1–S6, B1–B4) from the ST0787 standard
- **Resource links** — attach URLs to activities and organise them using the **CORE workflow** (Capture → Organise → Review → Engage), with support for Google Keep, Google Tasks, Google Docs, Google Drive, GitHub, and more
- **KSB reference** — browse the full ST0787 KSB catalogue, with hours and activity counts per competency

## Tech stack

- **Python 3.11+** / **Flask 3.0+**
- **Flask-SQLAlchemy** with **SQLite**
- **Tailwind CSS** (CDN)
- **UV** for dependency management

## Getting started

```bash
# Install dependencies
uv sync

# Run the app
uv run otj-helper
```

Then open [http://localhost:5000](http://localhost:5000).

The SQLite database is created automatically at `data/otj.db` on first run, and KSB reference data is seeded automatically.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `OTJ_DB_PATH` | `data/otj.db` | Path to the SQLite database file |
| `SECRET_KEY` | `dev-key-change-in-production` | Flask session secret key |

## Activity types

Training course, self study, mentoring, shadowing, workshop, conference, project work, research, writing, and other.

## KSB categories

The ST0787 standard defines 15 competencies across three categories:

- **Knowledge** (K1–K5) — shown in blue
- **Skills** (S1–S6) — shown in green
- **Behaviours** (B1–B4) — shown in yellow
