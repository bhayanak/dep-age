import json

from dep_age.models import CVE, Dependency, Ecosystem, Urgency
from dep_age.output.badge import render_badge
from dep_age.output.csv_output import render_csv
from dep_age.output.json_output import render_json
from dep_age.output.markdown_output import render_markdown
from dep_age.scoring.summary import HealthSummary


def _sample_deps():
    return [
        Dependency(
            name="lodash",
            ecosystem=Ecosystem.NPM,
            current_version="4.17.15",
            latest_version="4.17.21",
            age_days=800,
            cve_count=1,
            cves=[
                CVE(
                    id="CVE-1",
                    severity="HIGH",
                    summary="proto pollution",
                    fixed_version="4.17.21",
                    url="https://example.com",
                ),
            ],
            urgency=Urgency.HIGH,
        ),
        Dependency(
            name="requests",
            ecosystem=Ecosystem.PIP,
            current_version="2.31.0",
            latest_version="2.32.3",
            age_days=200,
            urgency=Urgency.LOW,
        ),
    ]


def _sample_summary():
    return HealthSummary(
        total=2,
        fresh=1,
        aging=1,
        stale=0,
        with_cves=1,
        critical_cves=1,
        moderate_cves=0,
        score=72,
    )


class TestJsonOutput:
    def test_render_json(self):
        text = render_json(_sample_deps(), _sample_summary())
        data = json.loads(text)
        assert data["summary"]["score"] == 72
        assert len(data["dependencies"]) == 2
        assert data["dependencies"][0]["name"] == "lodash"

    def test_render_json_to_file(self, tmp_path):
        out = str(tmp_path / "deps.json")
        render_json(_sample_deps(), _sample_summary(), output_file=out)
        data = json.loads((tmp_path / "deps.json").read_text())
        assert data["summary"]["total"] == 2


class TestMarkdownOutput:
    def test_render_markdown(self):
        text = render_markdown(_sample_deps(), _sample_summary())
        assert "# Dependency Health Report" in text
        assert "lodash" in text
        assert "requests" in text
        assert "72/100" in text

    def test_render_markdown_to_file(self, tmp_path):
        out = str(tmp_path / "deps.md")
        render_markdown(_sample_deps(), _sample_summary(), output_file=out)
        assert (tmp_path / "deps.md").exists()


class TestCsvOutput:
    def test_render_csv(self):
        text = render_csv(_sample_deps())
        lines = text.strip().split("\n")
        assert len(lines) == 3  # header + 2 deps
        assert "lodash" in lines[1]

    def test_render_csv_to_file(self, tmp_path):
        out = str(tmp_path / "deps.csv")
        render_csv(_sample_deps(), output_file=out)
        assert (tmp_path / "deps.csv").exists()


class TestBadge:
    def test_render_badge(self):
        svg = render_badge(_sample_summary())
        assert "<svg" in svg
        assert "deps" in svg
        assert "fresh" in svg

    def test_render_badge_to_file(self, tmp_path):
        out = str(tmp_path / "badge.svg")
        render_badge(_sample_summary(), output_file=out)
        assert (tmp_path / "badge.svg").exists()
