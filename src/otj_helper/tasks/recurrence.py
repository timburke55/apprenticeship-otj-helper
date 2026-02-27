"""Recurring activity generation task."""

from datetime import date, timedelta


def generate_recurring_activities():
    """Check all recurring templates and create draft activities for the current weekday.

    Only generates an activity when today matches the template's configured weekday
    and no activity has already been generated for that date.  Must be called
    within an active Flask application context.
    """
    from otj_helper.models import Activity, ActivityTemplate, KSB, Tag, db

    today = date.today()
    templates = ActivityTemplate.query.filter_by(is_recurring=True).all()

    for tmpl in templates:
        if tmpl.recurrence_day is None:
            continue

        # Only generate on the configured weekday
        if today.weekday() != tmpl.recurrence_day:
            continue

        # target_date is always today when weekday matches
        days_since = (today.weekday() - tmpl.recurrence_day) % 7
        target_date = today - timedelta(days=days_since)

        # Skip if already generated for this week
        if tmpl.last_generated is not None and tmpl.last_generated >= target_date:
            continue

        activity = Activity(
            user_id=tmpl.user_id,
            title=tmpl.title,
            description=tmpl.description or "",
            activity_date=target_date,
            duration_hours=tmpl.duration_hours if tmpl.duration_hours is not None else 1.0,
            activity_type=tmpl.activity_type,
            evidence_quality="draft",
        )

        if tmpl.ksb_codes_csv:
            codes = [c.strip() for c in tmpl.ksb_codes_csv.split(",") if c.strip()]
            activity.ksbs = KSB.query.filter(KSB.code.in_(codes)).all()

        if tmpl.tags_csv:
            for raw_name in tmpl.tags_csv.split(","):
                name = raw_name.strip().lower()
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
