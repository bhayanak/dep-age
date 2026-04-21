from pathlib import Path

from dep_age.models import Ecosystem
from dep_age.parsers.composer_parser import ComposerParser


class TestComposerParser:
    def test_parse_composer_lock(self, fixtures_dir: Path):
        parser = ComposerParser()
        deps = parser.parse(fixtures_dir / "composer.lock")
        assert len(deps) == 3
        names = {d.name for d in deps}
        assert "monolog/monolog" in names
        assert "symfony/console" in names
        assert "phpunit/phpunit" in names

    def test_versions(self, fixtures_dir: Path):
        parser = ComposerParser()
        deps = parser.parse(fixtures_dir / "composer.lock")
        by_name = {d.name: d for d in deps}
        assert by_name["monolog/monolog"].current_version == "3.5.0"
        assert by_name["symfony/console"].current_version == "6.4.1"

    def test_direct_flag(self, fixtures_dir: Path):
        parser = ComposerParser()
        deps = parser.parse(fixtures_dir / "composer.lock")
        by_name = {d.name: d for d in deps}
        assert by_name["monolog/monolog"].is_direct is True
        assert by_name["phpunit/phpunit"].is_direct is False

    def test_ecosystem(self, fixtures_dir: Path):
        parser = ComposerParser()
        deps = parser.parse(fixtures_dir / "composer.lock")
        for dep in deps:
            assert dep.ecosystem == Ecosystem.COMPOSER
