from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from dep_age import __version__
from dep_age.config import LOCKFILE_MAP, Config
from dep_age.enrichment.age_calculator import calculate_all_ages
from dep_age.enrichment.cache import Cache
from dep_age.enrichment.cve_checker import check_all_cves
from dep_age.enrichment.registry import enrich_dependencies
from dep_age.models import Dependency
from dep_age.output.badge import render_badge
from dep_age.output.csv_output import render_csv
from dep_age.output.json_output import render_json
from dep_age.output.markdown_output import render_markdown
from dep_age.output.terminal import render_terminal
from dep_age.parsers import ALL_PARSERS
from dep_age.scoring.summary import compute_health
from dep_age.scoring.urgency import calculate_all_urgencies

app = typer.Typer(
    name="dep-age",
    help="Cross-language dependency age analyzer",
    no_args_is_help=False,
    add_completion=False,
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"dep-age {__version__}")
        raise typer.Exit


def _detect_lockfiles(directory: Path) -> list[Path]:
    found: list[Path] = []
    for name in LOCKFILE_MAP:
        candidate = directory / name
        if candidate.is_file():
            found.append(candidate)
    return found


def _parse_lockfiles(paths: list[Path]) -> list[Dependency]:
    all_deps: list[Dependency] = []
    parsers = [p() for p in ALL_PARSERS]
    for path in paths:
        for parser in parsers:
            if parser.can_handle(path):
                deps = parser.parse(path)
                all_deps.extend(deps)
                break

    # Deduplicate: keep first occurrence per (name, ecosystem) pair.
    # Lock files are listed before manifests in LOCKFILE_MAP, so lock file
    # entries win when both files are present in the same directory.
    seen: set[tuple[str, str]] = set()
    unique: list[Dependency] = []
    for dep in all_deps:
        key = (dep.name, dep.ecosystem.value)
        if key not in seen:
            seen.add(key)
            unique.append(dep)
    return unique


def _filter_deps(deps: list[Dependency], cfg: Config) -> list[Dependency]:
    filtered = deps
    if cfg.ignore_packages:
        ignore_set = {p.lower() for p in cfg.ignore_packages}
        filtered = [d for d in filtered if d.name.lower() not in ignore_set]
    if cfg.cves_only:
        filtered = [d for d in filtered if d.cve_count > 0]
    if cfg.outdated_only:
        filtered = [
            d for d in filtered if d.latest_version and d.current_version != d.latest_version
        ]
    if cfg.older_than_days is not None:
        filtered = [
            d for d in filtered if d.age_days is not None and d.age_days > cfg.older_than_days
        ]
    return filtered


def _parse_age_string(age_str: str) -> int:
    """Convert human-readable age like '1 year' or '6 months' to days."""
    parts = age_str.lower().strip().split()
    if len(parts) < 2:
        # Try parsing as plain number of days
        return int(parts[0])
    num = int(parts[0])
    unit = parts[1]
    if unit.startswith("year"):
        return num * 365
    if unit.startswith("month"):
        return num * 30
    if unit.startswith("week"):
        return num * 7
    if unit.startswith("day"):
        return num
    return num


@app.command()
def scan(
    path: list[Path] = typer.Argument(  # noqa: B008, B006
        None,
        help="Lock file(s) or directory to scan.",
    ),
    output_format: str = typer.Option(  # noqa: A002
        "terminal",
        "--format",
        "-f",
        help="Output: terminal, json, markdown, csv",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to file",
    ),
    outdated: bool = typer.Option(
        False,
        "--outdated",
        help="Show only outdated deps",
    ),
    cves_only: bool = typer.Option(
        False,
        "--cves-only",
        help="Show only deps with CVEs",
    ),
    older_than: str | None = typer.Option(
        None,
        "--older-than",
        help='Filter by age, e.g. "1 year"',
    ),
    max_age: str | None = typer.Option(
        None,
        "--max-age",
        help="CI gate: max allowed age",
    ),
    max_cves: int | None = typer.Option(
        None,
        "--max-cves",
        help="CI gate: max allowed CVEs",
    ),
    ignore: str | None = typer.Option(
        None,
        "--ignore",
        help="Comma-separated packages to skip",
    ),
    offline: bool = typer.Option(
        False,
        "--offline",
        help="Skip network, use cache only",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version",
    ),
) -> None:
    """Scan lock files for dependency age, staleness, and CVEs."""
    cfg = Config(
        format=output_format,
        output_file=output,
        outdated_only=outdated,
        cves_only=cves_only,
        offline=offline,
    )
    if older_than:
        cfg.older_than_days = _parse_age_string(older_than)
    if max_age:
        cfg.max_age_days = _parse_age_string(max_age)
    if max_cves is not None:
        cfg.max_cves = max_cves
    if ignore:
        cfg.ignore_packages = [p.strip() for p in ignore.split(",")]

    # Resolve lock files
    if not path:
        paths = _detect_lockfiles(Path.cwd())
    else:
        paths = []
        for p in path:
            if p.is_dir():
                paths.extend(_detect_lockfiles(p))
            elif p.is_file():
                paths.append(p)
            else:
                console.print(f"[red]Not found: {p}[/red]")
                raise typer.Exit(1)

    if not paths:
        console.print("[yellow]No lock files found.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[dim]Found {len(paths)} lock file(s): {', '.join(p.name for p in paths)}[/dim]")

    # Parse
    deps = _parse_lockfiles(paths)
    if not deps:
        console.print("[yellow]No dependencies found in lock files.[/yellow]")
        raise typer.Exit(0)

    console.print(f"[dim]Parsed {len(deps)} dependencies[/dim]")

    # Enrich
    cache = Cache(cfg.cache_dir) if not cfg.offline or cfg.cache_dir.exists() else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Fetching registry data...", total=None)
        deps = asyncio.run(enrich_dependencies(deps, cache=cache, offline=cfg.offline))

        progress.add_task("Checking CVEs...", total=None)
        deps = asyncio.run(check_all_cves(deps, cache=cache, offline=cfg.offline))

    if cache:
        cache.close()

    # Calculate ages and urgencies
    calculate_all_ages(deps)
    calculate_all_urgencies(deps)

    # Filter
    deps = _filter_deps(deps, cfg)

    # Score
    summary = compute_health(deps)

    # Output
    project_name = Path.cwd().name
    if cfg.format == "json":
        text = render_json(deps, summary, output_file=cfg.output_file)
        if not cfg.output_file:
            console.print(text)
    elif cfg.format == "markdown":
        text = render_markdown(deps, summary, output_file=cfg.output_file)
        if not cfg.output_file:
            console.print(text)
    elif cfg.format == "csv":
        text = render_csv(deps, output_file=cfg.output_file)
        if not cfg.output_file:
            console.print(text)
    else:
        render_terminal(deps, summary, project_name=project_name)

    if cfg.output_file:
        console.print(f"[green]Written to {cfg.output_file}[/green]")

    # CI gating
    exit_code = 0
    if cfg.max_age_days is not None:
        violators = [d for d in deps if d.age_days is not None and d.age_days > cfg.max_age_days]
        if violators:
            console.print(
                f"[red]CI GATE FAILED: {len(violators)} dependencies exceed max age "
                f"({cfg.max_age_days} days)[/red]"
            )
            exit_code = 1

    if cfg.max_cves is not None:
        total_cves = sum(d.cve_count for d in deps)
        if total_cves > cfg.max_cves:
            console.print(
                f"[red]CI GATE FAILED: {total_cves} CVEs found (max allowed: {cfg.max_cves})[/red]"
            )
            exit_code = 1

    if exit_code:
        raise typer.Exit(exit_code)


@app.command()
def badge(
    output: str = typer.Option(  # noqa: B008
        "dep-badge.svg",
        "--output",
        "-o",
        help="Output SVG file path",
    ),
    path: list[Path] = typer.Argument(  # noqa: B008, B006
        None,
        help="Lock file(s) or directory to scan",
    ),
) -> None:
    """Generate an SVG badge showing dependency freshness."""
    if not path:
        paths = _detect_lockfiles(Path.cwd())
    else:
        paths = []
        for p in path:
            if p.is_dir():
                paths.extend(_detect_lockfiles(p))
            elif p.is_file():
                paths.append(p)

    if not paths:
        console.print("[yellow]No lock files found.[/yellow]")
        raise typer.Exit(0)

    deps = _parse_lockfiles(paths)
    cache = Cache(Config().cache_dir)

    deps = asyncio.run(enrich_dependencies(deps, cache=cache))
    deps = asyncio.run(check_all_cves(deps, cache=cache))
    cache.close()

    calculate_all_ages(deps)
    calculate_all_urgencies(deps)

    summary = compute_health(deps)
    render_badge(summary, output_file=output)
    console.print(f"[green]Badge written to {output}[/green]")
