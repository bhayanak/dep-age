from __future__ import annotations

import csv
import io
from pathlib import Path

from dep_age.enrichment.age_calculator import format_age
from dep_age.models import Dependency


def render_csv(
    deps: list[Dependency],
    output_file: str | None = None,
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "name",
            "ecosystem",
            "current_version",
            "latest_version",
            "age",
            "age_days",
            "cve_count",
            "urgency",
            "is_direct",
        ]
    )
    for dep in deps:
        writer.writerow(
            [
                dep.name,
                dep.ecosystem.value,
                dep.current_version,
                dep.latest_version or "",
                format_age(dep.age_days),
                dep.age_days if dep.age_days is not None else "",
                dep.cve_count,
                dep.urgency.value,
                dep.is_direct,
            ]
        )
    text = buf.getvalue()
    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
    return text
