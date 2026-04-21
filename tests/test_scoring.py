from dep_age.models import CVE, Dependency, Ecosystem, Urgency
from dep_age.scoring.urgency import calculate_all_urgencies, calculate_urgency


class TestUrgencyScoring:
    def test_no_issues(self):
        dep = Dependency(name="test", ecosystem=Ecosystem.NPM, current_version="1.0.0")
        dep.latest_version = "1.0.0"
        dep.age_days = 30
        result = calculate_urgency(dep)
        assert result.urgency == Urgency.NONE

    def test_outdated_only(self):
        dep = Dependency(name="test", ecosystem=Ecosystem.NPM, current_version="1.0.0")
        dep.latest_version = "2.0.0"
        dep.age_days = 100
        result = calculate_urgency(dep)
        assert result.urgency == Urgency.LOW

    def test_high_urgency_with_cves(self):
        dep = Dependency(name="test", ecosystem=Ecosystem.NPM, current_version="1.0.0")
        dep.cves = [
            CVE(id="CVE-1", severity="HIGH", summary="test", fixed_version="2.0.0", url=""),
        ]
        dep.age_days = 800
        result = calculate_urgency(dep)
        assert result.urgency in (Urgency.HIGH, Urgency.CRITICAL)

    def test_critical_urgency(self):
        dep = Dependency(name="test", ecosystem=Ecosystem.NPM, current_version="1.0.0")
        dep.cves = [
            CVE(id="CVE-1", severity="CRITICAL", summary="test", fixed_version="2.0.0", url=""),
            CVE(id="CVE-2", severity="HIGH", summary="test2", fixed_version="2.0.0", url=""),
        ]
        dep.age_days = 1000
        dep.latest_version = "2.0.0"
        result = calculate_urgency(dep)
        assert result.urgency == Urgency.CRITICAL

    def test_calculate_all(self):
        deps = [
            Dependency(
                name="a",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                age_days=30,
                latest_version="1.0.0",
            ),
            Dependency(
                name="b",
                ecosystem=Ecosystem.NPM,
                current_version="1.0.0",
                age_days=800,
                latest_version="2.0.0",
            ),
        ]
        results = calculate_all_urgencies(deps)
        assert len(results) == 2
        assert results[0].urgency == Urgency.NONE
