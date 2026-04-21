<p align="center">
  <img src="assets/logo.svg" alt="dep-age logo" width="180" height="180">
</p>

<h1 align="center">dep-age</h1>

<p align="center">
  <strong>Cross-language dependency age analyzer</strong> — scan lock files &amp; manifests for staleness, CVEs, and update urgency.
</p>

<p align="center">
  <a href="https://github.com/bhayanak/dep-age/actions/workflows/ci.yml"><img src="https://github.com/bhayanak/dep-age/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://codecov.io/gh/dep-age/dep-age"><img src="https://img.shields.io/badge/coverage-95%25-brightgreen" alt="Coverage 95%"></a>
  <a href="https://pypi.org/project/dep-age/"><img src="https://img.shields.io/pypi/v/dep-age?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/dep-age/"><img src="https://img.shields.io/pypi/pyversions/dep-age" alt="Python"></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/license-MIT-green" alt="License: MIT"></a>
  <a href="https://github.com/bhayanak/dep-age/releases"><img src="https://img.shields.io/github/v/release/bhayanak/dep-age?include_prereleases&label=release" alt="Release"></a>
</p>

<p align="center">
  One command to answer: <em>"How old and risky are my dependencies?"</em>
</p>

---

## Features

- **6 ecosystems**: npm · pip · gem · go · cargo · composer
- **Lock files + manifests**: scans both resolved lock files and project manifests (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `composer.json`)
- **Async parallel** registry lookups with local caching
- **CVE checking** via OSV.dev API
- **Age classification**: Fresh / Aging / Stale
- **Urgency scoring**: None → Critical
- **Health score**: 0–100
- **Multiple outputs**: Rich terminal, JSON, Markdown, CSV, SVG badge
- **CI gating**: `--max-age` and `--max-cves` flags exit non-zero on violations

## Installation

```bash
pip install dep-age
```

## Quick Start

```bash
# Auto-detect lock files in current directory
dep-age scan

# Scan specific file
dep-age scan package-lock.json

# JSON output
dep-age scan --format json --output deps.json

# CI gating: fail if any dep > 2 years or has CVEs
dep-age scan --max-age "2 years" --max-cves 0

# Generate freshness badge
dep-age badge --output dep-badge.svg
```

## CLI Reference

```
dep-age scan [PATH...] [OPTIONS]

Arguments:
  PATH    Lock file(s) or directory to scan (default: current directory)

Options:
  -f, --format TEXT     Output: terminal, json, markdown, csv
  -o, --output TEXT     Write output to file
  --outdated            Show only outdated dependencies
  --cves-only           Show only dependencies with CVEs
  --older-than TEXT     Filter by age (e.g. "1 year", "6 months")
  --max-age TEXT        CI gate: exit 1 if any dep exceeds this age
  --max-cves INT        CI gate: exit 1 if total CVEs exceed this
  --ignore TEXT         Comma-separated packages to skip
  --offline             Use cached data only, no network requests
  -V, --version         Show version
```

## Supported Files

| Ecosystem | Lock Files | Manifest / Config |
|-----------|-----------|-------------------|
| **npm** | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` | `package.json` |
| **Python** | `requirements.txt`, `Pipfile.lock`, `poetry.lock` | `pyproject.toml` |
| **Ruby** | `Gemfile.lock` | — |
| **Go** | `go.sum` | `go.mod` |
| **Rust** | `Cargo.lock` | `Cargo.toml` |
| **PHP** | `composer.lock` | `composer.json` |

## CI Integration

```yaml
# GitHub Actions
- name: Dependency audit
  run: |
    pip install dep-age
    dep-age scan --max-age "2 years" --max-cves 0
```

## Development

```bash
git clone https://github.com/dep-age/dep-age.git
cd dep-age
pip install -e ".[dev]"
ruff check src/ tests/
pytest --cov=dep_age --cov-fail-under=95
```

## License

MIT
