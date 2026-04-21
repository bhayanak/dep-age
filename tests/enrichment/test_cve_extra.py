"""Extra tests for CVE checker edge cases and caching."""

import json

import httpx
import pytest
import respx

from dep_age.enrichment.cache import Cache
from dep_age.enrichment.cve_checker import (
    _apply_cve_data,
    _cve_to_dict,
    _parse_vulns,
    check_all_cves,
)
from dep_age.models import CVE, Dependency, Ecosystem


class TestParseVulns:
    def test_parse_basic_vuln(self):
        vulns = [
            {
                "id": "GHSA-1234",
                "aliases": ["CVE-2024-0001"],
                "summary": "Test vulnerability",
                "severity": [],
                "database_specific": {"severity": "HIGH"},
                "affected": [
                    {
                        "ranges": [
                            {
                                "events": [
                                    {"introduced": "0"},
                                    {"fixed": "2.0.0"},
                                ]
                            }
                        ]
                    }
                ],
                "references": [
                    {
                        "type": "ADVISORY",
                        "url": "https://example.com/advisory",
                    }
                ],
            }
        ]
        cves = _parse_vulns(vulns)
        assert len(cves) == 1
        assert cves[0].id == "CVE-2024-0001"
        assert cves[0].fixed_version == "2.0.0"
        assert cves[0].url == "https://example.com/advisory"

    def test_parse_vuln_ghsa_only(self):
        vulns = [
            {
                "id": "GHSA-xxxx",
                "aliases": ["GHSA-xxxx"],
                "summary": "Test",
                "severity": [],
                "database_specific": {},
                "affected": [],
                "references": [],
            }
        ]
        cves = _parse_vulns(vulns)
        assert len(cves) == 1
        assert cves[0].id == "GHSA-xxxx"

    def test_parse_vuln_no_aliases(self):
        vulns = [
            {
                "id": "OSV-2024-001",
                "aliases": [],
                "summary": "Test",
                "severity": [],
                "database_specific": {},
                "affected": [],
                "references": [{"type": "WEB", "url": "https://example.com"}],
            }
        ]
        cves = _parse_vulns(vulns)
        assert len(cves) == 1
        assert cves[0].id == "OSV-2024-001"
        assert cves[0].url == "https://example.com"

    def test_parse_vuln_with_severity_score(self):
        vulns = [
            {
                "id": "TEST-001",
                "aliases": [],
                "summary": "Test",
                "severity": [{"score": "CVSS:3.1/AV:N"}],
                "database_specific": {"severity": "CRITICAL"},
                "affected": [],
                "references": [],
            }
        ]
        cves = _parse_vulns(vulns)
        assert len(cves) == 1
        assert cves[0].severity == "CRITICAL"

    def test_empty_vulns(self):
        assert _parse_vulns([]) == []


class TestCveToDict:
    def test_roundtrip(self):
        cve = CVE(
            id="CVE-2024-001",
            severity="HIGH",
            summary="Test",
            fixed_version="2.0.0",
            url="https://example.com",
        )
        d = _cve_to_dict(cve)
        assert d["id"] == "CVE-2024-001"
        assert d["severity"] == "HIGH"
        assert d["fixed_version"] == "2.0.0"


class TestApplyCveData:
    def test_apply_cve_data(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
        )
        cve_dicts = [
            {
                "id": "CVE-2024-001",
                "severity": "HIGH",
                "summary": "Test",
                "fixed_version": "2.0.0",
                "url": "https://example.com",
            }
        ]
        result = _apply_cve_data(dep, cve_dicts)
        assert result.cve_count == 1
        assert result.cves[0].id == "CVE-2024-001"


@respx.mock
@pytest.mark.asyncio
async def test_cve_cache_hit(tmp_path):
    cache = Cache(tmp_path / "cache")
    dep = Dependency(
        name="lodash",
        ecosystem=Ecosystem.NPM,
        current_version="4.17.15",
    )

    # Pre-populate cache
    cache_key = "cve:npm:lodash:4.17.15"
    cache.set(
        cache_key,
        json.dumps(
            [
                {
                    "id": "CVE-2024-001",
                    "severity": "HIGH",
                    "summary": "Test",
                    "fixed_version": "4.17.21",
                    "url": "https://example.com",
                }
            ]
        ),
    )

    # Should use cache, not make HTTP request
    result = await check_all_cves([dep], cache=cache)
    assert result[0].cve_count == 1
    assert result[0].cves[0].id == "CVE-2024-001"
    cache.close()


@respx.mock
@pytest.mark.asyncio
async def test_cve_populates_cache(tmp_path):
    cache = Cache(tmp_path / "cache")
    dep = Dependency(
        name="express",
        ecosystem=Ecosystem.NPM,
        current_version="4.17.0",
    )

    respx.post("https://api.osv.dev/v1/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "vulns": [
                    {
                        "id": "GHSA-test",
                        "aliases": ["CVE-2024-999"],
                        "summary": "Test vuln",
                        "severity": [],
                        "database_specific": {},
                        "affected": [],
                        "references": [],
                    }
                ]
            },
        )
    )

    result = await check_all_cves([dep], cache=cache)
    assert result[0].cve_count == 1

    # Verify cache was populated
    cache_key = "cve:npm:express:4.17.0"
    assert cache.get(cache_key) is not None
    cache.close()


@respx.mock
@pytest.mark.asyncio
async def test_cve_offline_with_cache(tmp_path):
    cache = Cache(tmp_path / "cache")
    dep = Dependency(
        name="test",
        ecosystem=Ecosystem.NPM,
        current_version="1.0.0",
    )

    cache_key = "cve:npm:test:1.0.0"
    cache.set(
        cache_key,
        json.dumps(
            [
                {
                    "id": "CVE-OFFLINE",
                    "severity": "LOW",
                    "summary": "Test",
                    "fixed_version": None,
                    "url": "",
                }
            ]
        ),
    )

    result = await check_all_cves([dep], cache=cache, offline=True)
    assert result[0].cve_count == 1
    assert result[0].cves[0].id == "CVE-OFFLINE"
    cache.close()
