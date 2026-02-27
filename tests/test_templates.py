"""Tests for activity template CRUD and recurring generation."""

import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_template(client, **overrides):
    """POST a valid template creation form, returning the response."""
    data = {
        "name": "Weekly mentor meeting",
        "title": "Mentor session",
        "activity_type": "mentoring",
        "duration_hours": "1.0",
        "description": "Regular mentor check-in",
        "tags_csv": "mentoring",
        "evidence_quality": "draft",
        **overrides,
    }
    return client.post("/templates/new", data=data, follow_redirects=True)


# ---------------------------------------------------------------------------
# Template list
# ---------------------------------------------------------------------------


def test_template_list_accessible(_with_spec, client):
    """GET /templates/ returns 200 for a logged-in user."""
    resp = client.get("/templates/")
    assert resp.status_code == 200


def test_template_list_empty_state(_with_spec, client):
    """Empty template list renders without error."""
    resp = client.get("/templates/")
    assert resp.status_code == 200
    assert b"No templates yet" in resp.data


# ---------------------------------------------------------------------------
# Create template
# ---------------------------------------------------------------------------


def test_create_template_saves_to_db(_with_spec, client, app):
    """A valid template POST creates a record in the database."""
    resp = _create_template(client)
    assert resp.status_code == 200

    with app.app_context():
        from otj_helper.models import ActivityTemplate
        tmpl = ActivityTemplate.query.filter_by(name="Weekly mentor meeting").first()
        assert tmpl is not None
        assert tmpl.title == "Mentor session"
        assert tmpl.activity_type == "mentoring"
        assert round(tmpl.duration_hours, 1) == 1.0


def test_create_template_missing_name_returns_422(_with_spec, client):
    """A template with no name must return HTTP 422."""
    resp = client.post(
        "/templates/new",
        data={
            "name": "",
            "title": "Something",
            "activity_type": "self_study",
            "evidence_quality": "draft",
        },
    )
    assert resp.status_code == 422


def test_create_template_missing_title_returns_422(_with_spec, client):
    """A template with no title must return HTTP 422."""
    resp = client.post(
        "/templates/new",
        data={
            "name": "My Template",
            "title": "",
            "activity_type": "self_study",
            "evidence_quality": "draft",
        },
    )
    assert resp.status_code == 422


def test_create_template_negative_duration_returns_422(_with_spec, client):
    """A negative duration must return HTTP 422."""
    resp = client.post(
        "/templates/new",
        data={
            "name": "My Template",
            "title": "Something",
            "activity_type": "self_study",
            "duration_hours": "-1",
            "evidence_quality": "draft",
        },
    )
    assert resp.status_code == 422


def test_create_template_with_ksbs(_with_spec, client, app):
    """KSB codes submitted with the form are stored as CSV."""
    resp = client.post(
        "/templates/new",
        data={
            "name": "KSB Template",
            "title": "KSB Activity",
            "activity_type": "self_study",
            "evidence_quality": "draft",
            "ksb_codes": ["K1", "S1"],
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        from otj_helper.models import ActivityTemplate
        tmpl = ActivityTemplate.query.filter_by(name="KSB Template").first()
        assert tmpl is not None
        codes = {c.strip() for c in tmpl.ksb_codes_csv.split(",") if c.strip()}
        assert "K1" in codes
        assert "S1" in codes


# ---------------------------------------------------------------------------
# Edit and delete template
# ---------------------------------------------------------------------------


def test_edit_template(_with_spec, client, app):
    """Editing a template updates its DB record."""
    _create_template(client)

    with app.app_context():
        from otj_helper.models import ActivityTemplate
        tmpl = ActivityTemplate.query.filter_by(name="Weekly mentor meeting").first()
        tmpl_id = tmpl.id

    resp = client.post(
        f"/templates/{tmpl_id}/edit",
        data={
            "name": "Updated Template",
            "title": "Updated Title",
            "activity_type": "research",
            "evidence_quality": "good",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        from otj_helper.models import ActivityTemplate, db
        updated = db.session.get(ActivityTemplate, tmpl_id)
        assert updated.name == "Updated Template"
        assert updated.activity_type == "research"


def test_delete_template(_with_spec, client, app):
    """Deleting a template removes it from the DB."""
    _create_template(client)

    with app.app_context():
        from otj_helper.models import ActivityTemplate
        tmpl_id = ActivityTemplate.query.filter_by(name="Weekly mentor meeting").first().id

    resp = client.post(f"/templates/{tmpl_id}/delete", follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        from otj_helper.models import ActivityTemplate, db
        assert db.session.get(ActivityTemplate, tmpl_id) is None


# ---------------------------------------------------------------------------
# Use template — pre-fills activity form via redirect
# ---------------------------------------------------------------------------


def test_use_template_redirects_with_query_params(_with_spec, client, app):
    """GET /templates/<id>/use redirects to /activities/new with pre-fill params."""
    _create_template(client)

    with app.app_context():
        from otj_helper.models import ActivityTemplate
        tmpl_id = ActivityTemplate.query.filter_by(name="Weekly mentor meeting").first().id

    resp = client.get(f"/templates/{tmpl_id}/use", follow_redirects=False)
    assert resp.status_code == 302
    location = resp.headers["Location"]
    assert "/activities/new" in location
    assert "tmpl_title=" in location
    assert "tmpl_type=" in location


def test_use_template_activity_form_preloads(_with_spec, client, app):
    """Following the use-template redirect renders the activity form with pre-filled values."""
    _create_template(client, title="Mentor session", activity_type="mentoring")

    with app.app_context():
        from otj_helper.models import ActivityTemplate
        tmpl_id = ActivityTemplate.query.filter_by(name="Weekly mentor meeting").first().id

    resp = client.get(f"/templates/{tmpl_id}/use", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Mentor session" in resp.data


# ---------------------------------------------------------------------------
# Create from activity
# ---------------------------------------------------------------------------


def test_create_from_activity_prefills_form(_with_spec, client, app):
    """GET /templates/from-activity/<id> renders the template form pre-filled."""
    # Create an activity first
    client.post(
        "/activities/new",
        data={
            "title": "My test activity",
            "activity_date": "2024-03-15",
            "duration_hours": "2.0",
            "activity_type": "research",
            "description": "Some research work",
            "notes": "",
            "tags": "",
            "evidence_quality": "good",
        },
    )

    with app.app_context():
        from otj_helper.models import Activity
        activity_id = Activity.query.filter_by(title="My test activity").first().id

    resp = client.get(f"/templates/from-activity/{activity_id}")
    assert resp.status_code == 200
    assert b"My test activity" in resp.data


# ---------------------------------------------------------------------------
# Recurring activity generation
# ---------------------------------------------------------------------------


def _ensure_user(db, User, email="test@example.com"):
    """Return the dev user, creating it if necessary."""
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name="Dev User")
        db.session.add(user)
        db.session.commit()
    return user


def test_recurring_generation_creates_activity(app):
    """generate_recurring_activities creates a draft activity on the correct weekday."""
    with app.app_context():
        from otj_helper.models import Activity, ActivityTemplate, User, db
        from otj_helper.tasks.recurrence import generate_recurring_activities

        user = _ensure_user(db, User)
        today = datetime.date.today()

        tmpl = ActivityTemplate(
            user_id=user.id,
            name="Recurring test",
            title="Weekly standup",
            activity_type="mentoring",
            duration_hours=0.5,
            evidence_quality="draft",
            is_recurring=True,
            recurrence_day=today.weekday(),  # matches today
        )
        db.session.add(tmpl)
        db.session.commit()

        before_count = Activity.query.filter_by(user_id=user.id).count()
        generate_recurring_activities()
        after_count = Activity.query.filter_by(user_id=user.id).count()

        assert after_count == before_count + 1

        created = Activity.query.filter_by(title="Weekly standup").first()
        assert created is not None
        assert created.activity_date == today
        assert created.evidence_quality == "draft"

        # last_generated should be updated
        db.session.refresh(tmpl)
        assert tmpl.last_generated == today


def test_recurring_generation_skips_if_already_generated(app):
    """generate_recurring_activities skips templates already generated this week."""
    with app.app_context():
        from otj_helper.models import Activity, ActivityTemplate, User, db
        from otj_helper.tasks.recurrence import generate_recurring_activities

        user = _ensure_user(db, User)
        today = datetime.date.today()

        tmpl = ActivityTemplate(
            user_id=user.id,
            name="Already done",
            title="Should not repeat",
            activity_type="self_study",
            duration_hours=1.0,
            is_recurring=True,
            recurrence_day=today.weekday(),
            last_generated=today,  # already generated today
        )
        db.session.add(tmpl)
        db.session.commit()

        before_count = Activity.query.filter_by(user_id=user.id).count()
        generate_recurring_activities()
        after_count = Activity.query.filter_by(user_id=user.id).count()

        assert after_count == before_count  # no new activity created


def test_recurring_generation_skips_wrong_day(app):
    """generate_recurring_activities does not generate on wrong weekday."""
    with app.app_context():
        from otj_helper.models import Activity, ActivityTemplate, User, db
        from otj_helper.tasks.recurrence import generate_recurring_activities

        user = _ensure_user(db, User)
        today = datetime.date.today()
        wrong_day = (today.weekday() + 1) % 7  # tomorrow's weekday

        tmpl = ActivityTemplate(
            user_id=user.id,
            name="Wrong day",
            title="Should not appear today",
            activity_type="self_study",
            duration_hours=1.0,
            is_recurring=True,
            recurrence_day=wrong_day,
        )
        db.session.add(tmpl)
        db.session.commit()

        before_count = Activity.query.filter_by(user_id=user.id).count()
        generate_recurring_activities()
        after_count = Activity.query.filter_by(user_id=user.id).count()

        assert after_count == before_count
