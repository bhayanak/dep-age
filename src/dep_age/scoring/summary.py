from __future__ import annotations

from dataclasses import dataclass

from dep_age.config import AGING_THRESHOLD_DAYS, FRESH_THRESHOLD_DAYS
from dep_age.models import Dependency


@dataclass
class HealthSummary:
    total: int = 0
    fresh: int = 0
    aging: int = 0
    stale: int = 0
    with_cves: int = 0
    critical_cves: int = 0
    moderate_cves: int = 0
    score: int = 0


def compute_health(deps: list[Dependency]) -> HealthSummary:
    summary = HealthSummary(total=len(deps))

    if not deps:
        summary.score = 100
        return summary

    for dep in deps:
        if dep.age_days is not None:
            if dep.age_days < FRESH_THRESHOLD_DAYS:
                summary.fresh += 1
            elif dep.age_days < AGING_THRESHOLD_DAYS:
                summary.aging += 1
            else:
                summary.stale += 1
        else:
            # Unknown age — count as aging
            summary.aging += 1

        if dep.cve_count > 0:
            summary.with_cves += 1
            for cve in dep.cves:
                sev = cve.severity.upper()
                if sev in ("CRITICAL", "HIGH"):
                    summary.critical_cves += 1
                else:
                    summary.moderate_cves += 1

    # Score: 100 base, deductions for staleness and CVEs
    score = 100.0
    if summary.total > 0:
        stale_pct = summary.stale / summary.total
        aging_pct = summary.aging / summary.total
        cve_pct = summary.with_cves / summary.total

        score -= stale_pct * 40  # Up to 40 points for staleness
        score -= aging_pct * 15  # Up to 15 points for aging
        score -= cve_pct * 30  # Up to 30 points for CVEs
        score -= min(summary.critical_cves * 3, 15)  # Up to 15 for critical CVEs

    summary.score = max(0, min(100, int(score)))
    return summary
