"""Extended CLI tests for better coverage."""

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from dep_age.cli import _parse_age_string, app

runner = CliRunner()
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestParseAgeString:
    def test_years(self):
        assert _parse_age_string("2 years") == 730

    def test_months(self):
        assert _parse_age_string("6 months") == 180

    def test_weeks(self):
        assert _parse_age_string("4 weeks") == 28

    def test_days(self):
        assert _parse_age_string("30 days") == 30

    def test_plain_number(self):
        assert _parse_age_string("365") == 365

    def test_singular(self):
        assert _parse_age_string("1 year") == 365
        assert _parse_age_string("1 month") == 30


class TestCLIBadge:
    def test_badge_no_lockfiles(self, tmp_path: Path):
        result = runner.invoke(
            app,
            ["badge", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "No lock files found" in result.stdout

    def test_badge_with_fixtures(self, tmp_path: Path):
        # Copy a fixture to tmp
        import shutil

        src = Path(FIXTURES_DIR) / "requirements.txt"
        dst = tmp_path / "requirements.txt"
        shutil.copy(src, dst)

        out = str(tmp_path / "badge.svg")
        result = runner.invoke(
            app,
            ["badge", "--output", out, str(tmp_path)],
        )
        assert result.exit_code == 0
        assert (tmp_path / "badge.svg").exists()


class TestCLIOutputFormats:
    def test_terminal_format(self):
        lockfile = os.path.join(FIXTURES_DIR, "Cargo.lock")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--format", "terminal"],
        )
        assert result.exit_code == 0

    def test_json_output_structure(self):
        lockfile = os.path.join(FIXTURES_DIR, "package-lock.json")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--format", "json"],
        )
        assert result.exit_code == 0
        # Find the JSON portion in the output
        lines = result.stdout.strip().split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None
        data = json.loads("\n".join(lines[json_start:]))
        assert "summary" in data
        assert "dependencies" in data

    def test_older_than_filter(self):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        result = runner.invoke(
            app,
            [
                "scan",
                lockfile,
                "--offline",
                "--format",
                "json",
                "--older-than",
                "100 years",
            ],
        )
        assert result.exit_code == 0

    def test_max_age_gate_pass(self):
        lockfile = os.path.join(FIXTURES_DIR, "Cargo.lock")
        result = runner.invoke(
            app,
            [
                "scan",
                lockfile,
                "--offline",
                "--max-age",
                "100 years",
            ],
        )
        assert result.exit_code == 0

    def test_outdated_flag(self):
        lockfile = os.path.join(FIXTURES_DIR, "Gemfile.lock")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--outdated"],
        )
        assert result.exit_code == 0

    def test_cves_only_flag(self):
        lockfile = os.path.join(FIXTURES_DIR, "go.sum")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--cves-only"],
        )
        assert result.exit_code == 0
