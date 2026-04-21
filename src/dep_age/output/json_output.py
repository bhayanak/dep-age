from __future__ import annotations

import json
from pathlib import Path

from dep_age.enrichment.age_calculator import format_age
from dep_age.models import Dependency
from dep_age.scoring.summary import HealthSummary


def render_json(
    deps: list[Dependency],
    summary: HealthSummary,
    output_file: str | None = None,
) -> str:
    data = {
        "summary": {
            "total": summary.total,
            "fresh": summary.fresh,
            "aging": summary.aging,
            "stale": summary.stale,
            "with_cves": summary.with_cves,
            "critical_cves": summary.critical_cves,
            "moderate_cves": summary.moderate_cves,
            "score": summary.score,
        },
        "dependencies": [
            {
                "name": d.name,
                "ecosystem": d.ecosystem.value,
                "current_version": d.current_version,
                "latest_version": d.latest_version,
                "age": format_age(d.age_days),
                "age_days": d.age_days,
                "cve_count": d.cve_count,
                "cves": [
                    {
                        "id": c.id,
                        "severity": c.severity,
                        "summary": c.summary,
                        "fixed_version": c.fixed_version,
                        "url": c.url,
                    }
                    for c in d.cves
                ],
                "urgency": d.urgency.value,
                "is_direct": d.is_direct,
            }
            for d in deps
        ],
    }
    text = json.dumps(data, indent=2, default=str)
    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
    return text
