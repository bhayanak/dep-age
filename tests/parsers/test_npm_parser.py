from pathlib import Path

from dep_age.models import Ecosystem
from dep_age.parsers.npm_parser import NpmParser


class TestNpmParserPackageLock:
    def test_parse_package_lock(self, fixtures_dir: Path):
        parser = NpmParser()
        deps = parser.parse(fixtures_dir / "package-lock.json")
        assert len(deps) == 3
        names = {d.name for d in deps}
        assert "lodash" in names
        assert "express" in names
        assert "accepts" in names
        for dep in deps:
            assert dep.ecosystem == Ecosystem.NPM
            assert dep.current_version

    def test_can_handle(self):
        parser = NpmParser()
        assert parser.can_handle(Path("package-lock.json"))
        assert parser.can_handle(Path("yarn.lock"))
        assert parser.can_handle(Path("pnpm-lock.yaml"))
        assert parser.can_handle(Path("package.json"))
        assert not parser.can_handle(Path("requirements.txt"))


class TestNpmParserYarnLock:
    def test_parse_yarn_lock(self, fixtures_dir: Path):
        parser = NpmParser()
        deps = parser.parse(fixtures_dir / "yarn.lock")
        assert len(deps) == 3
        names = {d.name for d in deps}
        assert "express" in names
        assert "lodash" in names
        assert "accepts" in names
        for dep in deps:
            assert dep.ecosystem == Ecosystem.NPM

    def test_versions_extracted(self, fixtures_dir: Path):
        parser = NpmParser()
        deps = parser.parse(fixtures_dir / "yarn.lock")
        by_name = {d.name: d for d in deps}
        assert by_name["express"].current_version == "4.18.2"
        assert by_name["lodash"].current_version == "4.17.21"
