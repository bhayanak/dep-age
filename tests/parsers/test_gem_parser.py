from pathlib import Path

from dep_age.models import Ecosystem
from dep_age.parsers.gem_parser import GemParser


class TestGemParser:
    def test_parse_gemfile_lock(self, fixtures_dir: Path):
        parser = GemParser()
        deps = parser.parse(fixtures_dir / "Gemfile.lock")
        names = {d.name for d in deps}
        assert "rack" in names
        assert "rails" in names
        assert "nokogiri" in names
        assert "actionpack" in names

    def test_versions(self, fixtures_dir: Path):
        parser = GemParser()
        deps = parser.parse(fixtures_dir / "Gemfile.lock")
        by_name = {d.name: d for d in deps}
        assert by_name["rack"].current_version == "3.0.8"
        assert by_name["rails"].current_version == "7.1.2"
        assert by_name["nokogiri"].current_version == "1.15.4"

    def test_ecosystem(self, fixtures_dir: Path):
        parser = GemParser()
        deps = parser.parse(fixtures_dir / "Gemfile.lock")
        for dep in deps:
            assert dep.ecosystem == Ecosystem.GEM

    def test_can_handle(self):
        parser = GemParser()
        assert parser.can_handle(Path("Gemfile.lock"))
        assert not parser.can_handle(Path("package-lock.json"))
