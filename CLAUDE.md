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

## Generative AI Guardrails (JGA Policy Compliance)

This app tracks off-the-job training evidence for apprenticeships delivered by JGA Group. JGA's Generative AI Strategy (QA-18) and the broader UK apprenticeship assessment framework place strict limits on how AI may be used. **Any feature that involves LLM or generative AI integration must comply with the rules below.**

Reference: [JGA AI Strategy (QA-18)](https://www.jga-group.com/wp-content/uploads/QA-18-JGA_AI_Strategy_v2_0824.pdf) · [JGA AI guidance for apprentices](https://www.jga-group.com/apprentice-zone/support/artificial-intelligence/)

### What AI must NEVER do in this app

- **Write, draft, or suggest evidence text** — portfolio evidence, reflective accounts, descriptions, or any narrative the apprentice would submit as their own work. This includes "suggest and edit" flows where the LLM produces a first draft.
- **Write or draft assessment answers** — professional discussion prep, project proposals, presentations, or any content assessed by an End-Point Assessment Organisation.
- **Auto-complete or ghost-write** activity descriptions, notes, or reflections — even as optional suggestions the user can accept/edit.
- **Generate or fabricate activity data** — titles, dates, durations, or resource links that did not actually occur.
- **Summarise or paraphrase the apprentice's own writing** into a "better" version — rewriting undermines authentic voice and is indistinguishable from generation.

### What AI may do

- **Identify which KSBs an activity might address** — suggest KSB codes with brief justifications, for the apprentice to accept or dismiss (see Extension 01).
- **Analyse coverage gaps** — highlight under-evidenced KSBs, stale evidence, or missing activity types (see Extension 11).
- **Classify or tag** — suggest activity types or tags based on a title, without generating prose.
- **Search and retrieve** — help the apprentice find their own existing activities or resources.

### Design rules for any AI feature

1. **Human-in-the-loop**: Every AI suggestion must be a candidate the apprentice explicitly accepts or dismisses. Nothing is auto-applied.
2. **No generated prose in the portfolio**: If an LLM produces natural-language output, it must be clearly auxiliary (e.g. a one-sentence justification for a KSB match) and must never be saved as part of the apprentice's evidence record.
3. **Transparency**: Where AI is used, the UI must make this obvious (e.g. a distinct "AI Suggestions" panel). AI output must not be silently blended into the apprentice's own content.
4. **Bring Your Own Key**: The app must never ship with or require a centrally-funded API key. Users configure their own provider and key via settings.

### When proposing new features

Before designing or implementing any feature that involves an LLM, generative AI, or automated text production, check it against the rules above. If a proposed feature would produce text that an apprentice could submit as their own evidence, **do not build it** — suggest an alternative that keeps the apprentice as the author. When in doubt, the test is: *"Could this output end up in the apprentice's portfolio or EPA submission as if they wrote it?"* If yes, it violates the policy.

## Code Review Standards (CodeRabbit)

PRs are reviewed automatically by CodeRabbit. Follow these conventions to avoid common flags:

### Security
- **CSRF**: All POST forms must include `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`. `CSRFProtect` is already wired up in `app.py` via Flask-WTF.
- **Server-side validation**: Validate all user-supplied numbers for `< 0` *and* `math.isfinite()` — HTML `min` attributes are client-side only.
- **JS injection**: Never interpolate server values into JS string literals directly. Use Jinja's `{{ value|tojson }}` filter so values are properly JSON-encoded and escaped.
- **CDN scripts**: Pin to a specific version (e.g. `chart.js@4.4.7`, not `@4`) and include a matching `integrity="sha384-..."` SRI hash plus `crossorigin="anonymous"`. Obtain the hash from the CDN's own integrity tool or by computing `sha384` of the file.

### Templates
- **URL generation**: Use `url_for('blueprint.view')` instead of hardcoded paths. Applies to form `action` attributes and `href` links for routes owned by this app. **When editing any template file, convert every hardcoded path in that file** — not just the lines you're adding. Run `grep -n 'href="/' <file>` before committing and replace any matches that aren't external URLs. Common endpoint names:
  - `url_for('landing.index')` → `/`
  - `url_for('dashboard.index')` → `/dashboard`
  - `url_for('activities.list_activities')` → `/activities` (accepts `tag=`, `ksb=`, `type=` kwargs for query params)
  - `url_for('activities.create')` → `/activities/new`
  - `url_for('activities.detail', activity_id=x)` → `/activities/<id>`
  - `url_for('activities.edit', activity_id=x)` → `/activities/<id>/edit`
  - `url_for('ksbs.list_ksbs')` → `/ksbs`
  - `url_for('ksbs.detail', code=x)` → `/ksbs/<code>`
  - `url_for('tags.list_tags')` → `/tags`
  - `url_for('auth.login')` → `/auth/login`
  - `url_for('auth.logout')` → `/auth/logout`
  - `url_for('auth.google_login')` → `/auth/google`
- **Null vs falsy checks**: Use `{% if value is not none %}` rather than `{% if value %}` when `0` is a valid state. Bare truthiness checks hide zero values and can cause division-by-zero in expressions that follow.

### Python
- **Docstrings**: Add a docstring to every new function/method. The configured coverage threshold is 80%; falling below it fails the pre-merge check.
- **Decimal precision**: Use 1 decimal place (`round(x, 1)`, `"%.1f"`) consistently — this matches the existing UI convention throughout the app.
