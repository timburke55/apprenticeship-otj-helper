# Extension 07: Mentor/Assessor Review Workflow

## Overview

Add a second user role (mentor/assessor) who can view their learners' activities, leave comments, approve/reject evidence quality, and sign off on KSB coverage. Introduces role-based access control (RBAC), a review state machine, a commenting system, and a multi-tenancy mentor-learner relationship.

**Complexity drivers:** RBAC with two distinct role types, mentor-learner pairing, review state machine (draft -> submitted -> approved/needs_revision), comment threads, notification triggers, and separate mentor vs learner UIs.

---

## Prerequisites

No new external dependencies. Uses existing Flask + SQLAlchemy stack.

---

## Step-by-step Implementation

### 1. Add role and pairing models

**File:** `src/otj_helper/models.py`

Add a `role` column to `User`:

```python
role = db.Column(db.String(20), nullable=False, default="learner")  # "learner" or "mentor"
```

Add a mentor-learner pairing table:

```python
mentor_learners = db.Table(
    "mentor_learners",
    db.Column("mentor_id", db.Integer, db.ForeignKey("app_user.id"), primary_key=True),
    db.Column("learner_id", db.Integer, db.ForeignKey("app_user.id"), primary_key=True),
)
```

Add a relationship to `User`:

```python
# On User class:
mentors = db.relationship(
    "User", secondary=mentor_learners,
    primaryjoin=(id == mentor_learners.c.learner_id),
    secondaryjoin=(id == mentor_learners.c.mentor_id),
    backref="learners",
)
```

### 2. Add review status to Activity

**File:** `src/otj_helper/models.py`

Add a review workflow column:

```python
review_status = db.Column(db.String(20), nullable=False, default="draft")
# Valid values: "draft", "submitted", "approved", "needs_revision"
reviewed_by = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=True)
reviewed_at = db.Column(db.DateTime, nullable=True)
```

Add class var:
```python
REVIEW_STATUSES: ClassVar[list[tuple[str, str]]] = [
    ("draft", "Draft"),
    ("submitted", "Submitted for Review"),
    ("approved", "Approved"),
    ("needs_revision", "Needs Revision"),
]
```

### 3. Add the Comment model

**File:** `src/otj_helper/models.py`

```python
class ReviewComment(db.Model):
    """A comment on an activity from a mentor or learner."""

    __tablename__ = "review_comment"

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    activity = db.relationship("Activity", backref="comments")
    user = db.relationship("User")
```

### 4. Add migrations

**File:** `src/otj_helper/app.py`

```python
"ALTER TABLE app_user ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'learner'",
(
    "CREATE TABLE IF NOT EXISTS mentor_learners ("
    "mentor_id INTEGER NOT NULL REFERENCES app_user(id), "
    "learner_id INTEGER NOT NULL REFERENCES app_user(id), "
    "PRIMARY KEY (mentor_id, learner_id))"
),
"ALTER TABLE activity ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'draft'",
"ALTER TABLE activity ADD COLUMN reviewed_by INTEGER REFERENCES app_user(id)",
"ALTER TABLE activity ADD COLUMN reviewed_at DATETIME",
(
    "CREATE TABLE IF NOT EXISTS review_comment ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "activity_id INTEGER NOT NULL REFERENCES activity(id), "
    "user_id INTEGER NOT NULL REFERENCES app_user(id), "
    "body TEXT NOT NULL, "
    "created_at DATETIME)"
),
```

### 5. Create a role-checking decorator

**New file:** `src/otj_helper/roles.py`

```python
"""Role-based access control decorators."""

from functools import wraps
from flask import abort, g


def mentor_required(f):
    """Restrict route to users with the 'mentor' role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user or g.user.role != "mentor":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def learner_required(f):
    """Restrict route to users with the 'learner' role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.user or g.user.role != "learner":
            abort(403)
        return f(*args, **kwargs)
    return decorated
```

### 6. Create mentor routes

**New file:** `src/otj_helper/routes/mentor.py`

```python
bp = Blueprint("mentor", __name__, url_prefix="/mentor")
```

Routes (all decorated with `@login_required` and `@mentor_required`):

| Method | Path | Description |
|--------|------|-------------|
| GET | `/mentor/` | Mentor dashboard: list of paired learners with progress summaries |
| GET | `/mentor/learner/<id>` | View a specific learner's activities and KSB coverage |
| GET | `/mentor/learner/<id>/activity/<aid>` | View activity detail with comment thread |
| POST | `/mentor/learner/<id>/activity/<aid>/review` | Change review status (approve/needs_revision) |
| POST | `/mentor/learner/<id>/activity/<aid>/comment` | Add a comment |

Mentor dashboard shows per-learner:
- Name, email
- Total hours, activity count
- KSBs covered count / total
- Number of activities pending review (status=submitted)

### 7. Add review submission to learner activity routes

**File:** `src/otj_helper/routes/activities.py`

Add a new route for learners to submit activities for review:

```python
@bp.route("/<int:activity_id>/submit-review", methods=["POST"])
@login_required
def submit_for_review(activity_id):
    """Change activity status to 'submitted' for mentor review."""
    activity = Activity.query.filter_by(
        id=activity_id, user_id=g.user.id
    ).first_or_404()
    if activity.review_status not in ("draft", "needs_revision"):
        flash("This activity cannot be submitted.", "error")
        return redirect(url_for("activities.detail", activity_id=activity_id))
    activity.review_status = "submitted"
    db.session.commit()
    flash("Activity submitted for review.", "success")
    return redirect(url_for("activities.detail", activity_id=activity_id))
```

### 8. Update the activity detail template

**File:** `src/otj_helper/templates/activities/detail.html`

Add:
- Review status badge (colour-coded: draft=gray, submitted=yellow, approved=green, needs_revision=red)
- "Submit for Review" button (visible when status is draft or needs_revision)
- Comment thread section at the bottom (list of comments with author, timestamp, body)
- Comment form (textarea + submit button) if user is a mentor viewing a learner's activity

### 9. Create mentor templates

**New file:** `src/otj_helper/templates/mentor/dashboard.html`

Shows learner cards with progress summaries and "View" links.

**New file:** `src/otj_helper/templates/mentor/learner_detail.html`

Activity list for that learner, filtered to show submitted activities first.

**New file:** `src/otj_helper/templates/mentor/activity_review.html`

Activity detail with review controls (Approve / Request Revision buttons) and comment thread.

### 10. Admin route for pairing mentors and learners

**New file:** `src/otj_helper/routes/admin.py`

A simple admin page (only accessible to mentors for now) to pair themselves with learners by email:

```python
@bp.route("/pair", methods=["POST"])
@login_required
@mentor_required
def pair_learner():
    """Pair the current mentor with a learner by email."""
    email = request.form.get("email", "").strip().lower()
    learner = User.query.filter_by(email=email, role="learner").first()
    if not learner:
        flash("No learner found with that email.", "error")
    elif learner in g.user.learners:
        flash("Already paired with this learner.", "info")
    else:
        g.user.learners.append(learner)
        db.session.commit()
        flash(f"Paired with {learner.name or learner.email}.", "success")
    return redirect(url_for("mentor.index"))
```

### 11. Register blueprints

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.mentor import bp as mentor_bp
app.register_blueprint(mentor_bp)
```

### 12. Update navigation

**File:** `src/otj_helper/templates/base.html`

Add conditional nav link: if `current_user.role == 'mentor'`, show "Mentor Dashboard" link.

### 13. Write tests

**New file:** `tests/test_mentor.py`

Create fixtures for mentor and learner users. Test:
- Mentor dashboard accessible for mentor role
- Mentor dashboard returns 403 for learner role
- Submit for review changes status
- Mentor can approve activity
- Mentor can add comment
- Comment appears on activity detail

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `src/otj_helper/models.py` | Edit | Add role, mentor_learners, review_status, ReviewComment |
| `src/otj_helper/app.py` | Edit | Migrations, register blueprints |
| `src/otj_helper/roles.py` | Create | RBAC decorators |
| `src/otj_helper/routes/mentor.py` | Create | Mentor dashboard and review routes |
| `src/otj_helper/routes/activities.py` | Edit | Add submit-for-review route |
| `src/otj_helper/routes/admin.py` | Create | Mentor-learner pairing |
| `src/otj_helper/templates/activities/detail.html` | Edit | Review badge, submit button, comments |
| `src/otj_helper/templates/mentor/dashboard.html` | Create | Mentor learner list |
| `src/otj_helper/templates/mentor/learner_detail.html` | Create | Learner activity view |
| `src/otj_helper/templates/mentor/activity_review.html` | Create | Review + comment UI |
| `src/otj_helper/templates/base.html` | Edit | Conditional mentor nav link |
| `tests/test_mentor.py` | Create | RBAC and review workflow tests |

---

## Security Considerations

- **Authorization:** Mentors can only view activities of their paired learners. All queries must check the `mentor_learners` relationship.
- **Role enforcement:** `@mentor_required` decorator returns 403 for non-mentors.
- **Comment XSS:** Comments rendered with `{{ comment.body }}` (auto-escaped by Jinja2).
- **State machine:** Only valid transitions allowed (draft->submitted, submitted->approved/needs_revision, needs_revision->submitted).

---

## Testing Checklist

- [ ] `uv run pytest tests/test_mentor.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: create a mentor user, pair with learner
- [ ] Manual: learner submits activity for review
- [ ] Manual: mentor sees pending review, approves it
- [ ] Manual: mentor leaves comment, learner sees it
- [ ] Manual: non-mentor gets 403 on mentor routes
