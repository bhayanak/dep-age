"""Extra tests for pip parser: Pipfile.lock and poetry.lock formats."""

import json
from pathlib import Path

from dep_age.parsers.pip_parser import PipParser


class TestPipfileLock:
    def test_parse_pipfile_lock(self, tmp_path: Path):
        data = {
            "default": {
                "requests": {"version": "==2.31.0"},
                "flask": {"version": "==3.0.0"},
            },
            "develop": {
                "pytest": {"version": "==8.0.0"},
            },
        }
        lockfile = tmp_path / "Pipfile.lock"
        lockfile.write_text(json.dumps(data))

        parser = PipParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 3
        by_name = {d.name: d for d in deps}
        assert by_name["requests"].current_version == "2.31.0"
        assert by_name["requests"].is_direct is True
        assert by_name["pytest"].is_direct is False

    def test_empty_sections(self, tmp_path: Path):
        data = {"default": {}, "develop": {}}
        lockfile = tmp_path / "Pipfile.lock"
        lockfile.write_text(json.dumps(data))
        parser = PipParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 0


class TestPoetryLock:
    def test_parse_poetry_lock(self, tmp_path: Path):
        content = """[[package]]
name = "requests"
version = "2.31.0"

[[package]]
name = "flask"
version = "3.0.0"
"""
        lockfile = tmp_path / "poetry.lock"
        lockfile.write_text(content)

        parser = PipParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 2
        by_name = {d.name: d for d in deps}
        assert by_name["requests"].current_version == "2.31.0"
        assert by_name["flask"].current_version == "3.0.0"

    def test_empty_poetry_lock(self, tmp_path: Path):
        lockfile = tmp_path / "poetry.lock"
        lockfile.write_text("")
        parser = PipParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 0


class TestPyprojectToml:
    def test_parse_basic(self, tmp_path: Path):
        content = """\
[project]
name = "myproject"
dependencies = [
    "requests>=2.31,<3.0",
    "flask==3.0.0",
    "numpy~=1.24.0",
]
"""
        f = tmp_path / "pyproject.toml"
        f.write_text(content)
        parser = PipParser()
        deps = parser.parse(f)
        assert len(deps) == 3
        by_name = {d.name: d for d in deps}
        assert "requests" in by_name
        assert "flask" in by_name
        assert "numpy" in by_name
        assert by_name["flask"].current_version == "3.0.0"
        assert by_name["requests"].is_direct is True

    def test_parse_optional_dependencies(self, tmp_path: Path):
        content = """\
[project]
name = "myproject"
dependencies = ["requests>=2.31"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.4"]
docs = ["sphinx>=7.0"]
"""
        f = tmp_path / "pyproject.toml"
        f.write_text(content)
        parser = PipParser()
        deps = parser.parse(f)
        assert len(deps) == 4
        names = {d.name for d in deps}
        assert names == {"requests", "pytest", "ruff", "sphinx"}

    def test_no_version(self, tmp_path: Path):
        content = """\
[project]
dependencies = ["requests"]
"""
        f = tmp_path / "pyproject.toml"
        f.write_text(content)
        parser = PipParser()
        deps = parser.parse(f)
        assert len(deps) == 1
        assert deps[0].current_version == "*"

    def test_empty_pyproject(self, tmp_path: Path):
        f = tmp_path / "pyproject.toml"
        f.write_text("[project]\nname = 'empty'\n")
        parser = PipParser()
        deps = parser.parse(f)
        assert len(deps) == 0

    def test_deduplication_across_sections(self, tmp_path: Path):
        content = """\
[project]
dependencies = ["requests>=2.31"]

[project.optional-dependencies]
dev = ["requests>=2.31"]
"""
        f = tmp_path / "pyproject.toml"
        f.write_text(content)
        parser = PipParser()
        deps = parser.parse(f)
        assert len(deps) == 1

    def test_can_handle(self):
        parser = PipParser()
        assert parser.can_handle(Path("pyproject.toml"))
