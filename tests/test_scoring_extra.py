"""Extra tests for urgency scoring edge cases."""

from dep_age.models import CVE, Dependency, Ecosystem, Urgency
from dep_age.scoring.urgency import calculate_urgency


class TestUrgencyEdgeCases:
    def test_medium_urgency(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
        )
        dep.cves = [
            CVE(
                id="CVE-1",
                severity="MEDIUM",
                summary="test",
                fixed_version="2.0.0",
                url="",
            ),
        ]
        dep.age_days = 200
        dep.latest_version = "2.0.0"
        result = calculate_urgency(dep)
        # MEDIUM CVE (10) + aging (5) + outdated (5) = 20 → HIGH
        assert result.urgency == Urgency.HIGH

    def test_low_severity_cve(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
        )
        dep.cves = [
            CVE(
                id="CVE-1",
                severity="LOW",
                summary="test",
                fixed_version="2.0.0",
                url="",
            ),
        ]
        dep.age_days = 100
        dep.latest_version = "2.0.0"
        result = calculate_urgency(dep)
        assert result.urgency == Urgency.MEDIUM

    def test_stale_no_cves(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
        )
        dep.age_days = 900
        dep.latest_version = "2.0.0"
        result = calculate_urgency(dep)
        assert result.urgency in (Urgency.HIGH, Urgency.MEDIUM)
