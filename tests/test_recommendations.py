"""Tests for the KSB recommendation engine and recommendations page."""


def test_recommendations_page_accessible(_with_spec, client):
    """Recommendations page returns 200."""
    resp = client.get("/recommendations/")
    assert resp.status_code == 200


def test_analyse_gaps_empty_log(_with_spec, app):
    """Analysis with no activities returns all KSBs as critical gaps."""
    from otj_helper.models import User
    from otj_helper.recommendations import analyse_gaps

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        assert result["overall_score"] == 0
        assert len(result["ksb_gaps"]) > 0
        assert all(g["severity"] == "critical" for g in result["ksb_gaps"])


def test_analyse_gaps_with_activity(_with_spec, client, app):
    """Activity reduces gaps and increases score."""
    from otj_helper.models import User
    from otj_helper.recommendations import analyse_gaps

    # Create an activity linked to K1
    client.post(
        "/activities/new",
        data={
            "title": "Test",
            "activity_date": "2024-03-15",
            "duration_hours": "3.0",
            "activity_type": "self_study",
            "evidence_quality": "good",
            "ksbs": ["K1"],
        },
    )

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        assert result["overall_score"] > 0
        # K1 should not be in critical gaps
        critical_codes = [g["ksb"].code for g in result["ksb_gaps"] if g["severity"] == "critical"]
        assert "K1" not in critical_codes


def test_type_gap_detection(_with_spec, app):
    """Unused activity types are detected."""
    from otj_helper.models import User
    from otj_helper.recommendations import analyse_gaps

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        type_ids = {g["type"] for g in result["type_gaps"]}
        assert "conference" in type_ids  # Unlikely to be used in tests


def test_coverage_and_quality_pct(_with_spec, app):
    """Coverage and quality percentages are 0 with no activities."""
    from otj_helper.models import User
    from otj_helper.recommendations import analyse_gaps

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        result = analyse_gaps(user.id, "ST0787")
        assert result["coverage_pct"] == 0
        assert result["quality_pct"] == 0


def test_recommendations_page_has_score_display(_with_spec, client):
    """Recommendations page renders a readiness score."""
    resp = client.get("/recommendations/")
    assert resp.status_code == 200
    assert b"Readiness" in resp.data


def test_dashboard_includes_readiness_widget(_with_spec, client):
    """Dashboard page includes the Portfolio Readiness widget."""
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Portfolio Readiness" in resp.data
    assert b"recommendations" in resp.data
