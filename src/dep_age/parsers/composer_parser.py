from __future__ import annotations

import json
import re
from pathlib import Path

from dep_age.models import Dependency, Ecosystem
from dep_age.parsers.base import BaseParser


class ComposerParser(BaseParser):
    ecosystem = Ecosystem.COMPOSER
    lock_filenames = ["composer.lock", "composer.json"]

    def parse(self, path: Path) -> list[Dependency]:
        if path.name == "composer.lock":
            return self._parse_composer_lock(path)
        if path.name == "composer.json":
            return self._parse_composer_json(path)
        return []

    def _parse_composer_lock(self, path: Path) -> list[Dependency]:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        for section in ("packages", "packages-dev"):
            for pkg in data.get(section, []):
                name = pkg.get("name", "")
                version = pkg.get("version", "").lstrip("v")
                if name and version and name not in seen:
                    seen.add(name)
                    deps.append(
                        Dependency(
                            name=name,
                            ecosystem=Ecosystem.COMPOSER,
                            current_version=version,
                            is_direct=section == "packages",
                        )
                    )
        return deps

    def _parse_composer_json(self, path: Path) -> list[Dependency]:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        for section in ("require", "require-dev"):
            packages = data.get(section, {})
            for name, version_spec in packages.items():
                # Skip php and ext-* entries
                if name == "php" or name.startswith("ext-"):
                    continue
                if name in seen:
                    continue
                seen.add(name)
                version = re.sub(r"^[\^~>=<|v* ]+", "", version_spec).split(",")[0].strip()
                deps.append(
                    Dependency(
                        name=name,
                        ecosystem=Ecosystem.COMPOSER,
                        current_version=version or "*",
                        is_direct=section == "require",
                        version_constraint=version_spec if version_spec != version else None,
                    )
                )
        return deps
