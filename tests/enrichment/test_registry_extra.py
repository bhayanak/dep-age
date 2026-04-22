"""Tests for registry response parsing and enrichment edge cases."""

import json

import httpx
import pytest
import respx

from dep_age.enrichment.registry import (
    _apply_registry_data,
    _find_version_time,
    _parse_response,
    enrich_dependencies,
)
from dep_age.models import Dependency, Ecosystem


class TestParseResponse:
    def test_npm_response(self):
        text = json.dumps(
            {
                "dist-tags": {"latest": "4.17.21"},
                "time": {
                    "4.17.21": "2021-02-20T15:42:15.000Z",
                },
            }
        )
        result = _parse_response(Ecosystem.NPM, "lodash", text)
        assert result is not None
        assert result["latest_version"] == "4.17.21"

    def test_pip_response(self):
        text = json.dumps(
            {
                "info": {"version": "2.32.0"},
                "releases": {
                    "2.31.0": [{"upload_time_iso_8601": "2023-05-22T10:00:00.000Z"}],
                    "2.32.0": [{"upload_time_iso_8601": "2024-01-01T10:00:00.000Z"}],
                },
            }
        )
        result = _parse_response(Ecosystem.PIP, "requests", text)
        assert result is not None
        assert result["latest_version"] == "2.32.0"

    def test_gem_response(self):
        text = json.dumps(
            [
                {"number": "3.0.8", "created_at": "2023-11-01T00:00:00Z"},
                {"number": "3.0.7", "created_at": "2023-10-01T00:00:00Z"},
            ]
        )
        result = _parse_response(Ecosystem.GEM, "rack", text)
        assert result is not None
        assert result["latest_version"] == "3.0.8"

    def test_gem_empty(self):
        result = _parse_response(Ecosystem.GEM, "rack", "[]")
        assert result is None

    def test_cargo_response(self):
        text = json.dumps(
            {
                "crate": {"newest_version": "1.0.193"},
                "versions": [
                    {
                        "num": "1.0.193",
                        "created_at": "2023-12-01T00:00:00Z",
                    },
                ],
            }
        )
        result = _parse_response(Ecosystem.CARGO, "serde", text)
        assert result is not None
        assert result["latest_version"] == "1.0.193"

    def test_composer_response(self):
        text = json.dumps(
            {
                "packages": {
                    "monolog/monolog": [
                        {
                            "version": "v3.5.0",
                            "time": "2023-10-27T00:00:00Z",
                        },
                    ]
                }
            }
        )
        result = _parse_response(Ecosystem.COMPOSER, "monolog/monolog", text)
        assert result is not None
        assert result["latest_version"] == "3.5.0"

    def test_composer_empty(self):
        text = json.dumps({"packages": {"test": []}})
        result = _parse_response(Ecosystem.COMPOSER, "test", text)
        assert result is None

    def test_go_response(self):
        import json

        text = json.dumps({"Version": "v1.2.0", "Time": "2024-01-15T10:00:00Z"})
        result = _parse_response(Ecosystem.GO, "example.com/pkg", text)
        assert result is not None
        assert result["latest_version"] == "v1.2.0"
        assert "v1.2.0" in result["times"]

    def test_go_empty(self):
        result = _parse_response(Ecosystem.GO, "example.com/pkg", "{}")
        assert result is not None
        assert result["latest_version"] is None

    def test_go_invalid_json(self):
        result = _parse_response(Ecosystem.GO, "test", "not json")
        assert result is None

    def test_invalid_json(self):
        result = _parse_response(Ecosystem.NPM, "test", "not json")
        assert result is None


class TestFindVersionTime:
    def test_exact_match(self):
        times = {"1.0.0": "2023-01-01", "2.0.0": "2024-01-01"}
        assert _find_version_time("1.0.0", times) == "2023-01-01"

    def test_short_version_padded(self):
        times = {"0.9.0": "2022-06-01", "0.9.1": "2022-07-01"}
        assert _find_version_time("0.9", times) == "2022-06-01"

    def test_prefix_fallback(self):
        times = {"2.8.1": "2022-01-01", "2.8.2": "2022-06-01"}
        assert _find_version_time("2.8", times) == "2022-01-01"

    def test_no_match(self):
        times = {"3.0.0": "2024-01-01"}
        assert _find_version_time("1.0", times) is None

    def test_empty_times(self):
        assert _find_version_time("1.0", {}) is None


class TestApplyRegistryDataFuzzyVersion:
    def test_fuzzy_version_resolves_date(self):
        dep = Dependency(name="typer", ecosystem=Ecosystem.PIP, current_version="0.9")
        data = {
            "latest_version": "0.12.0",
            "times": {
                "0.9.0": "2023-06-15T00:00:00Z",
                "0.12.0": "2024-06-01T00:00:00Z",
            },
        }
        result = _apply_registry_data(dep, data)
        assert result.published_date is not None


class TestApplyRegistryData:
    def test_apply_with_dates(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
        )
        data = {
            "latest_version": "2.0.0",
            "times": {
                "1.0.0": "2023-01-01T00:00:00Z",
                "2.0.0": "2024-01-01T00:00:00Z",
            },
        }
        result = _apply_registry_data(dep, data)
        assert result.latest_version == "2.0.0"
        assert result.published_date is not None
        assert result.latest_date is not None

    def test_apply_with_missing_times(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
        )
        data = {"latest_version": "2.0.0", "times": {}}
        result = _apply_registry_data(dep, data)
        assert result.latest_version == "2.0.0"
        assert result.published_date is None


@respx.mock
@pytest.mark.asyncio
async def test_enrich_with_cache(tmp_path):
    from dep_age.enrichment.cache import Cache

    cache = Cache(tmp_path / "cache")
    dep = Dependency(name="lodash", ecosystem=Ecosystem.NPM, current_version="4.17.21")

    respx.get("https://registry.npmjs.org/lodash").mock(
        return_value=httpx.Response(
            200,
            json={
                "dist-tags": {"latest": "4.17.21"},
                "time": {"4.17.21": "2021-02-20T15:42:15.000Z"},
            },
        )
    )

    # First call populates cache
    result = await enrich_dependencies([dep], cache=cache)
    assert result[0].latest_version == "4.17.21"

    # Second call should use cache
    dep2 = Dependency(name="lodash", ecosystem=Ecosystem.NPM, current_version="4.17.21")
    result2 = await enrich_dependencies([dep2], cache=cache)
    assert result2[0].latest_version == "4.17.21"

    cache.close()


class TestGoPseudoVersionTime:
    def test_pseudo_version(self):
        from dep_age.enrichment.registry import _parse_go_pseudo_version_time

        result = _parse_go_pseudo_version_time("v0.0.0-20180724234803-3673e40ba225")
        assert result is not None
        assert result.year == 2018
        assert result.month == 7
        assert result.day == 24

    def test_tagged_version(self):
        from dep_age.enrichment.registry import _parse_go_pseudo_version_time

        result = _parse_go_pseudo_version_time("v1.19.0")
        assert result is None

    def test_pre_release_pseudo(self):
        from dep_age.enrichment.registry import _parse_go_pseudo_version_time

        result = _parse_go_pseudo_version_time("v0.0.0-20200313102051-9f266ea9e77c")
        assert result is not None
        assert result.year == 2020
        assert result.month == 3
        assert result.day == 13


class TestGoModuleEncoding:
    def test_uppercase_encoding(self):
        from dep_age.enrichment.registry import _go_encode_module

        assert _go_encode_module("github.com/BurntSushi/toml") == "github.com/!burnt!sushi/toml"

    def test_no_uppercase(self):
        from dep_age.enrichment.registry import _go_encode_module

        assert _go_encode_module("github.com/pkg/errors") == "github.com/pkg/errors"

    def test_mixed_case(self):
        from dep_age.enrichment.registry import _go_encode_module

        assert (
            _go_encode_module("github.com/DATA-DOG/go-sqlmock")
            == "github.com/!d!a!t!a-!d!o!g/go-sqlmock"
        )


@respx.mock
@pytest.mark.asyncio
async def test_enrich_go_tagged_version():
    dep = Dependency(
        name="google.golang.org/grpc", ecosystem=Ecosystem.GO, current_version="v1.19.0"
    )

    # Mock @latest endpoint
    respx.get("https://proxy.golang.org/google.golang.org/grpc/@latest").mock(
        return_value=httpx.Response(
            200,
            json={"Version": "v1.72.3", "Time": "2025-04-01T00:00:00Z"},
        )
    )

    # Mock .info for current version
    respx.get("https://proxy.golang.org/google.golang.org/grpc/@v/v1.19.0.info").mock(
        return_value=httpx.Response(
            200,
            json={"Version": "v1.19.0", "Time": "2019-02-26T00:00:00Z"},
        )
    )

    result = await enrich_dependencies([dep])
    d = result[0]
    assert d.latest_version == "v1.72.3"
    assert d.published_date is not None
    assert d.published_date.year == 2019
    assert d.latest_date is not None


@respx.mock
@pytest.mark.asyncio
async def test_enrich_go_pseudo_version():
    dep = Dependency(
        name="golang.org/x/net",
        ecosystem=Ecosystem.GO,
        current_version="v0.0.0-20180724234803-3673e40ba225",
    )

    # Mock @latest endpoint
    respx.get("https://proxy.golang.org/golang.org/x/net/@latest").mock(
        return_value=httpx.Response(
            200,
            json={"Version": "v0.16.0", "Time": "2023-10-11T00:00:00Z"},
        )
    )

    result = await enrich_dependencies([dep])
    d = result[0]
    assert d.latest_version == "v0.16.0"
    assert d.published_date is not None
    assert d.published_date.year == 2018
    assert d.published_date.month == 7


@respx.mock
@pytest.mark.asyncio
async def test_enrich_go_uppercase_module():
    dep = Dependency(
        name="github.com/BurntSushi/toml",
        ecosystem=Ecosystem.GO,
        current_version="v0.3.1",
    )

    # Module path should be encoded for proxy
    respx.get("https://proxy.golang.org/github.com/!burnt!sushi/toml/@latest").mock(
        return_value=httpx.Response(
            200,
            json={"Version": "v1.3.2", "Time": "2023-02-01T00:00:00Z"},
        )
    )

    respx.get("https://proxy.golang.org/github.com/!burnt!sushi/toml/@v/v0.3.1.info").mock(
        return_value=httpx.Response(
            200,
            json={"Version": "v0.3.1", "Time": "2018-11-05T00:00:00Z"},
        )
    )

    result = await enrich_dependencies([dep])
    d = result[0]
    assert d.latest_version == "v1.3.2"
    assert d.published_date is not None


@respx.mock
@pytest.mark.asyncio
async def test_enrich_go_latest_404_pseudo_fallback():
    """When @latest returns 404, pseudo-version date should still be resolved."""
    dep = Dependency(
        name="example.com/unknown",
        ecosystem=Ecosystem.GO,
        current_version="v0.0.0-20200109180630-ec00e32a8dfd",
    )

    respx.get("https://proxy.golang.org/example.com/unknown/@latest").mock(
        return_value=httpx.Response(404)
    )

    result = await enrich_dependencies([dep])
    d = result[0]
    assert d.published_date is not None
    assert d.published_date.year == 2020
