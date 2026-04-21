import httpx
import pytest
import respx

from dep_age.enrichment.cve_checker import check_all_cves
from dep_age.models import Dependency, Ecosystem


@pytest.fixture
def dep_with_cves():
    return Dependency(name="lodash", ecosystem=Ecosystem.NPM, current_version="4.17.15")


@respx.mock
@pytest.mark.asyncio
async def test_check_cves_found(dep_with_cves):
    respx.post("https://api.osv.dev/v1/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "vulns": [
                    {
                        "id": "GHSA-test-1234",
                        "aliases": ["CVE-2024-0001"],
                        "summary": "Prototype pollution in lodash",
                        "severity": [],
                        "database_specific": {"severity": "HIGH"},
                        "affected": [
                            {
                                "ranges": [
                                    {
                                        "events": [
                                            {"introduced": "0"},
                                            {"fixed": "4.17.21"},
                                        ]
                                    }
                                ]
                            }
                        ],
                        "references": [
                            {
                                "type": "ADVISORY",
                                "url": "https://nvd.nist.gov/vuln/detail/CVE-2024-0001",
                            }
                        ],
                    }
                ]
            },
        )
    )

    result = await check_all_cves([dep_with_cves])
    dep = result[0]
    assert dep.cve_count == 1
    assert dep.cves[0].id == "CVE-2024-0001"
    assert dep.cves[0].fixed_version == "4.17.21"
    assert dep.cves[0].severity == "MEDIUM"


@respx.mock
@pytest.mark.asyncio
async def test_check_cves_none_found(dep_with_cves):
    respx.post("https://api.osv.dev/v1/query").mock(return_value=httpx.Response(200, json={}))

    result = await check_all_cves([dep_with_cves])
    dep = result[0]
    assert dep.cve_count == 0
    assert dep.cves == []


@respx.mock
@pytest.mark.asyncio
async def test_check_cves_api_error(dep_with_cves):
    respx.post("https://api.osv.dev/v1/query").mock(
        return_value=httpx.Response(500, text="Server Error")
    )

    result = await check_all_cves([dep_with_cves])
    dep = result[0]
    assert dep.cve_count == 0  # Graceful fallback


@respx.mock
@pytest.mark.asyncio
async def test_check_cves_offline():
    dep = Dependency(name="test", ecosystem=Ecosystem.NPM, current_version="1.0.0")
    result = await check_all_cves([dep], offline=True)
    assert len(result) == 1
    assert result[0].cve_count == 0
