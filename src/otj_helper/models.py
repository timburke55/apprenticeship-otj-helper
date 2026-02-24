"""Database models for OTJ tracking."""

from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# Many-to-many association table
activity_ksbs = db.Table(
    "activity_ksbs",
    db.Column("activity_id", db.Integer, db.ForeignKey("activity.id"), primary_key=True),
    db.Column("ksb_code", db.String(4), db.ForeignKey("ksb.code"), primary_key=True),
)


class KSB(db.Model):
    """Reference data for Knowledge, Skills and Behaviours."""

    code = db.Column(db.String(4), primary_key=True)  # e.g. K1, S3, B2
    category = db.Column(db.String(12), nullable=False)  # knowledge, skill, behaviour
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)


class Activity(db.Model):
    """A single off-the-job training activity."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    activity_date = db.Column(db.Date, nullable=False, default=date.today)
    duration_hours = db.Column(db.Float, nullable=False)  # decimal hours
    activity_type = db.Column(db.String(50), nullable=False, default="self_study")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ksbs = db.relationship("KSB", secondary=activity_ksbs, backref="activities", lazy="select")
    resources = db.relationship("ResourceLink", backref="activity", cascade="all, delete-orphan")

    ACTIVITY_TYPES = [
        ("training_course", "Training Course"),
        ("self_study", "Self-Study"),
        ("mentoring", "Mentoring"),
        ("shadowing", "Shadowing"),
        ("workshop", "Workshop"),
        ("conference", "Conference / Event"),
        ("project_work", "Project Work"),
        ("research", "Research"),
        ("writing", "Writing / Reflection"),
        ("other", "Other"),
    ]


class ResourceLink(db.Model):
    """A link to an external resource associated with an activity."""

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="other")
    description = db.Column(db.Text, default="")

    SOURCE_TYPES = [
        ("google_drive", "Google Drive"),
        ("github", "GitHub"),
        ("website", "Website"),
        ("other", "Other"),
    ]
