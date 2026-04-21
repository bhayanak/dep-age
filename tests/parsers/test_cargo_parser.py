from pathlib import Path

from dep_age.models import Ecosystem
from dep_age.parsers.cargo_parser import CargoParser


class TestCargoParser:
    def test_parse_cargo_lock(self, fixtures_dir: Path):
        parser = CargoParser()
        deps = parser.parse(fixtures_dir / "Cargo.lock")
        assert len(deps) == 3
        names = {d.name for d in deps}
        assert "serde" in names
        assert "tokio" in names
        assert "rand" in names

    def test_versions(self, fixtures_dir: Path):
        parser = CargoParser()
        deps = parser.parse(fixtures_dir / "Cargo.lock")
        by_name = {d.name: d for d in deps}
        assert by_name["serde"].current_version == "1.0.193"
        assert by_name["tokio"].current_version == "1.35.0"
        assert by_name["rand"].current_version == "0.8.5"

    def test_ecosystem(self, fixtures_dir: Path):
        parser = CargoParser()
        deps = parser.parse(fixtures_dir / "Cargo.lock")
        for dep in deps:
            assert dep.ecosystem == Ecosystem.CARGO

    def test_can_handle(self):
        parser = CargoParser()
        assert parser.can_handle(Path("Cargo.lock"))
        assert parser.can_handle(Path("Cargo.toml"))
        assert not parser.can_handle(Path("yarn.lock"))
