from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from dep_age.enrichment.age_calculator import format_age
from dep_age.models import Dependency, Urgency
from dep_age.scoring.summary import HealthSummary

URGENCY_COLORS = {
    Urgency.NONE: "green",
    Urgency.LOW: "blue",
    Urgency.MEDIUM: "yellow",
    Urgency.HIGH: "red",
    Urgency.CRITICAL: "bold red",
}


def _cve_display(dep: Dependency) -> str:
    if dep.cve_count == 0:
        return "0 ✅"
    if any(c.severity.upper() in ("CRITICAL", "HIGH") for c in dep.cves):
        return f"{dep.cve_count} 🔴"
    return f"{dep.cve_count} 🟡"


def render_terminal(
    deps: list[Dependency],
    summary: HealthSummary,
    project_name: str = "project",
) -> None:
    console = Console()

    ecosystems = sorted({d.ecosystem for d in deps}, key=lambda e: e.value)

    # Header panel
    header = (
        f"📦 dep-age · Dependency Health Report\n"
        f"{project_name}  ·  Score: {summary.score}/100\n"
        f"{len(ecosystems)} ecosystem(s)  ·  {summary.total} dependencies"
    )
    console.print(Panel(header, expand=False))
    console.print()

    # Table per ecosystem
    for eco in ecosystems:
        eco_deps = [d for d in deps if d.ecosystem == eco]
        if not eco_deps:
            continue

        eco_deps.sort(
            key=lambda d: (
                d.urgency != Urgency.CRITICAL,
                d.urgency != Urgency.HIGH,
                -(d.cve_count),
                -(d.age_days or 0),
            )
        )

        table = Table(title=f"{eco.value} — {len(eco_deps)} deps", show_lines=False)
        table.add_column("Package", style="bold")
        table.add_column("Current")
        table.add_column("Latest")
        table.add_column("Age")
        table.add_column("CVEs")
        table.add_column("Urgency")

        for dep in eco_deps:
            urgency_style = URGENCY_COLORS.get(dep.urgency, "white")
            table.add_row(
                dep.name,
                dep.current_version,
                dep.latest_version or "?",
                format_age(dep.age_days),
                _cve_display(dep),
                f"[{urgency_style}]{dep.urgency.value}[/{urgency_style}]",
            )

        console.print(table)
        console.print()

    # Summary
    console.print("Summary:")
    console.print(f"  📊 Total: {summary.total} deps across {len(ecosystems)} ecosystem(s)")
    console.print(f"  🟢 Fresh (<6 months): {summary.fresh} ({_pct(summary.fresh, summary.total)})")
    console.print(f"  🟡 Aging (6m-2y): {summary.aging} ({_pct(summary.aging, summary.total)})")
    console.print(f"  🔴 Stale (>2 years): {summary.stale} ({_pct(summary.stale, summary.total)})")
    console.print(
        f"  🔒 CVEs found: {summary.critical_cves + summary.moderate_cves} "
        f"({summary.critical_cves} critical, {summary.moderate_cves} moderate)"
    )
    console.print()

    # Recommendations
    critical_deps = [d for d in deps if d.cve_count > 0]
    critical_deps.sort(key=lambda d: -d.cve_count)
    if critical_deps:
        console.print("💡 Recommendations:")
        for i, dep in enumerate(critical_deps[:5], 1):
            latest = dep.latest_version or "latest"
            console.print(
                f"  {i}. UPDATE IMMEDIATELY: {dep.name} "
                f"{dep.current_version} → {latest} ({dep.cve_count} CVE(s))"
            )
        if summary.stale > 0:
            console.print(
                f"  {min(6, len(critical_deps) + 1)}. Plan update: "
                f"{summary.stale} stale dependencies (>2 years old)"
            )


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{part * 100 // total}%"
