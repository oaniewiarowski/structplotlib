# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-12-26

### Added
- Initial release of structplotlib
- ETABS-style plan "fill diagram" plotting with square markers along frame members
- Support for ETABS and SAP2000 frame station data exports
- Schema normalization from vendor-specific to canonical column names
- Member-level envelope across multiple load cases (min, max, absmax)
- Station-level aggregation and reduction
- Optional "Show Values" labels at controlling stations
- Optional context geometry (thin lines for filtered-out members)
- Per-story plotting with automatic figure generation
- Convenience wrapper `plot_fill_plan` for pipeline-friendly usage
- Core API functions: `normalize_df`, `filter_cases`, `envelope_by_member`, `reduce_plan`, `plot_plan`, `plot_plan_by_story`

### Documentation
- README with quickstart examples
- Developer documentation (CODEX_CONTEXT.md, DESIGN_NOTES.md)

---

## Versioning Policy

This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backwards-compatible manner
- **PATCH** version for backwards-compatible bug fixes

