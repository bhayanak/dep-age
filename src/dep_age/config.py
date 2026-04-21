from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# Default age thresholds (in days)
FRESH_THRESHOLD_DAYS = 180  # < 6 months = fresh
AGING_THRESHOLD_DAYS = 730  # 6 months – 2 years = aging
# > 2 years = stale

# Default urgency weights
CVE_CRITICAL_WEIGHT = 40
CVE_HIGH_WEIGHT = 20
CVE_MEDIUM_WEIGHT = 10
CVE_LOW_WEIGHT = 5
AGE_WEIGHT_PER_YEAR = 10

# Registry rate limiting
MAX_CONCURRENT_REQUESTS = 10
CACHE_TTL_SECONDS = 86400  # 24 hours

# Lock file -> ecosystem mapping
LOCKFILE_MAP: dict[str, str] = {
    "package-lock.json": "npm",
    "yarn.lock": "npm",
    "pnpm-lock.yaml": "npm",
    "package.json": "npm",
    "requirements.txt": "pip",
    "Pipfile.lock": "pip",
    "poetry.lock": "pip",
    "pyproject.toml": "pip",
    "Gemfile.lock": "gem",
    "go.sum": "go",
    "go.mod": "go",
    "Cargo.lock": "cargo",
    "Cargo.toml": "cargo",
    "composer.lock": "composer",
    "composer.json": "composer",
}


@dataclass
class Config:
    max_age_days: int | None = None
    max_cves: int | None = None
    ignore_packages: list[str] = field(default_factory=list)
    offline: bool = False
    cache_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "dep-age")
    format: str = "terminal"
    output_file: str | None = None
    older_than_days: int | None = None
    cves_only: bool = False
    outdated_only: bool = False
