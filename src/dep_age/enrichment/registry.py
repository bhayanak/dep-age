from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
from datetime import datetime, timezone

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
    Ecosystem.GO: "https://proxy.golang.org/{name}/@latest",
    Ecosystem.CARGO: "https://crates.io/api/v1/crates/{name}",
    Ecosystem.COMPOSER: "https://repo.packagist.org/p2/{name}.json",
}

# Go pseudo-version pattern: v0.0.0-YYYYMMDDHHMMSS-abcdef123456
_GO_PSEUDO_RE = re.compile(r"v\d+\.\d+\.\d+-(\d{14})-[0-9a-f]+")


def _go_encode_module(path: str) -> str:
    """Encode a Go module path for proxy.golang.org (uppercase → !lowercase)."""
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), path)


def _parse_go_pseudo_version_time(version: str) -> datetime | None:
    """Extract timestamp from Go pseudo-version string."""
    m = _GO_PSEUDO_RE.match(version)
    if not m:
        return None
    ts = m.group(1)  # YYYYMMDDHHMMSS
    try:
        return datetime(
            int(ts[:4]),
            int(ts[4:6]),
            int(ts[6:8]),
            int(ts[8:10]),
            int(ts[10:12]),
            int(ts[12:14]),
            tzinfo=timezone.utc,
        )
    except (ValueError, IndexError):
        return None


async def _fetch_go_version_info(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    module: str,
    version: str,
) -> str | None:
    """Fetch publish time for a specific Go module version via proxy.golang.org."""
    url = f"https://proxy.golang.org/{_go_encode_module(module)}/@v/{version}.info"
    try:
        async with semaphore:
            resp = await client.get(url, timeout=15.0)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            return data.get("Time")
    except (httpx.HTTPError, json.JSONDecodeError, Exception) as exc:
        logger.debug("Go version info fetch failed for %s@%s: %s", module, version, exc)
    return None


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

    name = _go_encode_module(dep.name) if dep.ecosystem == Ecosystem.GO else dep.name
    url = url_template.format(name=name)

    try:
        async with semaphore:
            resp = await client.get(url, timeout=15.0)
        if resp.status_code != 200:
            logger.debug("Registry returned %d for %s", resp.status_code, dep.name)
            # For Go, still try to resolve date from pseudo-version
            if dep.ecosystem == Ecosystem.GO:
                pdt = _parse_go_pseudo_version_time(dep.current_version)
                if pdt:
                    dep.published_date = pdt
            return dep

        data = _parse_response(dep.ecosystem, dep.name, resp.text)

        # For Go, enrich with per-version timestamps
        if data and dep.ecosystem == Ecosystem.GO:
            # Try pseudo-version extraction first (no network call needed)
            pdt = _parse_go_pseudo_version_time(dep.current_version)
            if pdt:
                data.setdefault("times", {})[dep.current_version] = pdt.isoformat()
            else:
                # Fetch .info for current version
                ts = await _fetch_go_version_info(client, semaphore, dep.name, dep.current_version)
                if ts:
                    data.setdefault("times", {})[dep.current_version] = ts

            # Latest version time from @latest response is already set
            # If latest is different from current, and we don't have its time, fetch it
            latest = data.get("latest_version")
            if latest and latest not in data.get("times", {}):
                lpdt = _parse_go_pseudo_version_time(latest)
                if lpdt:
                    data.setdefault("times", {})[latest] = lpdt.isoformat()
                else:
                    lts = await _fetch_go_version_info(client, semaphore, dep.name, latest)
                    if lts:
                        data.setdefault("times", {})[latest] = lts

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
            # proxy.golang.org/@latest returns JSON: {"Version": "v1.2.0", "Time": "..."}
            data = json.loads(text)
            latest = data.get("Version")
            times: dict[str, str] = {}
            t = data.get("Time")
            if latest and t:
                times[latest] = t
            return {"latest_version": latest, "times": times}

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
