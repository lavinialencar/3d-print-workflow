# Changelog

All notable changes are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.0] - 2026-09-22

### Added
- `scripts/package_gcode_as_3mf.py`: wraps a plain `.gcode` into a real Bambu `.gcode.3mf` by swapping only the template's `Metadata/plate_N.gcode` (and its `.md5`), leaving `Metadata/slice_info.config` untouched. Exists because a Bambu printer ignores AMS mapping entirely for a bare `.gcode` file, confirmed on the official Bambu Lab forum: AMS mapping lives in that config file, which only exists inside a `.3mf`. 11 tests; verified byte-for-byte on a real template and a real command-line-sliced G-code, not yet print-proven through this exact script end to end.

### Changed
- README: added an "active development, not a finished release" callout next to the existing unofficial-project notice, telling a new user to start on a small, low-stakes part and scale up gradually rather than trusting the template with a long print right away.
- README: the command-line slicing row now records that the tilted, tree-supported test cube was physically printed, not just settings-compared — a first print failed (support detached mid-print, caught by the printer's spaghetti-detection camera) because the default support interface is tuned for easy removal rather than for a small, steeply overhung contact area; tightening the top interface fixed it. Added rows for sending a plain G-code straight to a printer (works, but can't select an AMS slot) and for `package_gcode_as_3mf.py`.
- docs/06: documented a third OrcaSlicer crash, this one in opening a file from outside the app rather than in slicing. A plain `.stl` opened from the command line while OrcaSlicer is not yet running works reliably; a `.gcode.3mf` opened the same way opens a broken, empty "Import SLA archive" dialog instead of the project (traced to the file-type dispatch in OrcaSlicer's own `Plater.cpp`), and sending a second file to an already-running OrcaSlicer can crash the whole app or spawn a duplicate process instead of reusing the window. Workaround: script only the first STL of a session this way; open a `.3mf` from OrcaSlicer's own File > Open Project dialog instead, always.

## [0.2.1] - 2026-09-22

### Added
- `scripts/fix_bambu_machine_profile.py`: patches a Bambu machine profile with the keys it silently inherits but that OrcaSlicer's `--load-settings` does not resolve (about 30 for a P2S, including the real bed size), confirmed by comparing a GUI-exported G-code against a command-line slice of the same part. 11 tests on a fake profile tree.
- `scripts/analyze_part.py`: measures a model (slopes, flat tops, round walls, overhangs, bridges, wall thickness, six orientations) and turns it into questions for the owner, global and per-object settings, and three scenarios to slice and compare. Reads STL and 3MF plates. Needs numpy.
- `scripts/find_models.py`: before modeling, searches Printables and Thingiverse (official API, your own token, sent in a header) for an existing model and prints one shortlist with likes, makes (people who printed it), licence or derivatives permission, and link. Read-only, no downloads; hides adult and private things and drops loose hits. 18 tests with a fake network.
- `docs/12-slicing-by-part.md`: the method, with a source or an honest "heuristic" label on every rule, and a catalogue of ten kinds of part (curved, round walls, thin, thick, overhang, bridge, tall and thin, wide and flat, flat top, fits) built from public and community sources, with the disagreements between them written down.
- `--use` (text, multicolor, flexi, fit, container, watertight, vase, figurine, bracket, lithophane) and `--machine` for `analyze_part.py`: the ten uses carry rules from public and community sources, each with a status; an open container is detected from the geometry. Two of the disagreements found are settled with facts read from the slicer itself (the precise-wall help text, the default gap closing radius).
- 33 tests for the analyzer, built on shapes with known answers (cube, sphere, cylinder, T bracket, thin fin, thick block, wide plate). They also check that every rule has a source and a trust level, that unverified rules are never applied, and that every setting written exists in OrcaSlicer.

### Changed
- docs/06: the command-line versus GUI difference is now resolved, not just suspected. A real cube, sliced both ways and compared, confirmed the root cause (the CLI does not walk a machine profile's `inherits` chain) and proved the fix (`fix_bambu_machine_profile.py`): after patching, every setting that shapes the print matched the GUI exactly. Re-confirmed on a 45°-tilted cube with tree supports on: same 76-setting gap, same non-quality categories, every support-related setting matched. Documented two new CLI-only crashes found along the way: `--rotate`/`--rotate-x`/`--rotate-y` segfault (`Plater::build_volume()` on a null GUI singleton, via the auto-arrange path) and a brim near the bed edge on tilted+supported geometry can crash `Print::process` (`make_brim`/`outer_inner_brim_area`), non-deterministically. Neither reproduces in the GUI; both have documented workarounds.

### Security
- `scripts/analyze_part.py`: refuses a 3MF whose `.model` XML declares a `DOCTYPE` before parsing it, closing a billion-laughs-style entity-expansion denial of service. A `.model` file never legitimately has a `DOCTYPE` (it is not part of the 3MF format), so one is treated as a sign of a malicious file, which is a real risk for a script whose whole job is reading 3MFs downloaded from Printables/Thingiverse. Found in a security pass across her GitHub repos, not from an incident.

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

[Unreleased]: https://github.com/lavinialencar/3d-print-workflow/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/lavinialencar/3d-print-workflow/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/lavinialencar/3d-print-workflow/compare/v0.1.0...v0.2.1
[0.1.0]: https://github.com/lavinialencar/3d-print-workflow/releases/tag/v0.1.0
