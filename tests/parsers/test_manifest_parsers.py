"""Tests for manifest file parsing: package.json, Cargo.toml, go.mod, composer.json."""

import json
from pathlib import Path

from dep_age.parsers.cargo_parser import CargoParser
from dep_age.parsers.composer_parser import ComposerParser
from dep_age.parsers.go_parser import GoParser
from dep_age.parsers.npm_parser import NpmParser


class TestPackageJson:
    def test_parse_basic(self, tmp_path: Path):
        data = {
            "name": "my-app",
            "dependencies": {"lodash": "^4.17.21", "express": "~4.18.0"},
            "devDependencies": {"jest": "^29.0.0"},
        }
        f = tmp_path / "package.json"
        f.write_text(json.dumps(data))
        parser = NpmParser()
        deps = parser.parse(f)
        assert len(deps) == 3
        by_name = {d.name: d for d in deps}
        assert by_name["lodash"].current_version == "4.17.21"
        assert by_name["express"].current_version == "4.18.0"
        assert by_name["jest"].current_version == "29.0.0"
        assert by_name["lodash"].is_direct is True
        assert by_name["jest"].is_direct is False

    def test_empty_deps(self, tmp_path: Path):
        f = tmp_path / "package.json"
        f.write_text(json.dumps({"name": "empty"}))
        parser = NpmParser()
        deps = parser.parse(f)
        assert len(deps) == 0

    def test_wildcard_version(self, tmp_path: Path):
        f = tmp_path / "package.json"
        f.write_text(json.dumps({"dependencies": {"pkg": "*"}}))
        parser = NpmParser()
        deps = parser.parse(f)
        assert len(deps) == 1
        assert deps[0].current_version == "*"

    def test_dedup(self, tmp_path: Path):
        data = {
            "dependencies": {"lodash": "^4.17.21"},
            "devDependencies": {"lodash": "^4.17.21"},
        }
        f = tmp_path / "package.json"
        f.write_text(json.dumps(data))
        parser = NpmParser()
        deps = parser.parse(f)
        assert len(deps) == 1

    def test_can_handle(self):
        parser = NpmParser()
        assert parser.can_handle(Path("package.json"))

    def test_unknown_file_returns_empty(self):
        import tempfile

        parser = NpmParser()
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            assert parser.parse(Path(f.name)) == []


class TestCargoToml:
    def test_parse_basic(self, tmp_path: Path):
        content = """\
[package]
name = "my-crate"
version = "0.1.0"

[dependencies]
serde = "1.0"
tokio = { version = "1.35", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
"""
        f = tmp_path / "Cargo.toml"
        f.write_text(content)
        parser = CargoParser()
        deps = parser.parse(f)
        assert len(deps) == 3
        by_name = {d.name: d for d in deps}
        assert by_name["serde"].current_version == "1.0"
        assert by_name["tokio"].current_version == "1.35"
        assert by_name["criterion"].current_version == "0.5"
        assert by_name["serde"].is_direct is True
        assert by_name["criterion"].is_direct is False

    def test_empty(self, tmp_path: Path):
        f = tmp_path / "Cargo.toml"
        f.write_text("[package]\nname = 'empty'\nversion = '0.1.0'\n")
        parser = CargoParser()
        deps = parser.parse(f)
        assert len(deps) == 0

    def test_build_dependencies(self, tmp_path: Path):
        content = """\
[build-dependencies]
cc = "1.0"
"""
        f = tmp_path / "Cargo.toml"
        f.write_text(content)
        parser = CargoParser()
        deps = parser.parse(f)
        assert len(deps) == 1
        assert deps[0].name == "cc"

    def test_can_handle(self):
        parser = CargoParser()
        assert parser.can_handle(Path("Cargo.toml"))

    def test_version_with_caret(self, tmp_path: Path):
        content = """\
[dependencies]
serde = "^1.0.193"
"""
        f = tmp_path / "Cargo.toml"
        f.write_text(content)
        parser = CargoParser()
        deps = parser.parse(f)
        assert deps[0].current_version == "1.0.193"


class TestGoMod:
    def test_parse_require_block(self, tmp_path: Path):
        content = """\
module github.com/example/project

go 1.21

require (
\tgithub.com/pkg/errors v0.9.1
\tgolang.org/x/text v0.14.0
\tgithub.com/stretchr/testify v1.8.4 // indirect
)
"""
        f = tmp_path / "go.mod"
        f.write_text(content)
        parser = GoParser()
        deps = parser.parse(f)
        assert len(deps) == 3
        by_name = {d.name: d for d in deps}
        assert by_name["github.com/pkg/errors"].current_version == "v0.9.1"
        assert by_name["golang.org/x/text"].current_version == "v0.14.0"
        assert by_name["github.com/stretchr/testify"].current_version == "v1.8.4"

    def test_parse_single_require(self, tmp_path: Path):
        content = """\
module example.com/pkg

go 1.20

require github.com/pkg/errors v0.9.1
"""
        f = tmp_path / "go.mod"
        f.write_text(content)
        parser = GoParser()
        deps = parser.parse(f)
        assert len(deps) == 1
        assert deps[0].current_version == "v0.9.1"

    def test_empty(self, tmp_path: Path):
        f = tmp_path / "go.mod"
        f.write_text("module example.com/pkg\n\ngo 1.21\n")
        parser = GoParser()
        deps = parser.parse(f)
        assert len(deps) == 0

    def test_can_handle(self):
        parser = GoParser()
        assert parser.can_handle(Path("go.mod"))


class TestComposerJson:
    def test_parse_basic(self, tmp_path: Path):
        data = {
            "name": "vendor/project",
            "require": {"php": ">=8.1", "monolog/monolog": "^3.5", "symfony/console": "^6.4"},
            "require-dev": {"phpunit/phpunit": "^10.0"},
        }
        f = tmp_path / "composer.json"
        f.write_text(json.dumps(data))
        parser = ComposerParser()
        deps = parser.parse(f)
        # php should be skipped
        assert len(deps) == 3
        names = {d.name for d in deps}
        assert "php" not in names
        assert "monolog/monolog" in names
        assert "phpunit/phpunit" in names
        by_name = {d.name: d for d in deps}
        assert by_name["monolog/monolog"].is_direct is True
        assert by_name["phpunit/phpunit"].is_direct is False

    def test_skip_ext(self, tmp_path: Path):
        data = {"require": {"ext-json": "*", "ext-mbstring": "*", "real/package": "^1.0"}}
        f = tmp_path / "composer.json"
        f.write_text(json.dumps(data))
        parser = ComposerParser()
        deps = parser.parse(f)
        assert len(deps) == 1
        assert deps[0].name == "real/package"

    def test_empty(self, tmp_path: Path):
        f = tmp_path / "composer.json"
        f.write_text(json.dumps({"name": "vendor/empty"}))
        parser = ComposerParser()
        deps = parser.parse(f)
        assert len(deps) == 0

    def test_can_handle(self):
        parser = ComposerParser()
        assert parser.can_handle(Path("composer.json"))

    def test_unknown_file_returns_empty(self):
        import tempfile

        parser = ComposerParser()
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            assert parser.parse(Path(f.name)) == []
