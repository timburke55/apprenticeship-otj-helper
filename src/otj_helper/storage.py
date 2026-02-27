"""File storage abstraction -- local filesystem with optional thumbnail generation."""

import logging
import os
import uuid
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.environ.get(
    "UPLOAD_DIR",
    str(Path(__file__).resolve().parent.parent.parent / "data" / "uploads"),
)
THUMB_SIZE = (200, 200)


def _ensure_dirs():
    """Create upload and thumbnail directories if they don't exist."""
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(UPLOAD_DIR, "thumbs").mkdir(parents=True, exist_ok=True)


def save_file(file_obj, content_type: str) -> tuple[str, bool]:
    """Save an uploaded file and optionally generate a thumbnail.

    Args:
        file_obj: Werkzeug FileStorage object.
        content_type: The MIME type of the file.

    Returns:
        Tuple of (stored_name, has_thumbnail).
    """
    _ensure_dirs()

    ext = Path(file_obj.filename or "file").suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{ext}"
    dest = Path(UPLOAD_DIR) / stored_name
    file_obj.save(str(dest))

    has_thumb = False
    if content_type.startswith("image/"):
        try:
            img = Image.open(str(dest))
            img.thumbnail(THUMB_SIZE)
            thumb_path = Path(UPLOAD_DIR) / "thumbs" / stored_name
            img.save(str(thumb_path))
            has_thumb = True
        except Exception as exc:
            logger.warning("Thumbnail generation failed: %s", exc)

    return stored_name, has_thumb


def get_file_path(stored_name: str) -> str:
    """Return the full path to a stored file."""
    return str(Path(UPLOAD_DIR) / stored_name)


def get_thumb_path(stored_name: str) -> str:
    """Return the full path to a stored thumbnail."""
    return str(Path(UPLOAD_DIR) / "thumbs" / stored_name)


def delete_file(stored_name: str):
    """Delete a stored file and its thumbnail if they exist."""
    for path in [get_file_path(stored_name), get_thumb_path(stored_name)]:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
