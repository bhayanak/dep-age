# Changelog

## [1.0.0] - 2026-04-21

### Added
- 6 ecosystem parsers: npm, pip, gem, go, cargo, composer
- Async parallel registry lookups with local caching (24h TTL)
- CVE checking via OSV.dev API
- Age calculation with staleness classification (Fresh/Aging/Stale)
- Update urgency scoring (None → Critical)
- Overall dependency health score (0-100)
- Rich terminal output with color-coded tables
- JSON, Markdown, CSV export formats
- SVG badge generator
- `--max-age` and `--max-cves` flags for CI gating
- `--offline` mode using cache only
- `--ignore` flag for package exclusion
- `--outdated` and `--cves-only` filters
- GitHub Actions CI pipeline (lint, test, coverage, security)
- Release pipeline with PyPI publishing
