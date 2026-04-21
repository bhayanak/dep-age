from __future__ import annotations

import asyncio
import contextlib
import json
import logging

import httpx
from dateutil.parser import parse as parse_date

from dep_age.config import MAX_CONCURRENT_REQUESTS
from dep_age.enrichment.cache import Cache
from dep_age.models import Dependency, Ecosystem

logger = logging.getLogger(__name__)

# Registry URL templates
REGISTRY_URLS: dict[Ecosystem, str] = {
    Ecosystem.NPM: "https://registry.npmjs.org/{name}",
    Ecosystem.PIP: "https://pypi.org/pypi/{name}/json",
    Ecosystem.GEM: "https://rubygems.org/api/v1/versions/{name}.json",
    Ecosystem.GO: "https://proxy.golang.org/{name}/@v/list",
    Ecosystem.CARGO: "https://crates.io/api/v1/crates/{name}",
    Ecosystem.COMPOSER: "https://repo.packagist.org/p2/{name}.json",
}


async def fetch_registry_info(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    dep: Dependency,
    cache: Cache | None,
) -> Dependency:
    cache_key = f"registry:{dep.ecosystem.value}:{dep.name}"

    if cache:
        cached = cache.get(cache_key)
        if cached:
            return _apply_registry_data(dep, json.loads(cached))

    url_template = REGISTRY_URLS.get(dep.ecosystem)
    if not url_template:
        return dep

    url = url_template.format(name=dep.name)

    try:
        async with semaphore:
            resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            logger.debug("Registry returned %d for %s", resp.status_code, dep.name)
            return dep

        data = _parse_response(dep.ecosystem, dep.name, resp.text)
        if data and cache:
            cache.set(cache_key, json.dumps(data))
        if data:
            return _apply_registry_data(dep, data)
    except (httpx.HTTPError, json.JSONDecodeError, Exception) as exc:
        logger.debug("Registry lookup failed for %s: %s", dep.name, exc)

    return dep


def _parse_response(ecosystem: Ecosystem, name: str, text: str) -> dict | None:
    """Extract {latest_version, published_date, latest_date} from registry response."""
    try:
        if ecosystem == Ecosystem.NPM:
            data = json.loads(text)
            latest = data.get("dist-tags", {}).get("latest")
            times = data.get("time", {})
            return {
                "latest_version": latest,
                "times": times,
            }

        if ecosystem == Ecosystem.PIP:
            data = json.loads(text)
            info = data.get("info", {})
            releases = data.get("releases", {})
            latest = info.get("version")
            # Get dates from releases
            times: dict[str, str] = {}
            for ver, files in releases.items():
                if files:
                    times[ver] = files[0].get("upload_time_iso_8601", "")
            return {"latest_version": latest, "times": times}

        if ecosystem == Ecosystem.GEM:
            versions = json.loads(text)
            if not versions:
                return None
            latest = versions[0].get("number")
            times = {}
            for v in versions:
                num = v.get("number", "")
                created = v.get("created_at", "")
                if num and created:
                    times[num] = created
            return {"latest_version": latest, "times": times}

        if ecosystem == Ecosystem.CARGO:
            data = json.loads(text)
            crate = data.get("crate", {})
            latest = crate.get("newest_version")
            versions = data.get("versions", [])
            times = {}
            for v in versions:
                num = v.get("num", "")
                created = v.get("created_at", "")
                if num and created:
                    times[num] = created
            return {"latest_version": latest, "times": times}

        if ecosystem == Ecosystem.COMPOSER:
            data = json.loads(text)
            packages = data.get("packages", {}).get(name, [])
            if not packages:
                return None
            # First entry is usually the latest
            latest = packages[0].get("version", "").lstrip("v")
            times = {}
            for p in packages:
                ver = p.get("version", "").lstrip("v")
                t = p.get("time", "")
                if ver and t:
                    times[ver] = t
            return {"latest_version": latest, "times": times}

        if ecosystem == Ecosystem.GO:
            # proxy.golang.org/@v/list returns newline-separated versions
            versions = [v.strip() for v in text.splitlines() if v.strip()]
            latest = versions[-1] if versions else None
            return {"latest_version": latest, "times": {}}

    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.debug("Failed to parse registry response for %s: %s", name, exc)
    return None


def _find_version_time(version: str, times: dict[str, str]) -> str | None:
    """Find the publish timestamp for a version, handling short versions like '0.9' → '0.9.0'."""
    # Exact match first
    if version in times:
        return times[version]

    # Try appending .0 (e.g. "0.9" → "0.9.0", "2.8" → "2.8.0")
    padded = version + ".0"
    if padded in times:
        return times[padded]

    # Try prefix match — pick the earliest release that starts with "version."
    prefix = version + "."
    candidates = [(v, t) for v, t in times.items() if v.startswith(prefix)]
    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return None


def _apply_registry_data(dep: Dependency, data: dict) -> Dependency:
    dep.latest_version = data.get("latest_version") or dep.latest_version
    times: dict[str, str] = data.get("times", {})

    ts = _find_version_time(dep.current_version, times)
    if ts:
        with contextlib.suppress(ValueError, TypeError):
            dep.published_date = parse_date(ts)

    if dep.latest_version and dep.latest_version in times:
        with contextlib.suppress(ValueError, TypeError):
            dep.latest_date = parse_date(times[dep.latest_version])

    return dep


async def enrich_dependencies(
    deps: list[Dependency],
    cache: Cache | None = None,
    offline: bool = False,
) -> list[Dependency]:
    if offline:
        # Only use cache in offline mode
        if cache:
            for dep in deps:
                cache_key = f"registry:{dep.ecosystem.value}:{dep.name}"
                cached = cache.get(cache_key)
                if cached:
                    _apply_registry_data(dep, json.loads(cached))
        return deps

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"Accept": "application/json"},
    ) as client:
        tasks = [fetch_registry_info(client, semaphore, dep, cache) for dep in deps]
        return list(await asyncio.gather(*tasks))
