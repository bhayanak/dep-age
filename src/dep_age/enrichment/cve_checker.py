from __future__ import annotations

import asyncio
import json
import logging

import httpx

from dep_age.config import MAX_CONCURRENT_REQUESTS
from dep_age.enrichment.cache import Cache
from dep_age.models import CVE, Dependency, Ecosystem

logger = logging.getLogger(__name__)

OSV_API_URL = "https://api.osv.dev/v1/query"

# Ecosystem name mapping for OSV.dev
OSV_ECOSYSTEM_MAP: dict[Ecosystem, str] = {
    Ecosystem.NPM: "npm",
    Ecosystem.PIP: "PyPI",
    Ecosystem.GEM: "RubyGems",
    Ecosystem.GO: "Go",
    Ecosystem.CARGO: "crates.io",
    Ecosystem.COMPOSER: "Packagist",
}


async def check_cves_for_dep(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    dep: Dependency,
    cache: Cache | None,
) -> Dependency:
    osv_ecosystem = OSV_ECOSYSTEM_MAP.get(dep.ecosystem)
    if not osv_ecosystem:
        return dep

    cache_key = f"cve:{dep.ecosystem.value}:{dep.name}:{dep.current_version}"
    if cache:
        cached = cache.get(cache_key)
        if cached:
            return _apply_cve_data(dep, json.loads(cached))

    payload = {
        "version": dep.current_version,
        "package": {
            "name": dep.name,
            "ecosystem": osv_ecosystem,
        },
    }

    try:
        async with semaphore:
            resp = await client.post(OSV_API_URL, json=payload, timeout=15.0)
        if resp.status_code != 200:
            logger.debug("OSV returned %d for %s", resp.status_code, dep.name)
            return dep

        data = resp.json()
        vulns = data.get("vulns", [])
        cve_list = _parse_vulns(vulns)

        if cache:
            cache.set(cache_key, json.dumps([_cve_to_dict(c) for c in cve_list]))

        dep.cves = cve_list
        dep.cve_count = len(cve_list)
    except (httpx.HTTPError, json.JSONDecodeError, Exception) as exc:
        logger.debug("CVE check failed for %s: %s", dep.name, exc)

    return dep


def _parse_vulns(vulns: list[dict]) -> list[CVE]:
    cves: list[CVE] = []
    for v in vulns:
        cve_id = ""
        for alias in v.get("aliases", []):
            if alias.startswith("CVE-") or alias.startswith("GHSA-"):
                cve_id = alias
                break
        if not cve_id:
            cve_id = v.get("id", "UNKNOWN")

        severity = "MEDIUM"
        for s in v.get("severity", []):
            score_str = s.get("score", "")
            # CVSS v3 score extraction
            if ":" in score_str:
                try:
                    # Extract base score from CVSS vector
                    parts = score_str.split("/")
                    for part in parts:
                        if part.startswith("CVSS:"):
                            continue
                except (ValueError, IndexError):
                    pass
            severity_map = v.get("database_specific", {}).get("severity", "")
            if severity_map:
                severity = severity_map.upper()

        # Extract fixed version
        fixed_version = None
        for affected in v.get("affected", []):
            for rng in affected.get("ranges", []):
                for event in rng.get("events", []):
                    if "fixed" in event:
                        fixed_version = event["fixed"]
                        break

        url = ""
        for ref in v.get("references", []):
            if ref.get("type") == "ADVISORY":
                url = ref.get("url", "")
                break
        if not url:
            refs = v.get("references", [])
            url = refs[0].get("url", "") if refs else ""

        cves.append(
            CVE(
                id=cve_id,
                severity=severity,
                summary=v.get("summary", ""),
                fixed_version=fixed_version,
                url=url,
            )
        )
    return cves


def _cve_to_dict(cve: CVE) -> dict:
    return {
        "id": cve.id,
        "severity": cve.severity,
        "summary": cve.summary,
        "fixed_version": cve.fixed_version,
        "url": cve.url,
    }


def _apply_cve_data(dep: Dependency, cve_dicts: list[dict]) -> Dependency:
    dep.cves = [
        CVE(
            id=c["id"],
            severity=c["severity"],
            summary=c["summary"],
            fixed_version=c.get("fixed_version"),
            url=c["url"],
        )
        for c in cve_dicts
    ]
    dep.cve_count = len(dep.cves)
    return dep


async def check_all_cves(
    deps: list[Dependency],
    cache: Cache | None = None,
    offline: bool = False,
) -> list[Dependency]:
    if offline:
        if cache:
            for dep in deps:
                cache_key = f"cve:{dep.ecosystem.value}:{dep.name}:{dep.current_version}"
                cached = cache.get(cache_key)
                if cached:
                    _apply_cve_data(dep, json.loads(cached))
        return deps

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async with httpx.AsyncClient(
        headers={"Content-Type": "application/json"},
    ) as client:
        tasks = [check_cves_for_dep(client, semaphore, dep, cache) for dep in deps]
        return list(await asyncio.gather(*tasks))
