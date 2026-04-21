import os

from typer.testing import CliRunner

from dep_age.cli import app

runner = CliRunner()

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class TestCLI:
    def test_version(self):
        result = runner.invoke(app, ["scan", "--version"])
        assert result.exit_code == 0
        assert "dep-age" in result.stdout

    def test_scan_fixtures_dir(self):
        result = runner.invoke(app, ["scan", FIXTURES_DIR, "--offline"])
        # Should find lock files and parse deps
        assert result.exit_code == 0

    def test_scan_specific_file(self):
        lockfile = os.path.join(FIXTURES_DIR, "package-lock.json")
        result = runner.invoke(app, ["scan", lockfile, "--offline"])
        assert result.exit_code == 0

    def test_scan_json_format(self):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        result = runner.invoke(app, ["scan", lockfile, "--offline", "--format", "json"])
        assert result.exit_code == 0
        assert '"dependencies"' in result.stdout

    def test_scan_csv_format(self):
        lockfile = os.path.join(FIXTURES_DIR, "Cargo.lock")
        result = runner.invoke(app, ["scan", lockfile, "--offline", "--format", "csv"])
        assert result.exit_code == 0
        assert "name," in result.stdout

    def test_scan_markdown_format(self):
        lockfile = os.path.join(FIXTURES_DIR, "Gemfile.lock")
        result = runner.invoke(app, ["scan", lockfile, "--offline", "--format", "markdown"])
        assert result.exit_code == 0
        assert "# Dependency Health Report" in result.stdout

    def test_scan_not_found(self):
        result = runner.invoke(app, ["scan", "/nonexistent/file.lock"])
        assert result.exit_code == 1

    def test_scan_ignore_packages(self):
        lockfile = os.path.join(FIXTURES_DIR, "package-lock.json")
        result = runner.invoke(
            app, ["scan", lockfile, "--offline", "--format", "json", "--ignore", "lodash,express"]
        )
        assert result.exit_code == 0
        assert "lodash" not in result.stdout

    def test_scan_max_cves_gate(self):
        lockfile = os.path.join(FIXTURES_DIR, "package-lock.json")
        # With --offline, no CVEs should be found, so max-cves=0 should pass
        result = runner.invoke(app, ["scan", lockfile, "--offline", "--max-cves", "0"])
        assert result.exit_code == 0

    def test_scan_no_lockfiles_dir(self, tmp_path):
        result = runner.invoke(app, ["scan", str(tmp_path)])
        assert result.exit_code == 0
        assert "No lock files found" in result.stdout

    def test_scan_output_file(self, tmp_path):
        lockfile = os.path.join(FIXTURES_DIR, "requirements.txt")
        out = str(tmp_path / "output.json")
        result = runner.invoke(
            app, ["scan", lockfile, "--offline", "--format", "json", "--output", out]
        )
        assert result.exit_code == 0
        assert (tmp_path / "output.json").exists()
