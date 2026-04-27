from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Ecosystem(Enum):
    NPM = "npm"
    PIP = "pip"
    GEM = "gem"
    GO = "go"
    CARGO = "cargo"
    COMPOSER = "composer"


class Urgency(Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class CVE:
    id: str
    severity: str
    summary: str
    fixed_version: str | None
    url: str


@dataclass
class Dependency:
    name: str
    ecosystem: Ecosystem
    current_version: str
    latest_version: str | None = None
    published_date: datetime | None = None
    latest_date: datetime | None = None
    age_days: int | None = None
    cve_count: int = 0
    cves: list[CVE] = field(default_factory=list)
    urgency: Urgency = Urgency.NONE
    is_direct: bool = True
    version_constraint: str | None = None  # raw constraint from manifests, e.g. ">=0.9,<1.0"


@dataclass
class ScanResult:
    project_path: str
    ecosystems: list[Ecosystem]
    dependencies: list[Dependency]
    health_score: int = 0
    scan_time: datetime | None = None
