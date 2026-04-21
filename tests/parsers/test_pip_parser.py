from pathlib import Path

from dep_age.models import Ecosystem
from dep_age.parsers.pip_parser import PipParser


class TestPipParserRequirements:
    def test_parse_requirements(self, fixtures_dir: Path):
        parser = PipParser()
        deps = parser.parse(fixtures_dir / "requirements.txt")
        names = {d.name for d in deps}
        assert "requests" in names
        assert "flask" in names
        assert "numpy" in names
        assert "django" in names
        # -e lines should be skipped
        assert "pkg" not in names

    def test_versions(self, fixtures_dir: Path):
        parser = PipParser()
        deps = parser.parse(fixtures_dir / "requirements.txt")
        by_name = {d.name: d for d in deps}
        assert by_name["requests"].current_version == "2.31.0"
        assert by_name["flask"].current_version == "3.0.0"
        assert by_name["numpy"].current_version == "1.24.0"

    def test_ecosystem(self, fixtures_dir: Path):
        parser = PipParser()
        deps = parser.parse(fixtures_dir / "requirements.txt")
        for dep in deps:
            assert dep.ecosystem == Ecosystem.PIP

    def test_can_handle(self):
        parser = PipParser()
        assert parser.can_handle(Path("requirements.txt"))
        assert parser.can_handle(Path("Pipfile.lock"))
        assert parser.can_handle(Path("poetry.lock"))
        assert parser.can_handle(Path("pyproject.toml"))
        assert not parser.can_handle(Path("Cargo.lock"))
