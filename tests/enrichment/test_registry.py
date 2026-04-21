import httpx
import pytest
import respx

from dep_age.enrichment.registry import enrich_dependencies
from dep_age.models import Dependency, Ecosystem


@pytest.fixture
def npm_dep():
    return Dependency(name="lodash", ecosystem=Ecosystem.NPM, current_version="4.17.21")


@pytest.fixture
def pip_dep():
    return Dependency(name="requests", ecosystem=Ecosystem.PIP, current_version="2.31.0")


@respx.mock
@pytest.mark.asyncio
async def test_enrich_npm_dep(npm_dep):
    respx.get("https://registry.npmjs.org/lodash").mock(
        return_value=httpx.Response(
            200,
            json={
                "dist-tags": {"latest": "4.17.21"},
                "time": {
                    "4.17.21": "2021-02-20T15:42:15.000Z",
                    "4.17.20": "2020-08-13T02:13:50.000Z",
                },
            },
        )
    )

    result = await enrich_dependencies([npm_dep])
    assert len(result) == 1
    dep = result[0]
    assert dep.latest_version == "4.17.21"
    assert dep.published_date is not None


@respx.mock
@pytest.mark.asyncio
async def test_enrich_pip_dep(pip_dep):
    respx.get("https://pypi.org/pypi/requests/json").mock(
        return_value=httpx.Response(
            200,
            json={
                "info": {"version": "2.32.3"},
                "releases": {
                    "2.31.0": [{"upload_time_iso_8601": "2023-05-22T10:00:00.000Z"}],
                    "2.32.3": [{"upload_time_iso_8601": "2024-05-29T10:00:00.000Z"}],
                },
            },
        )
    )

    result = await enrich_dependencies([pip_dep])
    dep = result[0]
    assert dep.latest_version == "2.32.3"
    assert dep.published_date is not None


@respx.mock
@pytest.mark.asyncio
async def test_enrich_handles_error(npm_dep):
    respx.get("https://registry.npmjs.org/lodash").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    result = await enrich_dependencies([npm_dep])
    dep = result[0]
    assert dep.latest_version is None  # Graceful fallback


@respx.mock
@pytest.mark.asyncio
async def test_enrich_offline_mode(npm_dep):
    # No mocks needed; offline mode should not make requests
    result = await enrich_dependencies([npm_dep], offline=True)
    assert len(result) == 1
    assert result[0].latest_version is None
