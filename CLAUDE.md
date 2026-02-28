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
| `landing` | `/` | Public landing page and apprenticeship standard selection |
| `auth` | `/auth` | Google OAuth login/logout and dev auto-login |
| `dashboard` | `/dashboard` | Aggregated stats: total OTJ hours, activity breakdowns, KSB coverage matrix, readiness score |
| `activities` | `/activities` | Full CRUD for Activity + ResourceLink + Attachment records; CSV export |
| `ksbs` | `/ksbs` | Read-only KSB reference browser with linked activity summaries |
| `tags` | `/tags` | Tag management: list, rename, delete |
| `templates` | `/templates` | Activity template CRUD; recurring template generation |
| `recommendations` | `/recommendations` | Gap analysis dashboard (readiness score, KSB gaps, priority actions) |
| `uploads` | `/uploads` | File upload, serve, thumbnail, and delete for Attachment records |
| `events` | `/events` | Server-Sent Events stream for real-time dashboard updates |

### Data Models (`models.py`)

- **User** (`app_user`): Google-authenticated user. Stores `selected_spec`, hour targets (`otj_target_hours`, `seminar_target_hours`, `weekly_target_hours`).
- **KSB**: Reference data seeded from `ksb_data.py`. Supports two specs: ST0787 (24 KSBs: K1–K5, S1–S11, B1–B6) and ST0763 (64 KSBs with `A`-prefix codes). `natural_code` property strips the spec prefix for display.
- **Activity**: Core log entry. Fields: `title`, `activity_date`, `duration_hours`, `activity_type` (10 options), `description`, `notes`, `evidence_quality` (draft/good/review_ready). Many-to-many with KSB via `activity_ksbs` and with Tag via `activity_tags`. One-to-many with ResourceLink and Attachment.
- **ResourceLink**: Child of Activity. Has `workflow_stage` (capture/organise/review/engage) and `source_type`. Stage-specific source type defaults are in `routes/activities.py:_STAGE_SOURCE_TYPES`.
- **Tag**: User-scoped label. Unique per (name, user_id). Many-to-many with Activity via `activity_tags`.
- **ActivityTemplate**: Reusable activity defaults. Fields: `name` (unique per user), `title`, `description`, `activity_type`, `duration_hours`, `evidence_quality`, `tags_csv`, `ksb_codes_csv`. Supports recurrence: `is_recurring` (bool), `recurrence_day` (0=Monday–6=Sunday), `last_generated` (date).
- **Attachment**: File upload record. Stores `filename` (original), `stored_name` (UUID-based on disk), `content_type`, `file_size`, `has_thumbnail`.

### Schema Migrations

`app.py:_migrate_db()` applies incremental DDL directly via `db.session.execute()` — not Alembic. Add new `ALTER TABLE` statements there for schema changes.

### KSB Seeding

`ksb_data.py` holds the hardcoded KSB dicts for all supported specs. `app.py:_seed_ksbs()` inserts them on first run if the table is empty, keyed by (spec_code, code) for safe re-seeding. Update `ksb_data.py` to change reference data; the seed only runs once unless the table is cleared.

### Jinja2 Templates

Templates are under `src/otj_helper/templates/`. Base layout in `base.html` uses Tailwind CSS via CDN and includes dark-mode toggle, mobile nav, and flash messages. KSB categories have a consistent colour theme: Knowledge=blue, Skills=green, Behaviours=amber.

The activity form (`templates/activities/form.html`) dynamically handles a variable number of resource link rows via JavaScript; the route handler in `routes/activities.py` reads parallel lists from `request.form.getlist(...)` to reconstruct them.

Dashboard and KSB routes use SQLAlchemy subqueries with `func.sum` / `func.count` aggregations — see `routes/dashboard.py` and `routes/ksbs.py` for the pattern.

### Recommendations Engine

`recommendations.py:analyse_gaps()` performs deterministic gap analysis (no LLM): KSB coverage, evidence quality score, unused activity types, missing CORE workflow stages, stale KSBs (>30 days), and draft-only evidence. Readiness score = coverage_pct × 0.6 + quality_pct × 0.4.

### Real-time Updates

`routes/events.py` provides an SSE stream at `/events/stream`. The dashboard subscribes and reloads after `activity_saved` or `activity_deleted` events. Background task in `tasks/recurrence.py` generates recurring template activities once per day per user.

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
- **DB dialect checks**: Use `db.engine.dialect.name == "sqlite"` (or `"postgresql"`) rather than substring-matching the URL string. The URL can contain the word "sqlite" in a path component or username and produce false positives.

## User Documentation

The user-facing guide lives at **`docs/user-guide.md`**. It is the authoritative reference for how the app works from an end-user perspective. Keep it in sync with the code.

### When to update `docs/user-guide.md`

Update the user guide whenever you:

- **Add a new page or route** — add a section (or sub-section) describing what the page does, how to reach it, and what actions are available.
- **Add a new field to a form** — add the field to the relevant table in the guide, with a plain-English description of what it does and any constraints (e.g. allowed values, required vs optional).
- **Change how a feature works** — update the description to match the new behaviour. Remove steps or options that no longer exist.
- **Remove a feature** — remove the corresponding section or sub-section entirely. Do not leave stale instructions.
- **Add a new activity type, evidence quality level, or KSB category** — update the relevant table in the guide.
- **Change a URL or navigation path** — update any references in the guide.
- **Add a new apprenticeship standard** — add a row to the standards table in section 2.

### What the user guide must NOT contain

- Internal implementation details (models, migrations, blueprint names, SQL queries) — those belong in this file (CLAUDE.md).
- Developer setup instructions — those belong in README.md.
- Anything that would tell an apprentice how to use AI to generate their evidence — the guide explicitly prohibits this and the prohibition must not be weakened.

### Style conventions for the guide

- Write in plain English for a non-technical audience.
- Use tables for structured comparisons (fields, types, options).
- Use numbered lists for sequential steps.
- Use `**bold**` for UI element names (button labels, field names, page titles).
- Do not include screenshots (they go stale quickly); describe the layout in words instead.
- Keep section numbering sequential — if you add a section, renumber the table of contents and all section headings.
