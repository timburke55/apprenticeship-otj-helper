"""KSB recommendation engine -- identifies gaps and suggests next actions."""

from collections import defaultdict
from datetime import date, timedelta

from otj_helper.models import Activity, KSB, ResourceLink


def analyse_gaps(user_id: int, spec_code: str) -> dict:
    """Analyse a user's activity log and return structured recommendations.

    Returns a dict with keys:
        - ksb_gaps: list of KSBs with no or low evidence
        - type_gaps: activity types not yet used
        - workflow_gaps: CORE stages with few resources
        - staleness: KSBs not updated in >30 days
        - quality_gaps: KSBs with only 'draft' evidence
        - overall_score: 0-100 readiness score
        - coverage_pct: percentage of KSBs with any evidence
        - quality_pct: percentage of KSBs with good/review_ready evidence
        - suggestions: list of actionable suggestion strings
    """
    # All KSBs for this spec
    all_ksbs = KSB.query.filter_by(spec_code=spec_code).order_by(KSB.code).all()

    # All activities for this user
    activities = Activity.query.filter_by(user_id=user_id).all()

    # Hours per KSB
    ksb_hours: dict[str, float] = defaultdict(float)
    ksb_count: dict[str, int] = defaultdict(int)
    ksb_last_date: dict[str, date] = {}
    ksb_qualities: dict[str, list[str]] = defaultdict(list)

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
    type_label_map = dict(Activity.ACTIVITY_TYPES)
    type_gaps = [
        {"type": t, "label": type_label_map[t]}
        for t in sorted(all_types - used_types)
    ]

    # --- CORE Workflow Gaps ---
    stage_counts: dict[str, int] = defaultdict(int)
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
