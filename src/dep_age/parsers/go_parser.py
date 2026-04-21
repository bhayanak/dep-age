from __future__ import annotations

import re
from pathlib import Path

from dep_age.models import Dependency, Ecosystem
from dep_age.parsers.base import BaseParser


class GoParser(BaseParser):
    ecosystem = Ecosystem.GO
    lock_filenames = ["go.sum", "go.mod"]

    def parse(self, path: Path) -> list[Dependency]:
        if path.name == "go.sum":
            return self._parse_go_sum(path)
        if path.name == "go.mod":
            return self._parse_go_mod(path)
        return []

    def _parse_go_sum(self, path: Path) -> list[Dependency]:
        text = path.read_text(encoding="utf-8")
        deps: list[Dependency] = []
        seen: set[str] = set()

        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: module version hash
            # e.g.: github.com/pkg/errors v0.9.1 h1:abc123=
            match = re.match(r"^(\S+)\s+(v\S+?)(/go\.mod)?\s+\S+=\s*$", line)
            if match:
                module = match.group(1)
                version = match.group(2)
                # Strip +incompatible suffix
                version = version.split("+")[0]
                if module not in seen:
                    seen.add(module)
                    deps.append(
                        Dependency(
                            name=module,
                            ecosystem=Ecosystem.GO,
                            current_version=version,
                        )
                    )
        return deps

    def _parse_go_mod(self, path: Path) -> list[Dependency]:
        text = path.read_text(encoding="utf-8")
        deps: list[Dependency] = []
        seen: set[str] = set()
        in_require = False

        for line in text.splitlines():
            stripped = line.strip()

            # Single-line require: require github.com/pkg/errors v0.9.1
            single = re.match(r"^require\s+(\S+)\s+(v\S+)", stripped)
            if single:
                module, version = single.group(1), single.group(2).split("+")[0]
                if module not in seen:
                    seen.add(module)
                    deps.append(
                        Dependency(name=module, ecosystem=Ecosystem.GO, current_version=version)
                    )
                continue

            if stripped == "require (":
                in_require = True
                continue
            if stripped == ")":
                in_require = False
                continue

            if in_require:
                # Lines inside require (...) block: module version [// indirect]
                match = re.match(r"^(\S+)\s+(v\S+)", stripped)
                if match:
                    module, version = match.group(1), match.group(2).split("+")[0]
                    if module not in seen:
                        seen.add(module)
                        deps.append(
                            Dependency(
                                name=module,
                                ecosystem=Ecosystem.GO,
                                current_version=version,
                            )
                        )
        return deps
