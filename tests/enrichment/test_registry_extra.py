"""Tests for registry response parsing and enrichment edge cases."""

import json

import httpx
import pytest
import respx

from dep_age.enrichment.registry import (
    _apply_registry_data,
    _find_version_time,
    _parse_constraints,
    _parse_response,
    _resolve_manifest_version,
    _satisfies_all,
    _version_sort_key,
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


class TestVersionSortKey:
    def test_simple(self):
        assert _version_sort_key("1.2.3") == (1, 2, 3)

    def test_with_v_prefix(self):
        assert _version_sort_key("v2.0.0") == (2, 0, 0)

    def test_pre_release_stripped(self):
        assert _version_sort_key("1.0.0-rc1") == (1, 0, 0)

    def test_two_part(self):
        assert _version_sort_key("3.5") == (3, 5)

    def test_non_numeric(self):
        assert _version_sort_key("abc") == (0,)

    def test_sorting(self):
        versions = ["0.9.0", "0.25.0", "0.12.0", "1.0.0"]
        result = sorted(versions, key=_version_sort_key)
        assert result == ["0.9.0", "0.12.0", "0.25.0", "1.0.0"]


class TestParseConstraints:
    def test_caret(self):
        specs = _parse_constraints("^1.2.3", Ecosystem.NPM)
        assert specs is not None
        assert len(specs) == 2
        assert specs[0] == (">=", (1, 2, 3))
        assert specs[1] == ("<", (2,))

    def test_caret_zero_major(self):
        specs = _parse_constraints("^0.2.3", Ecosystem.NPM)
        assert specs is not None
        assert specs[1] == ("<", (0, 3))

    def test_tilde(self):
        specs = _parse_constraints("~1.2.3", Ecosystem.NPM)
        assert specs is not None
        assert specs[0] == (">=", (1, 2, 3))
        assert specs[1] == ("<", (1, 3))

    def test_compatible_release(self):
        specs = _parse_constraints("~=2.5", Ecosystem.PIP)
        assert specs is not None
        assert specs[0] == (">=", (2, 5))
        assert specs[1] == ("<", (2, 6))

    def test_comma_separated(self):
        specs = _parse_constraints(">=0.9,<1.0", Ecosystem.PIP)
        assert specs is not None
        assert len(specs) == 2
        assert specs[0] == (">=", (0, 9))
        assert specs[1] == ("<", (1, 0))

    def test_empty_returns_none(self):
        assert _parse_constraints("", Ecosystem.PIP) is None

    def test_single_ge(self):
        specs = _parse_constraints(">=2.0", Ecosystem.PIP)
        assert specs is not None
        assert specs[0] == (">=", (2, 0))


class TestSatisfiesAll:
    def test_within_range(self):
        specs = [(">=", (0, 9)), ("<", (1, 0))]
        assert _satisfies_all("0.25.0", specs) is True

    def test_below_range(self):
        specs = [(">=", (0, 9)), ("<", (1, 0))]
        assert _satisfies_all("0.8.0", specs) is False

    def test_above_range(self):
        specs = [(">=", (0, 9)), ("<", (1, 0))]
        assert _satisfies_all("1.0.0", specs) is False

    def test_exact_lower_bound(self):
        specs = [(">=", (2, 0)), ("<", (3, 0))]
        assert _satisfies_all("2.0.0", specs) is True

    def test_skips_prerelease(self):
        specs = [(">=", (1, 0))]
        assert _satisfies_all("2.0.0-rc1", specs) is False
        assert _satisfies_all("2.0.0-alpha", specs) is False
        assert _satisfies_all("2.0.0-beta.1", specs) is False

    def test_equality(self):
        specs = [("==", (1, 5, 0))]
        assert _satisfies_all("1.5.0", specs) is True
        assert _satisfies_all("1.6.0", specs) is False

    def test_not_equal(self):
        specs = [("!=", (1, 0, 0)), (">=", (0, 9))]
        assert _satisfies_all("1.0.0", specs) is False
        assert _satisfies_all("1.1.0", specs) is True

    def test_greater_than(self):
        specs = [(">", (1, 0, 0))]
        assert _satisfies_all("1.0.0", specs) is False
        assert _satisfies_all("1.0.1", specs) is True

    def test_less_equal(self):
        specs = [("<=", (2, 0, 0))]
        assert _satisfies_all("2.0.0", specs) is True
        assert _satisfies_all("2.0.1", specs) is False


class TestResolveManifestVersion:
    def test_resolves_to_latest_satisfying(self):
        dep = Dependency(
            name="typer",
            ecosystem=Ecosystem.PIP,
            current_version="0.9",
            version_constraint=">=0.9,<1.0",
        )
        times = {
            "0.9.0": "2023-06-15T00:00:00Z",
            "0.12.0": "2023-12-01T00:00:00Z",
            "0.25.0": "2024-10-01T00:00:00Z",
            "1.0.0": "2025-01-01T00:00:00Z",
        }
        result = _resolve_manifest_version(dep, times)
        assert result == "0.25.0"

    def test_no_constraint_returns_current(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.PIP,
            current_version="1.0.0",
        )
        result = _resolve_manifest_version(dep, {"1.0.0": "2023-01-01"})
        assert result == "1.0.0"

    def test_empty_times_returns_current(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.PIP,
            current_version="1.0.0",
            version_constraint=">=1.0",
        )
        result = _resolve_manifest_version(dep, {})
        assert result == "1.0.0"

    def test_caret_constraint(self):
        dep = Dependency(
            name="lodash",
            ecosystem=Ecosystem.NPM,
            current_version="4.17.0",
            version_constraint="^4.17.0",
        )
        times = {
            "4.17.0": "2020-01-01T00:00:00Z",
            "4.17.21": "2021-02-20T00:00:00Z",
            "5.0.0": "2025-01-01T00:00:00Z",
        }
        result = _resolve_manifest_version(dep, times)
        assert result == "4.17.21"

    def test_apply_registry_data_uses_resolved_version(self):
        dep = Dependency(
            name="typer",
            ecosystem=Ecosystem.PIP,
            current_version="0.9",
            version_constraint=">=0.9,<1.0",
        )
        data = {
            "latest_version": "0.25.0",
            "times": {
                "0.9.0": "2023-06-15T00:00:00Z",
                "0.25.0": "2024-10-01T00:00:00Z",
            },
        }
        result = _apply_registry_data(dep, data)
        assert result.current_version == "0.25.0"
        assert result.published_date is not None
        assert result.published_date.year == 2024


class TestResolveManifestVersionEdgeCases:
    def test_unparseable_constraint_returns_current(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.PIP,
            current_version="1.0.0",
            version_constraint="",
        )
        result = _resolve_manifest_version(dep, {"1.0.0": "2023-01-01"})
        assert result == "1.0.0"

    def test_no_version_satisfies_returns_current(self):
        dep = Dependency(
            name="test",
            ecosystem=Ecosystem.NPM,
            current_version="1.0.0",
            version_constraint=">=5.0",
        )
        times = {"1.0.0": "2023-01-01", "2.0.0": "2024-01-01"}
        result = _resolve_manifest_version(dep, times)
        assert result == "1.0.0"


class TestParseConstraintsEdgeCases:
    def test_caret_zero_zero(self):
        """^0.0.3 means >=0.0.3, <0.0.4"""
        specs = _parse_constraints("^0.0.3", Ecosystem.NPM)
        assert specs is not None
        assert specs[0] == (">=", (0, 0, 3))
        assert specs[1] == ("<", (0, 0, 4))

    def test_caret_zero_zero_no_patch(self):
        """^0.0 means >=0.0, <0.0.1"""
        specs = _parse_constraints("^0.0", Ecosystem.NPM)
        assert specs is not None
        assert specs[1] == ("<", (0, 0, 1))

    def test_tilde_single_part(self):
        """~1 means >=1, <2"""
        specs = _parse_constraints("~1", Ecosystem.NPM)
        assert specs is not None
        assert specs[0] == (">=", (1,))
        assert specs[1] == ("<", (2,))


class TestGoRegistryEdgeCases:
    """Cover Go-specific branches: pseudo fallback on 404, version info fetch errors."""

    @staticmethod
    @respx.mock
    @pytest.mark.asyncio
    async def test_go_latest_pseudo_version_fetch():
        """When latest itself is a pseudo-version, its date should be extracted."""
        dep = Dependency(
            name="example.com/mod",
            ecosystem=Ecosystem.GO,
            current_version="v1.0.0",
        )

        # @latest returns a pseudo-version as the latest
        respx.get("https://proxy.golang.org/example.com/mod/@latest").mock(
            return_value=httpx.Response(
                200,
                json={
                    "Version": "v0.0.0-20210101120000-abcdef123456",
                    "Time": "2021-01-01T12:00:00Z",
                },
            )
        )

        # .info for current version
        respx.get("https://proxy.golang.org/example.com/mod/@v/v1.0.0.info").mock(
            return_value=httpx.Response(
                200,
                json={"Version": "v1.0.0", "Time": "2020-06-01T00:00:00Z"},
            )
        )

        result = await enrich_dependencies([dep])
        d = result[0]
        assert d.published_date is not None
        assert d.latest_date is not None
