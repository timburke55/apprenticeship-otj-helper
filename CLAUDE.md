# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the development server (port 5000, debug mode)
uv run otj-helper

# Run tests (pytest is configured, no tests exist yet)
uv run pytest

# Run a single test file
uv run pytest tests/path/to/test_file.py

# Run a single test
uv run pytest tests/path/to/test_file.py::test_function_name
```

The database file is created automatically at `data/otj.db` on first run. Override with `OTJ_DB_PATH` env var.

## Architecture

Flask app using the application factory pattern (`src/otj_helper/app.py`). The factory configures SQLite via Flask-SQLAlchemy, runs lightweight schema migrations, seeds KSB reference data, and registers three blueprints.

### Blueprints and Routes

| Blueprint | Prefix | Responsibility |
|-----------|--------|----------------|
| `dashboard` | `/` | Aggregated stats: total OTJ hours, activity breakdowns, KSB coverage matrix |
| `activities` | `/activities` | Full CRUD for Activity + ResourceLink records |
| `ksbs` | `/ksbs` | Read-only KSB reference browser with linked activity summaries |

### Data Models (`models.py`)

Three models with a many-to-many join:

- **KSB**: Reference data for the ST0787 standard (24 records seeded from `ksb_data.py`). Codes are K1–K5 (Knowledge), S1–S11 (Skills), B1–B6 (Behaviours).
- **Activity**: Core log entry. Has `activity_type` (10 options: training_course, self_study, mentoring, shadowing, workshop, conference, project_work, research, writing, other) and a many-to-many relationship to KSB via `activity_ksbs`.
- **ResourceLink**: Child of Activity. Each link has a `workflow_stage` following the CORE framework (capture → organise → review → engage), each stage having a default `source_type`.

### Schema Migrations

`app.py:_migrate_db()` applies incremental DDL directly via `db.session.execute()` — not Alembic. Add new `ALTER TABLE` statements there for schema changes.

### KSB Seeding

`ksb_data.py` holds the hardcoded list of 24 KSB dicts. `app.py:_seed_ksbs()` inserts them on first run if the table is empty. Update `ksb_data.py` to change reference data; the seed only runs once unless the table is cleared.

### Templates

Jinja2 templates under `src/otj_helper/templates/`. Base layout in `base.html` uses Tailwind CSS via CDN. KSB categories have a consistent color theme: Knowledge=blue, Skills=green, Behaviours=amber.

The activity form (`templates/activities/form.html`) dynamically handles a variable number of resource link rows via JavaScript; the route handler in `routes/activities.py` reads parallel lists from `request.form.getlist(...)` to reconstruct them.

Dashboard and KSB routes use SQLAlchemy subqueries with `func.sum` / `func.count` aggregations — see `routes/dashboard.py` and `routes/ksbs.py` for the pattern.
