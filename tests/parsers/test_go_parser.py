from pathlib import Path

from dep_age.models import Ecosystem
from dep_age.parsers.go_parser import GoParser


class TestGoParser:
    def test_parse_go_sum(self, fixtures_dir: Path):
        parser = GoParser()
        deps = parser.parse(fixtures_dir / "go.sum")
        names = {d.name for d in deps}
        assert "github.com/pkg/errors" in names
        assert "golang.org/x/text" in names
        assert "github.com/stretchr/testify" in names

    def test_versions(self, fixtures_dir: Path):
        parser = GoParser()
        deps = parser.parse(fixtures_dir / "go.sum")
        by_name = {d.name: d for d in deps}
        assert by_name["github.com/pkg/errors"].current_version == "v0.9.1"
        assert by_name["golang.org/x/text"].current_version == "v0.14.0"

    def test_no_duplicates(self, fixtures_dir: Path):
        parser = GoParser()
        deps = parser.parse(fixtures_dir / "go.sum")
        names = [d.name for d in deps]
        assert len(names) == len(set(names))

    def test_ecosystem(self, fixtures_dir: Path):
        parser = GoParser()
        deps = parser.parse(fixtures_dir / "go.sum")
        for dep in deps:
            assert dep.ecosystem == Ecosystem.GO
