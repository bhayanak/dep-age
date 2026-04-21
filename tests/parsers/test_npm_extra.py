"""Extra tests for npm parser: pnpm-lock.yaml and edge cases."""

from pathlib import Path

import yaml

from dep_age.parsers.npm_parser import NpmParser


class TestPnpmLock:
    def test_parse_pnpm_lock(self, tmp_path: Path):
        data = {
            "lockfileVersion": "6.0",
            "packages": {
                "/lodash@4.17.21": {},
                "/express@4.18.2": {},
                "/@types/node@20.10.0": {},
            },
        }
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(yaml.dump(data))

        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 3
        names = {d.name for d in deps}
        assert "lodash" in names
        assert "express" in names
        assert "@types/node" in names

    def test_pnpm_scoped_package(self, tmp_path: Path):
        data = {
            "packages": {
                "/@scope/pkg@1.0.0": {},
            },
        }
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(yaml.dump(data))

        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 1
        assert deps[0].name == "@scope/pkg"
        assert deps[0].current_version == "1.0.0"

    def test_pnpm_empty(self, tmp_path: Path):
        data = {"packages": {}}
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(yaml.dump(data))

        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 0


class TestPackageLockV1:
    def test_parse_v1_format(self, tmp_path: Path):
        import json

        data = {
            "name": "test",
            "version": "1.0.0",
            "lockfileVersion": 1,
            "dependencies": {
                "lodash": {"version": "4.17.21"},
                "express": {"version": "4.18.2"},
            },
        }
        lockfile = tmp_path / "package-lock.json"
        lockfile.write_text(json.dumps(data))

        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 2
        names = {d.name for d in deps}
        assert "lodash" in names
        assert "express" in names


class TestYarnLockEdgeCases:
    def test_yarn_duplicate_name(self, tmp_path: Path):
        content = """\
"lodash@^4.17.0":
  version "4.17.21"

"lodash@^4.17.15":
  version "4.17.21"
"""
        lockfile = tmp_path / "yarn.lock"
        lockfile.write_text(content)
        parser = NpmParser()
        deps = parser.parse(lockfile)
        # Should dedup
        assert len(deps) == 1


class TestPnpmEdgeCases:
    def test_pnpm_no_at_symbol(self, tmp_path: Path):
        data = {"packages": {"no-version-key": {}}}
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(yaml.dump(data))
        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 0

    def test_pnpm_scoped_too_few_parts(self, tmp_path: Path):
        data = {"packages": {"/@only-scope": {}}}
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(yaml.dump(data))
        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 0

    def test_pnpm_unscoped_no_version(self, tmp_path: Path):
        data = {"packages": {"/pkg-no-at": {}}}
        lockfile = tmp_path / "pnpm-lock.yaml"
        lockfile.write_text(yaml.dump(data))
        parser = NpmParser()
        deps = parser.parse(lockfile)
        assert len(deps) == 0
