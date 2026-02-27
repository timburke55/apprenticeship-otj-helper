# Extension 09: Activity Templates and Recurrence

Reusable activity templates that pre-fill the activity form and optionally generate recurring draft activities on a fixed weekday.

---

## What was built

| File | Change |
|------|--------|
| `src/otj_helper/models.py` | Added `ActivityTemplate` model |
| `src/otj_helper/app.py` | Migration, blueprint registration, `maybe_generate_recurring` before-request hook |
| `src/otj_helper/routes/templates.py` | Template CRUD + `/use` + `/from-activity` routes |
| `src/otj_helper/routes/activities.py` | Template pre-fill via query params; `user_templates` in form context |
| `src/otj_helper/tasks/__init__.py` | New package |
| `src/otj_helper/tasks/recurrence.py` | `generate_recurring_activities()` — idempotent weekday-based generation |
| `src/otj_helper/templates/templates/list.html` | Template card list with Use / Edit / Delete actions |
| `src/otj_helper/templates/templates/form.html` | Template create/edit form with recurrence toggle |
| `src/otj_helper/templates/activities/form.html` | "Start from a template" dropdown; KSB + tag pre-fill from query params |
| `src/otj_helper/templates/activities/detail.html` | "Save as Template" button; all hardcoded paths converted to `url_for` |
| `src/otj_helper/templates/base.html` | "Templates" nav link (desktop + mobile) |
| `tests/test_templates.py` | 15 tests covering CRUD, use, pre-fill, and recurrence logic |

---

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates/` | List user's templates |
| GET | `/templates/new` | Template creation form |
| POST | `/templates/new` | Save new template |
| GET | `/templates/<id>/edit` | Edit form |
| POST | `/templates/<id>/edit` | Update template |
| POST | `/templates/<id>/delete` | Delete template |
| GET | `/templates/<id>/use` | Redirect to `/activities/new` pre-filled from template |
| GET | `/templates/from-activity/<id>` | Pre-fill template form from an existing activity |

---

## Model: `ActivityTemplate`

Stored in table `activity_template`.

| Column | Type | Notes |
|--------|------|-------|
| `name` | `VARCHAR(200)` | Display label shown in lists and dropdowns |
| `title` | `VARCHAR(200)` | Pre-fills the activity title field |
| `activity_type` | `VARCHAR(50)` | Defaults to `self_study` |
| `duration_hours` | `REAL` | Optional; pre-fills duration |
| `description` | `TEXT` | Optional pre-fill text |
| `evidence_quality` | `VARCHAR(20)` | Defaults to `draft` |
| `tags_csv` | `VARCHAR(500)` | Comma-separated tag names |
| `ksb_codes_csv` | `VARCHAR(500)` | Comma-separated KSB codes to pre-check |
| `is_recurring` | `BOOLEAN` | Enables weekly draft generation |
| `recurrence_day` | `INTEGER` | `0`=Monday … `6`=Sunday |
| `last_generated` | `DATE` | Guards against duplicate generation |

---

## Recurrence

`generate_recurring_activities()` in `tasks/recurrence.py` is called by the `maybe_generate_recurring` before-request hook at most once per user per day (tracked in the session). On each call it:

1. Queries all `is_recurring=True` templates.
2. Skips if today's weekday ≠ `recurrence_day`.
3. Skips if `last_generated >= target_date` (already done this week).
4. Creates a `draft` `Activity`, links KSBs and tags, updates `last_generated`.

The function is idempotent and safe to call multiple times.
