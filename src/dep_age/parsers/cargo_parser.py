from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):  # pragma: no cover
    import tomllib
else:  # pragma: no cover
    try:
        import tomllib  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]

from dep_age.models import Dependency, Ecosystem
from dep_age.parsers.base import BaseParser


class CargoParser(BaseParser):
    ecosystem = Ecosystem.CARGO
    lock_filenames = ["Cargo.lock", "Cargo.toml"]

    def parse(self, path: Path) -> list[Dependency]:
        if path.name == "Cargo.lock":
            return self._parse_cargo_lock(path)
        if path.name == "Cargo.toml":
            return self._parse_cargo_toml(path)
        return []

    def _parse_cargo_lock(self, path: Path) -> list[Dependency]:
        text = path.read_text(encoding="utf-8")
        deps: list[Dependency] = []
        seen: set[str] = set()
        current_name: str | None = None
        current_version: str | None = None

        for line in text.splitlines():
            line = line.strip()
            if line == "[[package]]":
                if current_name and current_version and current_name not in seen:
                    seen.add(current_name)
                    deps.append(
                        Dependency(
                            name=current_name,
                            ecosystem=Ecosystem.CARGO,
                            current_version=current_version,
                        )
                    )
                current_name = None
                current_version = None
            elif line.startswith("name = "):
                current_name = line.split("=", 1)[1].strip().strip('"')
            elif line.startswith("version = "):
                current_version = line.split("=", 1)[1].strip().strip('"')

        # Last block
        if current_name and current_version and current_name not in seen:
            seen.add(current_name)
            deps.append(
                Dependency(
                    name=current_name,
                    ecosystem=Ecosystem.CARGO,
                    current_version=current_version,
                )
            )
        return deps

    def _parse_cargo_toml(self, path: Path) -> list[Dependency]:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        for section in ("dependencies", "dev-dependencies", "build-dependencies"):
            packages = data.get(section, {})
            for name, spec in packages.items():
                if name in seen:
                    continue
                seen.add(name)
                if isinstance(spec, str):
                    raw_constraint = spec
                    version = re.sub(r"^[\^~>=<*= ]+", "", spec).split(",")[0].strip()
                elif isinstance(spec, dict):
                    raw_constraint = spec.get("version", "")
                    version = re.sub(r"^[\^~>=<*= ]+", "", raw_constraint).split(",")[0].strip()
                else:
                    continue
                if version:
                    has_constraint = raw_constraint != version
                    deps.append(
                        Dependency(
                            name=name,
                            ecosystem=Ecosystem.CARGO,
                            current_version=version,
                            is_direct=section == "dependencies",
                            version_constraint=raw_constraint if has_constraint else None,
                        )
                    )
        return deps
