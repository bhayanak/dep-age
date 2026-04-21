from __future__ import annotations

from pathlib import Path

from dep_age.enrichment.age_calculator import format_age
from dep_age.models import Dependency
from dep_age.scoring.summary import HealthSummary


def render_markdown(
    deps: list[Dependency],
    summary: HealthSummary,
    output_file: str | None = None,
) -> str:
    lines: list[str] = []
    lines.append("# Dependency Health Report")
    lines.append("")
    lines.append(f"**Score**: {summary.score}/100  ")
    lines.append(f"**Total**: {summary.total} dependencies  ")
    lines.append(
        f"**Fresh** (<6m): {summary.fresh} | "
        f"**Aging** (6m-2y): {summary.aging} | "
        f"**Stale** (>2y): {summary.stale}  "
    )
    lines.append(f"**CVEs**: {summary.critical_cves} critical, {summary.moderate_cves} moderate  ")
    lines.append("")

    ecosystems = sorted({d.ecosystem for d in deps}, key=lambda e: e.value)
    for eco in ecosystems:
        eco_deps = [d for d in deps if d.ecosystem == eco]
        if not eco_deps:
            continue
        lines.append(f"## {eco.value} ({len(eco_deps)} deps)")
        lines.append("")
        lines.append("| Package | Current | Latest | Age | CVEs | Urgency |")
        lines.append("|---------|---------|--------|-----|------|---------|")
        for dep in eco_deps:
            lines.append(
                f"| {dep.name} | {dep.current_version} | {dep.latest_version or '?'} "
                f"| {format_age(dep.age_days)} | {dep.cve_count} | {dep.urgency.value} |"
            )
        lines.append("")

    text = "\n".join(lines)
    if output_file:
        Path(output_file).write_text(text, encoding="utf-8")
    return text
