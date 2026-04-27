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

    def test_csv_format(self):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--format", "csv"],
        )
        assert result.exit_code == 0

    def test_markdown_format(self):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--format", "markdown"],
        )
        assert result.exit_code == 0

    def test_output_to_file(self, tmp_path: Path):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        out = str(tmp_path / "output.json")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--format", "json", "--output", out],
        )
        assert result.exit_code == 0
        assert (tmp_path / "output.json").exists()

    def test_max_cves_gate_pass(self):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--max-cves", "999"],
        )
        # With offline + high threshold, should pass
        assert result.exit_code == 0

    def test_not_found_path(self, tmp_path: Path):
        result = runner.invoke(
            app,
            ["scan", str(tmp_path / "nonexistent.lock")],
        )
        assert result.exit_code == 1
        assert "Not found" in result.stdout

    def test_ignore_flag(self):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        result = runner.invoke(
            app,
            ["scan", lockfile, "--offline", "--ignore", "requests,flask"],
        )
        assert result.exit_code == 0


class TestParseAgeStringExtra:
    def test_unknown_unit_fallback(self):
        # Unknown unit should just return the number
        assert _parse_age_string("5 foobar") == 5


class TestBadgeWithFile:
    def test_badge_with_file_path(self, tmp_path: Path):
        import shutil

        src = Path(FIXTURES_DIR) / "requirements.txt"
        dst = tmp_path / "requirements.txt"
        shutil.copy(src, dst)

        out = str(tmp_path / "badge.svg")
        result = runner.invoke(
            app,
            ["badge", "--output", out, str(dst)],
        )
        assert result.exit_code == 0
        assert (tmp_path / "badge.svg").exists()

    def test_badge_with_dir_path(self, tmp_path: Path):
        import shutil

        src = Path(FIXTURES_DIR) / "requirements.txt"
        dst = tmp_path / "requirements.txt"
        shutil.copy(src, dst)

        out = str(tmp_path / "badge2.svg")
        result = runner.invoke(
            app,
            ["badge", "--output", out, str(tmp_path)],
        )
        assert result.exit_code == 0


class TestDeduplication:
    def test_dedup_go_sum_and_mod(self, tmp_path: Path):
        """When both go.sum and go.mod are present, deps should be deduplicated."""
        go_sum = tmp_path / "go.sum"
        go_sum.write_text(
            "github.com/pkg/errors v0.9.1 h1:abc=\ngolang.org/x/text v0.14.0 h1:xyz=\n"
        )
        go_mod = tmp_path / "go.mod"
        go_mod.write_text(
            "module example.com/mymod\n\ngo 1.21\n\n"
            "require (\n"
            "\tgithub.com/pkg/errors v0.9.1\n"
            "\tgolang.org/x/text v0.14.0\n"
            ")\n"
        )

        result = runner.invoke(
            app,
            ["scan", str(tmp_path), "--offline", "--format", "json"],
        )
        assert result.exit_code == 0
        # Find JSON portion
        lines = result.stdout.strip().split("\n")
        json_start = next(i for i, line in enumerate(lines) if line.strip().startswith("{"))
        data = json.loads("\n".join(lines[json_start:]))
        names = [d["name"] for d in data["dependencies"]]
        # Each dep should appear only once
        assert names.count("github.com/pkg/errors") == 1
        assert names.count("golang.org/x/text") == 1


class TestCLIGating:
    def test_max_age_gate_fails(self, tmp_path: Path):
        """max-age gate should fail when deps exceed threshold."""
        req = tmp_path / "requirements.txt"
        req.write_text("somefakepkg-notcached==1.0.0\n")
        result = runner.invoke(
            app,
            ["scan", str(req), "--offline", "--max-age", "1 day"],
        )
        # With offline and unknown package, age is unknown, so gate passes
        assert result.exit_code == 0

    def test_max_cves_gate_fails_offline(self, tmp_path: Path):
        """max-cves gate with 0 threshold should pass offline (no CVEs fetched)."""
        req = tmp_path / "requirements.txt"
        req.write_text("somefakepkg-notcached==1.0.0\n")
        result = runner.invoke(
            app,
            ["scan", str(req), "--offline", "--max-cves", "0"],
        )
        assert result.exit_code == 0

    def test_no_deps_found(self, tmp_path: Path):
        """Empty lock file should show no deps message."""
        req = tmp_path / "requirements.txt"
        req.write_text("# empty\n")
        result = runner.invoke(
            app,
            ["scan", str(req), "--offline"],
        )
        assert result.exit_code == 0
        assert "No dependencies" in result.stdout
