from __future__ import annotations

import re
from pathlib import Path

from dep_age.models import Dependency, Ecosystem
from dep_age.parsers.base import BaseParser


class GemParser(BaseParser):
    ecosystem = Ecosystem.GEM
    lock_filenames = ["Gemfile.lock"]

    def parse(self, path: Path) -> list[Dependency]:
        text = path.read_text(encoding="utf-8")
        deps: list[Dependency] = []
        seen: set[str] = set()
        in_specs = False

        for line in text.splitlines():
            if line.strip() == "GEM":
                continue
            if line.strip() == "specs:":
                in_specs = True
                continue
            if in_specs:
                # Gem entries are indented with spaces: "    gem_name (1.2.3)"
                match = re.match(r"^\s{4}(\S+)\s+\(([^)]+)\)", line)
                if match:
                    name = match.group(1)
                    version = match.group(2)
                    if name not in seen:
                        seen.add(name)
                        deps.append(
                            Dependency(
                                name=name,
                                ecosystem=Ecosystem.GEM,
                                current_version=version,
                            )
                        )
                elif line and not line.startswith(" " * 4):
                    # Left a specs block
                    in_specs = line.strip() == "specs:"
        return deps
