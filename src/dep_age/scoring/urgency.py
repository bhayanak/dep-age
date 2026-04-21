from __future__ import annotations

from dep_age.config import (
    AGING_THRESHOLD_DAYS,
    CVE_CRITICAL_WEIGHT,
    CVE_HIGH_WEIGHT,
    CVE_LOW_WEIGHT,
    CVE_MEDIUM_WEIGHT,
    FRESH_THRESHOLD_DAYS,
)
from dep_age.models import Dependency, Urgency


def calculate_urgency(dep: Dependency) -> Dependency:
    score = 0

    # CVE-based scoring
    for cve in dep.cves:
        sev = cve.severity.upper()
        if sev == "CRITICAL":
            score += CVE_CRITICAL_WEIGHT
        elif sev == "HIGH":
            score += CVE_HIGH_WEIGHT
        elif sev == "MEDIUM":
            score += CVE_MEDIUM_WEIGHT
        elif sev == "LOW":
            score += CVE_LOW_WEIGHT

    # Age-based scoring
    if dep.age_days is not None:
        if dep.age_days > AGING_THRESHOLD_DAYS:
            score += 15
        elif dep.age_days > FRESH_THRESHOLD_DAYS:
            score += 5

    # Version gap scoring (if we have latest and current differ)
    if dep.latest_version and dep.current_version != dep.latest_version:
        score += 5

    # Map score to urgency
    if score >= 40:
        dep.urgency = Urgency.CRITICAL
    elif score >= 20:
        dep.urgency = Urgency.HIGH
    elif score >= 10:
        dep.urgency = Urgency.MEDIUM
    elif score >= 5:
        dep.urgency = Urgency.LOW
    else:
        dep.urgency = Urgency.NONE

    return dep


def calculate_all_urgencies(deps: list[Dependency]) -> list[Dependency]:
    return [calculate_urgency(dep) for dep in deps]
