from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from dep_age.models import Dependency, Ecosystem
from dep_age.parsers.base import BaseParser


class NpmParser(BaseParser):
    ecosystem = Ecosystem.NPM
    lock_filenames = ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "package.json"]

    def parse(self, path: Path) -> list[Dependency]:
        if path.name == "package-lock.json":
            return self._parse_package_lock(path)
        if path.name == "yarn.lock":
            return self._parse_yarn_lock(path)
        if path.name == "pnpm-lock.yaml":
            return self._parse_pnpm_lock(path)
        if path.name == "package.json":
            return self._parse_package_json(path)
        return []

    def _parse_package_lock(self, path: Path) -> list[Dependency]:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        # v2/v3 format: "packages" key
        packages = data.get("packages", {})
        if packages:
            for pkg_path, info in packages.items():
                if not pkg_path:  # root entry
                    continue
                name = info.get("name") or pkg_path.rsplit("node_modules/", 1)[-1]
                version = info.get("version", "")
                if not name or not version or name in seen:
                    continue
                seen.add(name)
                deps.append(
                    Dependency(
                        name=name,
                        ecosystem=Ecosystem.NPM,
                        current_version=version,
                        is_direct=not info.get("dev", False),
                    )
                )
            return deps

        # v1 format: "dependencies" key
        for name, info in data.get("dependencies", {}).items():
            version = info.get("version", "")
            if name in seen or not version:
                continue
            seen.add(name)
            deps.append(
                Dependency(
                    name=name,
                    ecosystem=Ecosystem.NPM,
                    current_version=version,
                )
            )
        return deps

    def _parse_yarn_lock(self, path: Path) -> list[Dependency]:
        text = path.read_text(encoding="utf-8")
        deps: list[Dependency] = []
        seen: set[str] = set()

        # Match patterns like: "package@^1.0.0": or package@^1.0.0:
        block_re = re.compile(r'^"?([^@\s]+)@[^"]*"?:\s*$', re.MULTILINE)
        version_re = re.compile(r'^\s+version\s+"?([^"\s]+)"?\s*$', re.MULTILINE)

        blocks = block_re.finditer(text)
        versions = version_re.finditer(text)
        version_list = list(versions)
        v_idx = 0

        for match in blocks:
            name = match.group(1)
            # Find the next version line after this block header
            pos = match.end()
            while v_idx < len(version_list) and version_list[v_idx].start() < pos:
                v_idx += 1
            if v_idx < len(version_list):
                version = version_list[v_idx].group(1)
                v_idx += 1
            else:
                continue

            if name in seen or not version:
                continue
            seen.add(name)
            deps.append(
                Dependency(
                    name=name,
                    ecosystem=Ecosystem.NPM,
                    current_version=version,
                )
            )
        return deps

    def _parse_pnpm_lock(self, path: Path) -> list[Dependency]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        packages = data.get("packages", {})
        for pkg_key in packages:
            # pnpm format: /package@version or package@version
            cleaned = pkg_key.lstrip("/")
            if "@" not in cleaned:
                continue
            # Handle scoped packages like @scope/pkg@version
            if cleaned.startswith("@"):
                # @scope/pkg@version
                parts = cleaned.split("@")
                # parts = ['', 'scope/pkg', 'version']
                if len(parts) >= 3:
                    name = f"@{parts[1]}"
                    version = parts[2].split("(")[0]  # strip peer dep markers
                else:
                    continue
            else:
                idx = cleaned.rfind("@")
                if idx <= 0:
                    continue
                name = cleaned[:idx]
                version = cleaned[idx + 1 :].split("(")[0]

            if name in seen or not version:
                continue
            seen.add(name)
            deps.append(
                Dependency(
                    name=name,
                    ecosystem=Ecosystem.NPM,
                    current_version=version,
                )
            )
        return deps

    def _parse_package_json(self, path: Path) -> list[Dependency]:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps: list[Dependency] = []
        seen: set[str] = set()

        for section in ("dependencies", "devDependencies"):
            packages = data.get(section, {})
            for name, version_spec in packages.items():
                if name in seen:
                    continue
                seen.add(name)
                # Strip range prefixes: ^, ~, >=, etc.
                version = re.sub(r"^[\^~>=<|* ]+", "", version_spec).split(",")[0].strip()
                deps.append(
                    Dependency(
                        name=name,
                        ecosystem=Ecosystem.NPM,
                        current_version=version or "*",
                        is_direct=section == "dependencies",
                    )
                )
        return deps
