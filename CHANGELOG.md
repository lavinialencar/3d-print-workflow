# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `scripts/analyze_part.py`: measures a model (slopes, flat tops, round walls, overhangs, bridges, wall thickness, six orientations) and turns it into questions for the owner, global and per-object settings, and three scenarios to slice and compare. Reads STL and 3MF plates. Needs numpy.
- `scripts/find_models.py`: before modeling, searches Printables for an existing model and prints a shortlist with likes, downloads, makes (people who printed it), licence and link. Read-only, no downloads. 7 tests with a fake network.
- `docs/12-slicing-by-part.md`: the method, with a source or an honest "heuristic" label on every rule.
- 15 tests for the analyzer, built on shapes with known answers (cube, sphere, cylinder, T bracket, thin plate).

### Changed
- docs/06 now records the likely upstream cause of the command-line versus GUI difference (OrcaSlicer pull request 15438, merged after v2.4.2) and says it is untested here.

## [0.1.0] - 2026-09-20

First public template, extracted from a working personal setup with every personal detail removed. Built for any printer, with a full track for
Bambu Lab's closed ecosystem.

### Added
- `scripts/print_monitor.py`: read-only printer monitor with ntfy alerts for start, finish, failure, pause, cancel and "not responding". Adapters for Bambu Lab
  (verified), Klipper/Moonraker and OctoPrint (experimental, unit-tested on sample payloads).
- `scripts/print_monitor_launchd.py`: macOS scheduler installer with `print`, `install`, `status`, `uninstall`.
- `scripts/studio_to_orca_filament.py`: converts a Bambu Studio 2.x filament profile into a standalone OrcaSlicer profile, avoiding three silent failure modes.
- `scripts/gcode_consumption.py`: reads filament use from sliced G-code and writes the log row.
- `scripts/gcode_settings_diff.py`: compares the slicer settings recorded inside two G-code files, to check a command-line profile against the GUI.
- `skill/print-conductor/`: thin conductor skill template.
- `knowledge-base-template/`: hub, printer profile, modeling checklist, filament log and print queue.
- `tools/scan_personal_data.py` and `tools/check_links.py`: a shape-based personal-data scanner and a documentation link checker, both run in CI.
- Twelve guides in `docs/`, including a Bambu Lab track, an other-printers guide, an example session, three SVG diagrams and a troubleshooting table.
- 49 unit tests on synthetic data, GitHub Actions CI with secret scanning, issue and pull-request templates.

### Known gaps
- The "print finished" alert has not yet been observed on real hardware (logic is unit-tested).
- The Klipper and OctoPrint adapters have never run on a real printer.
- Assistant-driven modeling through a CAD MCP server is connected but not yet exercised.
- Command-line slicing is not verified to match the GUI: the slicer's CLI does not resolve profile inheritance like the GUI does (see docs/06).
- Linux and Windows are untested; only the scheduler is macOS-specific.

[Unreleased]: https://github.com/lavinialencar/3d-print-workflow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lavinialencar/3d-print-workflow/releases/tag/v0.1.0
