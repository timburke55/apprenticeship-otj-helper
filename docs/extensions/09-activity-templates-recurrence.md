# Extension 09: Activity Templates and Recurrence

## Overview

Allow users to create reusable activity templates (e.g. "Weekly mentor meeting") that pre-fill the form with a title, type, KSBs, duration, and tags. Optionally, templates can recur on a schedule, auto-generating draft activities. Introduces template CRUD, schedule configuration, and a periodic task to create recurring entries.

**Complexity drivers:** Template-to-activity mapping, cron-like scheduling, recurrence conflict detection, undo/draft states, and a template management UI.

---

## Prerequisites

No new external dependencies for templates. For automated recurrence, depends on Extension 05 (Background Task Queue) or a simple `before_request` check approach.

---

## Step-by-step Implementation

### 1. Create the ActivityTemplate model

**File:** `src/otj_helper/models.py`

```python
class ActivityTemplate(db.Model):
    """A reusable template for quickly logging common activities."""

    __tablename__ = "activity_template"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)           # Template display name
    title = db.Column(db.String(200), nullable=False)          # Pre-filled activity title
    description = db.Column(db.Text, default="")
    activity_type = db.Column(db.String(50), nullable=False, default="self_study")
    duration_hours = db.Column(db.Float, nullable=True)        # Default duration (optional)
    evidence_quality = db.Column(db.String(20), default="draft")
    tags_csv = db.Column(db.String(500), default="")           # Comma-separated tag names
    ksb_codes_csv = db.Column(db.String(500), default="")      # Comma-separated KSB codes

    # Recurrence fields
    is_recurring = db.Column(db.Boolean, default=False)
    recurrence_day = db.Column(db.Integer, nullable=True)      # 0=Mon, 6=Sun (ISO weekday)
    last_generated = db.Column(db.Date, nullable=True)         # Date of last auto-generated activity

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="templates")

    RECURRENCE_DAYS: ClassVar[list[tuple[int, str]]] = [
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
        (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday"),
    ]
```

### 2. Add migration

**File:** `src/otj_helper/app.py`

```python
(
    "CREATE TABLE IF NOT EXISTS activity_template ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "user_id INTEGER NOT NULL REFERENCES app_user(id), "
    "name VARCHAR(200) NOT NULL, "
    "title VARCHAR(200) NOT NULL, "
    "description TEXT DEFAULT '', "
    "activity_type VARCHAR(50) NOT NULL DEFAULT 'self_study', "
    "duration_hours REAL, "
    "evidence_quality VARCHAR(20) DEFAULT 'draft', "
    "tags_csv VARCHAR(500) DEFAULT '', "
    "ksb_codes_csv VARCHAR(500) DEFAULT '', "
    "is_recurring BOOLEAN DEFAULT 0, "
    "recurrence_day INTEGER, "
    "last_generated DATE, "
    "created_at DATETIME)"
),
```

### 3. Create template CRUD routes

**New file:** `src/otj_helper/routes/templates.py`

```python
bp = Blueprint("templates", __name__, url_prefix="/templates")
```

| Method | Path | Description |
|--------|------|-------------|
| GET | `/templates/` | List user's templates |
| GET | `/templates/new` | Template creation form |
| POST | `/templates/new` | Save new template |
| GET | `/templates/<id>/edit` | Edit form |
| POST | `/templates/<id>/edit` | Update template |
| POST | `/templates/<id>/delete` | Delete template |
| GET | `/templates/<id>/use` | Redirect to activity form pre-filled from template |

The "use" route is the key UX feature. It redirects to `/activities/new` with query parameters that pre-fill the form:

```python
@bp.route("/<int:template_id>/use")
@login_required
def use_template(template_id):
    """Redirect to the activity form pre-filled from a template."""
    tmpl = ActivityTemplate.query.filter_by(
        id=template_id, user_id=g.user.id
    ).first_or_404()
    return redirect(url_for(
        "activities.create",
        tmpl_title=tmpl.title,
        tmpl_type=tmpl.activity_type,
        tmpl_duration=tmpl.duration_hours or "",
        tmpl_description=tmpl.description or "",
        tmpl_tags=tmpl.tags_csv or "",
        tmpl_ksbs=tmpl.ksb_codes_csv or "",
        tmpl_quality=tmpl.evidence_quality or "draft",
    ))
```

### 4. Update the activity form to accept template pre-fill params

**File:** `src/otj_helper/routes/activities.py`

In the `create()` GET handler, read query params and construct a pre-filled activity:

```python
@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        return _save_activity(Activity())

    # Check for template pre-fill
    prefill = None
    if request.args.get("tmpl_title"):
        prefill = Activity()
        prefill.title = request.args.get("tmpl_title", "")
        prefill.activity_type = request.args.get("tmpl_type", "self_study")
        prefill.duration_hours = float(request.args.get("tmpl_duration") or 0) or None
        prefill.description = request.args.get("tmpl_description", "")
        prefill.evidence_quality = request.args.get("tmpl_quality", "draft")
        # Pre-select KSBs and tags handled in template via query params

    return render_template("activities/form.html", **_form_context(prefill))
```

### 5. Update the activity form template for pre-fill

**File:** `src/otj_helper/templates/activities/form.html`

The form already reads from `activity.*` for edit mode, so the pre-fill data flows through the same mechanism. For KSBs from template, parse `tmpl_ksbs` query param in the template:

```html
{% set tmpl_ksbs = request.args.get('tmpl_ksbs', '')|split(',') if not activity or not activity.id else [] %}
{% set selected_codes = (activity.ksbs|map(attribute='code')|list if activity and activity.ksbs else []) + tmpl_ksbs %}
```

### 6. Add a "Save as Template" button to the activity form

**File:** `src/otj_helper/templates/activities/detail.html`

Add a link on the activity detail page:

```html
<a href="{{ url_for('templates.create_from_activity', activity_id=activity.id) }}"
    class="rounded-md bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50">
    Save as Template
</a>
```

Add a route in `routes/templates.py`:

```python
@bp.route("/from-activity/<int:activity_id>")
@login_required
def create_from_activity(activity_id):
    """Pre-fill template form from an existing activity."""
    activity = Activity.query.filter_by(
        id=activity_id, user_id=g.user.id
    ).first_or_404()
    return render_template("templates/form.html", template=None, from_activity=activity)
```

### 7. Implement recurring activity generation

**New file:** `src/otj_helper/tasks/recurrence.py`

A function that checks all recurring templates and creates activities for the current week if not already generated:

```python
def generate_recurring_activities():
    """Check all recurring templates and create activities for this week."""
    from datetime import date, timedelta
    from otj_helper.app import create_app
    from otj_helper.models import Activity, ActivityTemplate, KSB, Tag, db

    app = create_app()
    with app.app_context():
        today = date.today()
        templates = ActivityTemplate.query.filter_by(is_recurring=True).all()

        for tmpl in templates:
            # Find the most recent occurrence of this weekday
            days_since = (today.weekday() - tmpl.recurrence_day) % 7
            target_date = today - timedelta(days=days_since)

            # Skip if already generated for this week
            if tmpl.last_generated and tmpl.last_generated >= target_date:
                continue

            # Only generate if today is the target day
            if today.weekday() != tmpl.recurrence_day:
                continue

            activity = Activity(
                user_id=tmpl.user_id,
                title=tmpl.title,
                description=tmpl.description,
                activity_date=target_date,
                duration_hours=tmpl.duration_hours or 1.0,
                activity_type=tmpl.activity_type,
                evidence_quality="draft",
            )

            # Link KSBs
            if tmpl.ksb_codes_csv:
                codes = [c.strip() for c in tmpl.ksb_codes_csv.split(",") if c.strip()]
                activity.ksbs = KSB.query.filter(KSB.code.in_(codes)).all()

            # Link tags
            if tmpl.tags_csv:
                for name in tmpl.tags_csv.split(","):
                    name = name.strip().lower()
                    if not name:
                        continue
                    tag = Tag.query.filter_by(name=name, user_id=tmpl.user_id).first()
                    if not tag:
                        tag = Tag(name=name, user_id=tmpl.user_id)
                        db.session.add(tag)
                    activity.tags.append(tag)

            db.session.add(activity)
            tmpl.last_generated = target_date

        db.session.commit()
```

For the PoC, call this function from a `before_request` hook (checks once per day per user) or from the background task queue if Extension 05 is implemented.

### 8. Create templates

**New file:** `src/otj_helper/templates/templates/list.html`

Shows user's templates as cards with: name, pre-filled type, duration, KSBs, recurrence badge. "Use", "Edit", "Delete" actions.

**New file:** `src/otj_helper/templates/templates/form.html`

Form with: template name, pre-fill title, type, duration, description, KSB checkboxes, tags input, evidence quality, recurrence toggle + weekday selector.

### 9. Register blueprint and add navigation

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.templates import bp as templates_bp
app.register_blueprint(templates_bp)
```

**File:** `src/otj_helper/templates/base.html`

Add "Templates" link to nav bar.

**File:** `src/otj_helper/templates/activities/form.html`

Add a "From template" dropdown at the top of the form if user has templates.

### 10. Write tests

**New file:** `tests/test_templates.py`

- Template list accessible
- Create template saves to DB
- "Use template" pre-fills activity form (check query params in redirect)
- Recurring generation creates activity on correct day
- Recurring generation skips if already generated this week

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `src/otj_helper/models.py` | Edit | Add `ActivityTemplate` model |
| `src/otj_helper/app.py` | Edit | Migration, register blueprint |
| `src/otj_helper/routes/templates.py` | Create | Template CRUD + use + from-activity |
| `src/otj_helper/routes/activities.py` | Edit | Accept template pre-fill query params |
| `src/otj_helper/tasks/recurrence.py` | Create | Recurring activity generation |
| `src/otj_helper/templates/templates/list.html` | Create | Template list UI |
| `src/otj_helper/templates/templates/form.html` | Create | Template form UI |
| `src/otj_helper/templates/activities/form.html` | Edit | Template pre-fill support |
| `src/otj_helper/templates/activities/detail.html` | Edit | "Save as Template" button |
| `src/otj_helper/templates/base.html` | Edit | "Templates" nav link |
| `tests/test_templates.py` | Create | Template CRUD and recurrence tests |

---

## Testing Checklist

- [ ] `uv run pytest tests/test_templates.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: create template, verify it appears in list
- [ ] Manual: click "Use", verify activity form is pre-filled
- [ ] Manual: create activity, click "Save as Template", verify template created
- [ ] Manual: enable recurrence, verify activity auto-created on correct day
