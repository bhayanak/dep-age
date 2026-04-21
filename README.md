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

## what it shows?
Below is **scan of current repo**:
```
$ dep-age scan .                                        
Found 1 lock file(s): pyproject.toml
Parsed 12 dependencies
╭───────────────────────────────────────╮
│ 📦 dep-age · Dependency Health Report │
│ dep-age  ·  Score: 57/100             │
│ 1 ecosystem(s)  ·  12 dependencies    │
╰───────────────────────────────────────╯

                            pip — 12 deps                            
┏━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━┳━━━━━━━━━┓
┃ Package         ┃ Current ┃ Latest      ┃ Age    ┃ CVEs ┃ Urgency ┃
┡━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━╇━━━━━━━━━┩
│ python-dateutil │ 2.8     │ 2.9.0.post0 │ 7y 2m  │ 0 ✅ │ HIGH    │
│ pyyaml          │ 6.0     │ 6.0.3       │ 4y 6m  │ 0 ✅ │ HIGH    │
│ tomli           │ 2.0     │ 2.4.1       │ 4y 4m  │ 0 ✅ │ HIGH    │
│ rich            │ 13.0    │ 15.0.0      │ 3y 3m  │ 0 ✅ │ HIGH    │
│ typer           │ 0.9     │ 0.24.1      │ 2y 11m │ 0 ✅ │ HIGH    │
│ pytest-asyncio  │ 0.23    │ 1.3.0       │ 2y 4m  │ 0 ✅ │ HIGH    │
│ httpx           │ 0.27    │ 0.28.1      │ 2y 2m  │ 0 ✅ │ HIGH    │
│ respx           │ 0.21    │ 0.23.1      │ 2y 1m  │ 0 ✅ │ HIGH    │
│ pytest-cov      │ 5.0     │ 7.1.0       │ 2y     │ 0 ✅ │ HIGH    │
│ ruff            │ 0.4     │ 0.15.11     │ 2y     │ 0 ✅ │ HIGH    │
│ diskcache       │ 5.6.3   │ 5.6.3       │ 2y 7m  │ 1 🟡 │ MEDIUM  │
│ pytest          │ 8.3     │ 9.0.3       │ 1y 9m  │ 1 🟡 │ MEDIUM  │
└─────────────────┴─────────┴─────────────┴────────┴──────┴─────────┘

Summary:
  📊 Total: 12 deps across 1 ecosystem(s)
  🟢 Fresh (<6 months): 0 (0%)
  🟡 Aging (6m-2y): 1 (8%)
  🔴 Stale (>2 years): 11 (91%)
  🔒 CVEs found: 2 (0 critical, 2 moderate)

💡 Recommendations:
  1. UPDATE IMMEDIATELY: diskcache 5.6.3 → 5.6.3 (1 CVE(s))
  2. UPDATE IMMEDIATELY: pytest 8.3 → 9.0.3 (1 CVE(s))
  3. Plan update: 11 stale dependencies (>2 years old)
```

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

[MIT](LICENSE)
