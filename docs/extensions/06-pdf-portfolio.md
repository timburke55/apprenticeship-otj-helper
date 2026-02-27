# Extension 06: Evidence Portfolio PDF Generation

## Overview

Generate a formatted PDF portfolio that an apprentice can submit to their EPA (End-Point Assessment) assessor. The portfolio groups evidence by KSB, includes resource links, hours breakdowns, and summary charts. Uses WeasyPrint for HTML-to-PDF conversion.

**Complexity drivers:** PDF layout engine, pagination, embedded charts/images, large document memory management, CSS print styles, table-of-contents generation, and a multi-page report structure.

---

## Prerequisites

- New dependency: `weasyprint>=62.0`
- System dependency: WeasyPrint requires `pango`, `cairo`, `gdk-pixbuf` (usually available on Linux; needs `brew install` on macOS)

---

## Step-by-step Implementation

### 1. Add dependency

**File:** `pyproject.toml`

Add `"weasyprint>=62.0"` to `dependencies`. Run `uv sync`.

### 2. Create the PDF generation service

**New file:** `src/otj_helper/pdf.py`

```python
"""PDF portfolio generation using WeasyPrint."""

import logging
from collections import defaultdict
from datetime import date

from flask import render_template
from sqlalchemy import func

from otj_helper.models import Activity, KSB, activity_ksbs, db

logger = logging.getLogger(__name__)


def generate_portfolio_pdf(user, spec):
    """Generate a PDF portfolio for the user.

    Args:
        user: The User model instance.
        spec: The spec dict from SPECS_BY_CODE.

    Returns:
        bytes: The PDF content.
    """
    from weasyprint import HTML

    uid = user.id
    spec_code = user.selected_spec or "ST0787"

    # Gather all activities
    activities = (
        Activity.query.filter_by(user_id=uid)
        .order_by(Activity.activity_date.desc())
        .all()
    )

    # Total hours
    total_hours = sum(a.duration_hours for a in activities)

    # Hours by type
    type_labels = dict(Activity.ACTIVITY_TYPES)
    hours_by_type = defaultdict(float)
    for a in activities:
        hours_by_type[type_labels.get(a.activity_type, a.activity_type)] += a.duration_hours

    # KSB coverage with linked activities
    ksbs = KSB.query.filter_by(spec_code=spec_code).order_by(KSB.code).all()
    ksb_activities = defaultdict(list)
    for a in activities:
        for k in a.ksbs:
            ksb_activities[k.code].append(a)

    ksb_data = []
    for k in ksbs:
        acts = ksb_activities.get(k.code, [])
        ksb_data.append({
            "ksb": k,
            "activities": acts,
            "total_hours": sum(a.duration_hours for a in acts),
            "activity_count": len(acts),
        })

    # Render HTML template
    html_content = render_template(
        "pdf/portfolio.html",
        user=user,
        spec=spec,
        activities=activities,
        total_hours=total_hours,
        hours_by_type=dict(hours_by_type),
        ksb_data=ksb_data,
        generated_date=date.today(),
        activity_count=len(activities),
    )

    # Convert to PDF
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
```

### 3. Create the PDF template

**New file:** `src/otj_helper/templates/pdf/portfolio.html`

This is a standalone HTML file (not extending base.html) with embedded CSS for print:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {
            size: A4;
            margin: 2cm;
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-size: 9pt;
                color: #666;
            }
        }
        body { font-family: sans-serif; font-size: 10pt; color: #1f2937; }
        h1 { font-size: 20pt; color: #1e40af; margin-bottom: 4pt; }
        h2 { font-size: 14pt; color: #1e40af; margin-top: 16pt; border-bottom: 1px solid #dbeafe; padding-bottom: 4pt; }
        h3 { font-size: 11pt; margin-top: 12pt; }
        table { width: 100%; border-collapse: collapse; margin-top: 8pt; }
        th, td { padding: 4pt 6pt; text-align: left; border-bottom: 1px solid #e5e7eb; font-size: 9pt; }
        th { background: #f3f4f6; font-weight: 600; }
        .ksb-section { page-break-inside: avoid; }
        .badge { display: inline-block; padding: 1pt 6pt; border-radius: 3pt; font-size: 8pt; font-weight: 600; }
        .badge-k { background: #dbeafe; color: #1e40af; }
        .badge-s { background: #dcfce7; color: #166534; }
        .badge-b { background: #fef3c7; color: #92400e; }
        .summary-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12pt; margin: 12pt 0; }
        .summary-box { border: 1px solid #e5e7eb; border-radius: 4pt; padding: 8pt; }
        .stat-value { font-size: 18pt; font-weight: 700; color: #4338ca; }
        .stat-label { font-size: 8pt; color: #6b7280; }
        .toc-entry { margin: 4pt 0; }
        .toc-entry a { color: #4338ca; text-decoration: none; }
    </style>
</head>
<body>
    <!-- Title page -->
    <div style="text-align: center; padding-top: 40%;">
        <h1>OTJ Evidence Portfolio</h1>
        <p style="font-size: 14pt; color: #4b5563;">{{ spec.name }} L{{ spec.level }}</p>
        <p>{{ user.name or user.email }}</p>
        <p style="color: #9ca3af;">Generated {{ generated_date.strftime('%d %B %Y') }}</p>
    </div>

    <div style="page-break-after: always;"></div>

    <!-- Summary page -->
    <h2>Summary</h2>
    <div class="summary-grid">
        <div class="summary-box">
            <div class="stat-value">{{ "%.1f"|format(total_hours) }}h</div>
            <div class="stat-label">Total OTJ Hours</div>
        </div>
        <div class="summary-box">
            <div class="stat-value">{{ activity_count }}</div>
            <div class="stat-label">Activities Logged</div>
        </div>
    </div>

    <h3>Hours by Activity Type</h3>
    <table>
        <tr><th>Type</th><th>Hours</th></tr>
        {% for type_name, hours in hours_by_type.items()|sort(attribute='1', reverse=true) %}
        <tr><td>{{ type_name }}</td><td>{{ "%.1f"|format(hours) }}</td></tr>
        {% endfor %}
    </table>

    <div style="page-break-after: always;"></div>

    <!-- KSB Evidence sections -->
    <h2>Evidence by KSB</h2>

    {% for item in ksb_data %}
    <div class="ksb-section">
        <h3>
            <span class="badge {% if item.ksb.category == 'knowledge' %}badge-k{% elif item.ksb.category == 'skill' %}badge-s{% else %}badge-b{% endif %}">
                {{ item.ksb.natural_code }}
            </span>
            {{ item.ksb.title }}
            <span style="font-weight: normal; color: #6b7280; font-size: 9pt;">
                ({{ item.activity_count }} activities, {{ "%.1f"|format(item.total_hours) }}h)
            </span>
        </h3>
        <p style="font-size: 9pt; color: #6b7280; margin: 4pt 0;">{{ item.ksb.description }}</p>

        {% if item.activities %}
        <table>
            <tr><th>Date</th><th>Activity</th><th>Hours</th><th>Type</th><th>Quality</th></tr>
            {% for a in item.activities %}
            <tr>
                <td>{{ a.activity_date.strftime('%d/%m/%Y') }}</td>
                <td>{{ a.title }}</td>
                <td>{{ "%.1f"|format(a.duration_hours) }}</td>
                <td>{{ dict(a.ACTIVITY_TYPES).get(a.activity_type, a.activity_type) }}</td>
                <td>{{ dict(a.EVIDENCE_QUALITY_OPTIONS).get(a.evidence_quality or 'draft', 'draft') }}</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <p style="color: #ef4444; font-size: 9pt;">No evidence linked to this KSB yet.</p>
        {% endif %}
    </div>
    {% endfor %}

    <div style="page-break-after: always;"></div>

    <!-- Full activity log -->
    <h2>Full Activity Log</h2>
    <table>
        <tr><th>Date</th><th>Title</th><th>Hours</th><th>Type</th><th>KSBs</th></tr>
        {% for a in activities %}
        <tr>
            <td>{{ a.activity_date.strftime('%d/%m/%Y') }}</td>
            <td>{{ a.title }}</td>
            <td>{{ "%.1f"|format(a.duration_hours) }}</td>
            <td>{{ dict(a.ACTIVITY_TYPES).get(a.activity_type, a.activity_type) }}</td>
            <td>{{ a.ksbs|map(attribute='natural_code')|join(', ') }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
```

### 4. Create the download route

**New file:** `src/otj_helper/routes/portfolio.py`

```python
"""Portfolio PDF generation routes."""

from flask import Blueprint, Response, flash, g, redirect, render_template, url_for

from otj_helper.auth import login_required
from otj_helper.specs_data import SPECS_BY_CODE

bp = Blueprint("portfolio", __name__, url_prefix="/portfolio")


@bp.route("/")
@login_required
def index():
    """Show portfolio preview/download page."""
    return render_template("portfolio/index.html")


@bp.route("/download")
@login_required
def download():
    """Generate and download the PDF portfolio."""
    from otj_helper.pdf import generate_portfolio_pdf

    spec = SPECS_BY_CODE.get(g.user.selected_spec)
    if not spec:
        flash("Select a spec first.", "error")
        return redirect(url_for("landing.index"))

    try:
        pdf_bytes = generate_portfolio_pdf(g.user, spec)
    except Exception as exc:
        flash(f"PDF generation failed: {exc}", "error")
        return redirect(url_for("portfolio.index"))

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=otj_portfolio.pdf"},
    )
```

### 5. Create the portfolio preview page

**New file:** `src/otj_helper/templates/portfolio/index.html`

Extends `base.html`. Shows:
- Summary of what the PDF will contain (KSB count, activity count, total hours)
- "Download PDF" button linking to `url_for('portfolio.download')`
- Note about WeasyPrint system dependencies

### 6. Register blueprint

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.portfolio import bp as portfolio_bp
app.register_blueprint(portfolio_bp)
```

### 7. Add navigation link

**File:** `src/otj_helper/templates/base.html`

Add "Portfolio" link in nav: `url_for('portfolio.index')`.

### 8. Write tests

**New file:** `tests/test_pdf.py`

```python
def test_portfolio_page_accessible(_with_spec, client):
    """Portfolio page returns 200."""
    resp = client.get("/portfolio/")
    assert resp.status_code == 200

def test_portfolio_download_returns_pdf(_with_spec, client):
    """Download endpoint returns PDF content type."""
    # Create a test activity first
    client.post("/activities/new", data={
        "title": "PDF test", "activity_date": "2024-03-15",
        "duration_hours": "2.0", "activity_type": "self_study",
        "evidence_quality": "good",
    })
    resp = client.get("/portfolio/download")
    assert resp.status_code == 200
    assert resp.content_type == "application/pdf"
    assert resp.data[:4] == b"%PDF"  # PDF magic bytes
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Edit | Add `weasyprint` dependency |
| `src/otj_helper/pdf.py` | Create | PDF generation service |
| `src/otj_helper/templates/pdf/portfolio.html` | Create | PDF HTML template with print CSS |
| `src/otj_helper/routes/portfolio.py` | Create | Portfolio routes |
| `src/otj_helper/templates/portfolio/index.html` | Create | Preview/download page |
| `src/otj_helper/app.py` | Edit | Register blueprint |
| `src/otj_helper/templates/base.html` | Edit | Add "Portfolio" nav link |
| `tests/test_pdf.py` | Create | PDF generation tests |

---

## Security Considerations

- **Memory:** Large portfolios with many activities could use significant memory during PDF generation. Consider paginating or streaming for very large datasets.
- **WeasyPrint security:** WeasyPrint can fetch external URLs in the HTML (images, CSS). Our template uses only inline styles, so no external fetches.
- **File size:** PDFs with many pages can be large. Consider adding a size limit or warning.

---

## Testing Checklist

- [ ] `uv run pytest tests/test_pdf.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: navigate to Portfolio page, click download
- [ ] Manual: open downloaded PDF, verify title page, summary, KSB sections, activity log
- [ ] Manual: verify page numbers appear in footer
- [ ] Manual: verify KSB colour badges render correctly
