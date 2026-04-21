from dep_age.models import CVE, Dependency, Ecosystem
from dep_age.scoring.summary import compute_health


class TestHealthSummary:
    def test_empty_deps(self):
        summary = compute_health([])
        assert summary.score == 100
        assert summary.total == 0

    def test_all_fresh(self):
        deps = [
            Dependency(name="a", ecosystem=Ecosystem.NPM, current_version="1.0.0", age_days=30),
            Dependency(name="b", ecosystem=Ecosystem.NPM, current_version="1.0.0", age_days=60),
        ]
        summary = compute_health(deps)
        assert summary.fresh == 2
        assert summary.stale == 0
        assert summary.score >= 85

    def test_mixed_ages(self):
        deps = [
            Dependency(
                name="fresh",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                age_days=30,
            ),
            Dependency(
                name="aging",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                age_days=400,
            ),
            Dependency(
                name="stale",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                age_days=800,
            ),
        ]
        summary = compute_health(deps)
        assert summary.fresh == 1
        assert summary.aging == 1
        assert summary.stale == 1
        assert summary.total == 3

    def test_cves_impact_score(self):
        deps = [
            Dependency(
                name="vuln",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                age_days=100,
                cve_count=2,
                cves=[
                    CVE(id="CVE-1", severity="CRITICAL", summary="", fixed_version=None, url=""),
                    CVE(id="CVE-2", severity="MEDIUM", summary="", fixed_version=None, url=""),
                ],
            ),
        ]
        summary = compute_health(deps)
        assert summary.with_cves == 1
        assert summary.critical_cves == 1
        assert summary.moderate_cves == 1
        assert summary.score < 100
