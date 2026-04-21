from __future__ import annotations

from datetime import datetime, timezone

from dep_age.models import Dependency


def calculate_age(dep: Dependency, now: datetime | None = None) -> Dependency:
    if now is None:
        now = datetime.now(tz=timezone.utc)

    if dep.published_date:
        pub = dep.published_date
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        delta = now - pub
        dep.age_days = max(0, delta.days)

    return dep


def format_age(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days < 30:
        return f"{days}d"
    if days < 365:
        months = days // 30
        return f"{months}m"
    years = days // 365
    months = (days % 365) // 30
    if months:
        return f"{years}y {months}m"
    return f"{years}y"


def calculate_all_ages(deps: list[Dependency], now: datetime | None = None) -> list[Dependency]:
    return [calculate_age(dep, now) for dep in deps]
