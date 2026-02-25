"""Tags CRUD routes."""

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from otj_helper.auth import login_required
from otj_helper.models import Tag, db

bp = Blueprint("tags", __name__, url_prefix="/tags")


@bp.route("/")
@login_required
def list_tags():
    tags = (
        Tag.query.filter_by(user_id=g.user.id)
        .order_by(Tag.name)
        .all()
    )
    # Attach activity count to each tag for display
    tag_counts = {tag.id: len(tag.activities) for tag in tags}
    return render_template("tags/list.html", tags=tags, tag_counts=tag_counts)


@bp.route("/<int:tag_id>/delete", methods=["POST"])
@login_required
def delete(tag_id):
    tag = Tag.query.filter_by(id=tag_id, user_id=g.user.id).first_or_404()
    db.session.delete(tag)
    db.session.commit()
    flash(f'Tag "{tag.name}" deleted.', "info")
    return redirect(url_for("tags.list_tags"))


@bp.route("/<int:tag_id>/rename", methods=["POST"])
@login_required
def rename(tag_id):
    tag = Tag.query.filter_by(id=tag_id, user_id=g.user.id).first_or_404()
    new_name = request.form.get("name", "").strip().lower()
    if not new_name:
        flash("Tag name cannot be empty.", "error")
        return redirect(url_for("tags.list_tags"))
    existing = Tag.query.filter_by(name=new_name, user_id=g.user.id).first()
    if existing and existing.id != tag_id:
        flash(f'A tag named "{new_name}" already exists.', "error")
        return redirect(url_for("tags.list_tags"))
    tag.name = new_name
    db.session.commit()
    flash(f'Tag renamed to "{new_name}".', "success")
    return redirect(url_for("tags.list_tags"))
