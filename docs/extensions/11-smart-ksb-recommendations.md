# Extension 11: Smart KSB Recommendations

## Overview

Analyse the user's activity log and provide intelligent recommendations: which KSBs are under-evidenced, what activity types they haven't tried, which CORE workflow stages are missing resources, and what to focus on next. Starts rule-based, with the option to add LLM-powered suggestions later.

**Complexity drivers:** Gap analysis algorithms, scoring models, heuristic tuning, recommendation ranking, contextual awareness (how far into the apprenticeship are they?), and a clear, actionable UI.

---

## Prerequisites

No new external dependencies for the rule-based engine. Optionally builds on Extension 01 (LLM) for natural-language recommendations.

---

## Step-by-step Implementation

### 1. Create the recommendation engine

**New file:** `src/otj_helper/recommendations.py`

```python
"""KSB recommendation engine -- identifies gaps and suggests next actions."""

from collections import defaultdict
from datetime import date, timedelta

from otj_helper.models import Activity, KSB, ResourceLink, activity_ksbs, db


def analyse_gaps(user_id: int, spec_code: str) -> dict:
    """Analyse a user's activity log and return structured recommendations.

    Returns a dict with keys:
        - ksb_gaps: list of KSBs with no or low evidence
        - type_gaps: activity types not yet used
        - workflow_gaps: CORE stages with few resources
        - staleness: KSBs not updated in >30 days
        - quality_gaps: KSBs with only 'draft' evidence
        - overall_score: 0-100 readiness score
        - suggestions: list of actionable suggestion strings
    """
    # All KSBs for this spec
    all_ksbs = KSB.query.filter_by(spec_code=spec_code).order_by(KSB.code).all()

    # All activities for this user
    activities = Activity.query.filter_by(user_id=user_id).all()

    # Hours per KSB
    ksb_hours = defaultdict(float)
    ksb_count = defaultdict(int)
    ksb_last_date = {}
    ksb_qualities = defaultdict(list)

    for a in activities:
        for k in a.ksbs:
            ksb_hours[k.code] += a.duration_hours
            ksb_count[k.code] += 1
            if k.code not in ksb_last_date or a.activity_date > ksb_last_date[k.code]:
                ksb_last_date[k.code] = a.activity_date
            ksb_qualities[k.code].append(a.evidence_quality or "draft")

    # --- KSB Gaps ---
    ksb_gaps = []
    for k in all_ksbs:
        hours = ksb_hours.get(k.code, 0)
        count = ksb_count.get(k.code, 0)
        if hours == 0:
            ksb_gaps.append({
                "ksb": k, "hours": 0, "count": 0,
                "severity": "critical", "reason": "No evidence at all",
            })
        elif hours < 2.0:
            ksb_gaps.append({
                "ksb": k, "hours": round(hours, 1), "count": count,
                "severity": "warning", "reason": f"Only {hours:.1f}h logged",
            })

    # --- Activity Type Gaps ---
    used_types = {a.activity_type for a in activities}
    all_types = {t for t, _ in Activity.ACTIVITY_TYPES}
    type_gaps = [
        {"type": t, "label": dict(Activity.ACTIVITY_TYPES)[t]}
        for t in sorted(all_types - used_types)
    ]

    # --- CORE Workflow Gaps ---
    stage_counts = defaultdict(int)
    for a in activities:
        for r in a.resources:
            stage_counts[r.workflow_stage] += 1

    workflow_gaps = []
    for stage_id, label, desc, _ in ResourceLink.WORKFLOW_STAGES:
        count = stage_counts.get(stage_id, 0)
        if count == 0:
            workflow_gaps.append({
                "stage": stage_id, "label": label, "count": 0,
                "reason": f"No {label} resources linked yet",
            })

    # --- Staleness ---
    today = date.today()
    stale_threshold = today - timedelta(days=30)
    staleness = []
    for k in all_ksbs:
        last = ksb_last_date.get(k.code)
        if last and last < stale_threshold and ksb_hours.get(k.code, 0) > 0:
            days_ago = (today - last).days
            staleness.append({
                "ksb": k, "last_date": last, "days_ago": days_ago,
            })

    # --- Quality Gaps ---
    quality_gaps = []
    for k in all_ksbs:
        qualities = ksb_qualities.get(k.code, [])
        if qualities and all(q == "draft" for q in qualities):
            quality_gaps.append({
                "ksb": k, "count": len(qualities),
                "reason": "All evidence is still in draft quality",
            })

    # --- Overall Score ---
    total_ksbs = len(all_ksbs)
    covered = sum(1 for k in all_ksbs if ksb_hours.get(k.code, 0) > 0)
    good_quality = sum(
        1 for k in all_ksbs
        if any(q in ("good", "review_ready") for q in ksb_qualities.get(k.code, []))
    )
    coverage_pct = (covered / total_ksbs * 100) if total_ksbs else 0
    quality_pct = (good_quality / total_ksbs * 100) if total_ksbs else 0
    overall_score = round((coverage_pct * 0.6 + quality_pct * 0.4), 0)

    # --- Actionable Suggestions ---
    suggestions = []
    critical_gaps = [g for g in ksb_gaps if g["severity"] == "critical"]
    if critical_gaps:
        codes = ", ".join(g["ksb"].natural_code for g in critical_gaps[:5])
        suggestions.append(f"Priority: log evidence for {codes} (no evidence yet)")

    if type_gaps:
        labels = ", ".join(g["label"] for g in type_gaps[:3])
        suggestions.append(f"Try new activity types: {labels}")

    if workflow_gaps:
        stages = ", ".join(g["label"] for g in workflow_gaps)
        suggestions.append(f"Add CORE workflow resources: {stages}")

    if staleness:
        codes = ", ".join(s["ksb"].natural_code for s in staleness[:3])
        suggestions.append(f"Revisit stale KSBs: {codes} (no activity in 30+ days)")

    if quality_gaps:
        codes = ", ".join(g["ksb"].natural_code for g in quality_gaps[:5])
        suggestions.append(f"Improve evidence quality: {codes} (all still draft)")

    return {
        "ksb_gaps": ksb_gaps,
        "type_gaps": type_gaps,
        "workflow_gaps": workflow_gaps,
        "staleness": staleness,
        "quality_gaps": quality_gaps,
        "overall_score": overall_score,
        "coverage_pct": round(coverage_pct, 0),
        "quality_pct": round(quality_pct, 0),
        "suggestions": suggestions,
    }
```

### 2. Create the recommendations route

**New file:** `src/otj_helper/routes/recommendations.py`

```python
bp = Blueprint("recommendations", __name__, url_prefix="/recommendations")


@bp.route("/")
@login_required
def index():
    """Show the recommendations dashboard."""
    from otj_helper.recommendations import analyse_gaps
    spec = g.user.selected_spec or "ST0787"
    analysis = analyse_gaps(g.user.id, spec)
    return render_template("recommendations/index.html", **analysis)
```

### 3. Create the recommendations template

**New file:** `src/otj_helper/templates/recommendations/index.html`

Extends `base.html`. Layout:

**Top: Readiness Score**
- Large circular progress indicator (CSS) showing overall_score out of 100
- Breakdown: coverage % and quality %
- Colour: green (>75), amber (50-75), red (<50)

**Section: Priority Actions**
- Ordered list of `suggestions` as actionable cards
- Each card has a link to the relevant page (e.g. "Log activity for K3" links to `/activities/new`)

**Section: KSB Gaps**
- Table: KSB code, title, severity badge (critical=red, warning=amber), hours logged, action link
- Critical gaps highlighted at top

**Section: Activity Type Diversity**
- Grid of all activity types, greyed out for unused types
- "Try this" links for unused types

**Section: CORE Workflow Coverage**
- Four-stage pipeline indicator (similar to activity detail) showing which stages have resources

**Section: Stale Evidence**
- Table: KSB code, last activity date, days since last update

**Section: Quality Improvement**
- Table: KSBs where all evidence is draft quality
- Links to edit those activities

### 4. Add recommendations widget to dashboard

**File:** `src/otj_helper/templates/dashboard.html`

Add a compact widget above the existing content:

```html
<!-- Readiness score widget -->
<div class="bg-white shadow rounded-lg p-6 mb-8">
    <div class="flex items-center justify-between">
        <div>
            <h2 class="text-lg font-medium text-gray-900">Portfolio Readiness</h2>
            <p class="text-sm text-gray-500">Based on KSB coverage and evidence quality</p>
        </div>
        <a href="{{ url_for('recommendations.index') }}"
            class="text-sm text-indigo-600 hover:text-indigo-500">View recommendations</a>
    </div>
    <!-- Compact score display -->
</div>
```

The dashboard route in `routes/dashboard.py` needs to call `analyse_gaps()` and pass `overall_score` and `suggestions` (first 3) to the template.

### 5. Register blueprint and add navigation

**File:** `src/otj_helper/app.py`

```python
from otj_helper.routes.recommendations import bp as recommendations_bp
app.register_blueprint(recommendations_bp)
```

**File:** `src/otj_helper/templates/base.html`

Add "Recommendations" link to nav bar.

### 6. Write tests

**New file:** `tests/test_recommendations.py`

```python
def test_recommendations_page_accessible(_with_spec, client):
    """Recommendations page returns 200."""
    resp = client.get("/recommendations/")
    assert resp.status_code == 200

def test_analyse_gaps_empty_log(_with_spec, app):
    """Analysis with no activities returns all KSBs as critical gaps."""
    from otj_helper.recommendations import analyse_gaps
    from otj_helper.models import User
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        assert result["overall_score"] == 0
        assert len(result["ksb_gaps"]) > 0
        assert all(g["severity"] == "critical" for g in result["ksb_gaps"])

def test_analyse_gaps_with_activity(_with_spec, client, app):
    """Activity reduces gaps and increases score."""
    from otj_helper.recommendations import analyse_gaps
    from otj_helper.models import User

    # Create an activity linked to K1
    client.post("/activities/new", data={
        "title": "Test", "activity_date": "2024-03-15",
        "duration_hours": "3.0", "activity_type": "self_study",
        "evidence_quality": "good", "ksbs": ["K1"],
    })

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        assert result["overall_score"] > 0
        # K1 should not be in critical gaps
        critical_codes = [g["ksb"].code for g in result["ksb_gaps"] if g["severity"] == "critical"]
        assert "K1" not in critical_codes

def test_type_gap_detection(_with_spec, app):
    """Unused activity types are detected."""
    from otj_helper.recommendations import analyse_gaps
    from otj_helper.models import User
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        type_ids = {g["type"] for g in result["type_gaps"]}
        assert "conference" in type_ids  # Unlikely to be used in tests
```

---

## Files Changed Summary

| File | Action | Description |
|------|--------|-------------|
| `src/otj_helper/recommendations.py` | Create | Gap analysis engine |
| `src/otj_helper/routes/recommendations.py` | Create | Recommendations page route |
| `src/otj_helper/templates/recommendations/index.html` | Create | Full recommendations UI |
| `src/otj_helper/routes/dashboard.py` | Edit | Add readiness score to dashboard context |
| `src/otj_helper/templates/dashboard.html` | Edit | Readiness widget |
| `src/otj_helper/app.py` | Edit | Register blueprint |
| `src/otj_helper/templates/base.html` | Edit | Add nav link |
| `tests/test_recommendations.py` | Create | Gap analysis tests |

---

## Testing Checklist

- [ ] `uv run pytest tests/test_recommendations.py` -- all pass
- [ ] `uv run pytest` -- existing tests still pass
- [ ] Manual: view recommendations page with no activities -- all KSBs shown as critical
- [ ] Manual: log a few activities, verify score increases and gaps reduce
- [ ] Manual: check "Try new activity types" shows types not yet used
- [ ] Manual: check stale evidence appears after 30+ days without updates
