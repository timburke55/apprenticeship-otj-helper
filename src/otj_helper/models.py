"""Database models for OTJ tracking."""

from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """An authenticated user of the application."""

    __tablename__ = "app_user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    google_sub = db.Column(db.String(255), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    selected_spec = db.Column(db.String(20), nullable=True)  # e.g. 'ST0763'
    otj_target_hours = db.Column(db.Float, nullable=True)  # total OTJ hours target for the apprenticeship
    seminar_target_hours = db.Column(db.Float, nullable=True)  # expected total seminar/training hours
    weekly_target_hours = db.Column(db.Float, nullable=True)  # weekly OTJ hours target

    activities = db.relationship("Activity", backref="user", lazy="select")


# Many-to-many association table
activity_ksbs = db.Table(
    "activity_ksbs",
    db.Column("activity_id", db.Integer, db.ForeignKey("activity.id"), primary_key=True),
    db.Column("ksb_code", db.String(4), db.ForeignKey("ksb.code"), primary_key=True),
)


class KSB(db.Model):
    """Reference data for Knowledge, Skills and Behaviours."""

    code = db.Column(db.String(6), primary_key=True)  # e.g. K1, S3, B2, AK1, AS28
    spec_code = db.Column(db.String(20), nullable=False, default="ST0787")  # e.g. ST0763
    category = db.Column(db.String(12), nullable=False)  # knowledge, skill, behaviour
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)

    @property
    def natural_code(self):
        """Return the standard-display code without the spec prefix character.

        ST0787 codes have no prefix (K1 → K1).
        ST0763 codes are prefixed with 'A' (AK1 → K1, AS28 → S28).
        """
        if len(self.code) >= 3 and self.code[0].isalpha() and self.code[1].isalpha():
            return self.code[1:]
        return self.code


class Activity(db.Model):
    """A single off-the-job training activity."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=True)
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
    tags = db.relationship("Tag", secondary="activity_tags", backref="activities", lazy="select")

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

    EVIDENCE_QUALITY_OPTIONS = [
        ("draft", "Draft"),
        ("good", "Good"),
        ("review_ready", "Ready for Review"),
    ]

    evidence_quality = db.Column(db.String(20), nullable=True, default="draft")


# Many-to-many association table for tags
activity_tags = db.Table(
    "activity_tags",
    db.Column("activity_id", db.Integer, db.ForeignKey("activity.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tag.id"), primary_key=True),
)


class Tag(db.Model):
    """A user-defined label for categorising activities (e.g. 'systems thinking')."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("app_user.id"), nullable=False)

    __table_args__ = (db.UniqueConstraint("name", "user_id", name="uq_tag_name_user"),)


class ResourceLink(db.Model):
    """A link to an external resource associated with an activity."""

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="other")
    description = db.Column(db.Text, default="")
    workflow_stage = db.Column(db.String(20), nullable=False, default="engage")

    SOURCE_TYPES = [
        ("google_keep", "Google Keep"),
        ("google_tasks", "Google Tasks"),
        ("google_docs", "Google Docs"),
        ("google_drive", "Google Drive"),
        ("diagram", "Diagram"),
        ("markdown", "Markdown"),
        ("github", "GitHub"),
        ("website", "Website"),
        ("other", "Other"),
    ]

    # Each tuple: (id, label, description, default_source_type)
    WORKFLOW_STAGES = [
        ("capture", "Capture", "Initial notes and ideas — typically Google Keep", "google_keep"),
        ("organise", "Organise", "Structured tasks and planning — typically Google Tasks", "google_tasks"),
        ("review", "Review", "Synthesis documents, diagrams, and markdown files", "google_docs"),
        ("engage", "Engage", "Final outputs and evidence — docs, drive files, code", "google_docs"),
    ]
