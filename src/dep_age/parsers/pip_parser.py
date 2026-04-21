from __future__ import annotations

import json
import re
from pathlib import Path

if __import__("sys").version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:  # pragma: no cover
        import tomli as tomllib  # type: ignore[no-redef]

from dep_age.models import Dependency, Ecosystem
from dep_age.parsers.base import BaseParser


class PipParser(BaseParser):
    ecosystem = Ecosystem.PIP
    lock_filenames = ["requirements.txt", "Pipfile.lock", "poetry.lock", "pyproject.toml"]

    def parse(self, path: Path) -> list[Dependency]:
        if path.name == "requirements.txt":
            return self._parse_requirements(path)
        if path.name == "Pipfile.lock":
            return self._parse_pipfile_lock(path)
        if path.name == "poetry.lock":
            return self._parse_poetry_lock(path)
        if path.name == "pyproject.toml":
            return self._parse_pyproject_toml(path)
        return []

    def _parse_requirements(self, path: Path) -> list[Dependency]:
        deps: list[Dependency] = []
        seen: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            # Handle: package==1.0.0, package>=1.0.0, package~=1.0.0
            match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*[=~!<>]=?\s*([^\s;,#]+)", line)
            if match:
                name = match.group(1).lower()
                version = match.group(2)
                if name not in seen:
                    seen.add(name)
                    deps.append(
                        Dependency(
                            name=name,
                            ecosystem=Ecosystem.PIP,
                            current_version=version,
                        )
                    )
        return deps

    def _parse_pipfile_lock(self, path: Path) -> list[Dependency]:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        for section in ("default", "develop"):
            packages = data.get(section, {})
            for name, info in packages.items():
                version = info.get("version", "").lstrip("=")
                name_lower = name.lower()
                if name_lower in seen or not version:
                    continue
                seen.add(name_lower)
                deps.append(
                    Dependency(
                        name=name_lower,
                        ecosystem=Ecosystem.PIP,
                        current_version=version,
                        is_direct=section == "default",
                    )
                )
        return deps

    def _parse_pyproject_toml(self, path: Path) -> list[Dependency]:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        # [project.dependencies]
        for req in data.get("project", {}).get("dependencies", []):
            match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*([=~!<>]=?\s*[^\s,;]+)?", req)
            if match:
                name = match.group(1).lower()
                version = (match.group(2) or "").strip().lstrip("=~!<> ")
                if name not in seen:
                    seen.add(name)
                    deps.append(
                        Dependency(
                            name=name,
                            ecosystem=Ecosystem.PIP,
                            current_version=version or "*",
                            is_direct=True,
                        )
                    )

        # [project.optional-dependencies]
        for group_deps in data.get("project", {}).get("optional-dependencies", {}).values():
            for req in group_deps:
                match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*([=~!<>]=?\s*[^\s,;]+)?", req)
                if match:
                    name = match.group(1).lower()
                    version = (match.group(2) or "").strip().lstrip("=~!<> ")
                    if name not in seen:
                        seen.add(name)
                        deps.append(
                            Dependency(
                                name=name,
                                ecosystem=Ecosystem.PIP,
                                current_version=version or "*",
                                is_direct=True,
                            )
                        )

        return deps

    def _parse_poetry_lock(self, path: Path) -> list[Dependency]:
        deps: list[Dependency] = []
        seen: set[str] = set()
        text = path.read_text(encoding="utf-8")

        # Parse TOML-like structure: [[package]] blocks
        current_name = None
        current_version = None

        for line in text.splitlines():
            line = line.strip()
            if line == "[[package]]":
                if current_name and current_version and current_name not in seen:
                    seen.add(current_name)
                    deps.append(
                        Dependency(
                            name=current_name,
                            ecosystem=Ecosystem.PIP,
                            current_version=current_version,
                        )
                    )
                current_name = None
                current_version = None
            elif line.startswith("name = "):
                current_name = line.split("=", 1)[1].strip().strip('"').lower()
            elif line.startswith("version = "):
                current_version = line.split("=", 1)[1].strip().strip('"')

        # Don't forget the last block
        if current_name and current_version and current_name not in seen:
            seen.add(current_name)
            deps.append(
                Dependency(
                    name=current_name,
                    ecosystem=Ecosystem.PIP,
                    current_version=current_version,
                )
            )
        return deps
