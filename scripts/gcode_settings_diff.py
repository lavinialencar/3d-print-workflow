#!/usr/bin/env python3
"""gcode_settings_diff.py - compare the slicer settings recorded inside two G-code files.

Why this exists
    OrcaSlicer's command line does NOT resolve profile inheritance the way its GUI does. Slicing the same
    part with (a) a system profile file as-is, (b) a fully merged copy of it, or (c) a child profile that
    "inherits" it produces G-code whose settings differ in dozens of keys you never touched: speeds,
    line widths, wall generator, support type. This tool shows exactly which ones.

How to use it to check that a command-line slice matches the GUI
    1. In the slicer GUI, slice a part with your profile and export the G-code.
    2. Slice the SAME part from the command line with the profile you want to trust.
    3. Run:   python3 scripts/gcode_settings_diff.py gui.gcode cli.gcode
    If the list is empty (or contains only what you deliberately changed), the command-line
    profile is equivalent to the GUI's. If not, fix the profile until it is.

Reads .gcode or .gcode.3mf. It only reads. Slicers append their whole configuration to the G-code as
"; key = value" comment lines, and that is what is compared.

Usage
    python3 scripts/gcode_settings_diff.py A.gcode B.gcode
    python3 scripts/gcode_settings_diff.py A.gcode B.gcode --ignore wall_loops,brim_width
    python3 scripts/gcode_settings_diff.py A.gcode B.gcode --all      # do not hide identification/time keys
"""
import argparse
import re
import sys
import zipfile

# Zip-bomb guard: a .3mf is a zip, and a downloaded one is untrusted. The central directory's declared
# sizes are checked before anything is inflated (zipfile never inflates past the declared size).
ZIP_MAX_ENTRY = 200 * 1024 * 1024   # bytes, one entry uncompressed
ZIP_MAX_TOTAL = 500 * 1024 * 1024   # bytes, all entries together
ZIP_MAX_RATIO = 100                 # uncompressed:compressed, checked on entries over 1 MB


def check_zip(archive):
    """Raise ValueError when the archive would inflate to something absurd."""
    total = 0
    for info in archive.infolist():
        total += info.file_size
        if info.file_size > ZIP_MAX_ENTRY or total > ZIP_MAX_TOTAL:
            raise ValueError(f"{info.filename}: archive too large once uncompressed, refused")
        if info.file_size > 1024 * 1024 and info.file_size > ZIP_MAX_RATIO * max(info.compress_size, 1):
            raise ValueError(f"{info.filename}: compression ratio over {ZIP_MAX_RATIO}:1, refused as a possible zip bomb")

# Keys that describe the run, not the settings: hidden unless --all.
NOISE_EXACT = {"print_settings_id", "filament_settings_id", "printer_settings_id", "total_layer_number",
               "inherits_group", "filename_format"}
NOISE_PREFIX = ("filament used", "total ")
NOISE_CONTAINS = ("time", "weight")


def read_text(path):
    if path.lower().endswith(".3mf"):
        with zipfile.ZipFile(path) as archive:
            try:
                check_zip(archive)
            except ValueError as error:
                sys.exit(f"{path}: {error}")
            plates = sorted(n for n in archive.namelist() if re.match(r"Metadata/plate_\d+\.gcode$", n))
            if not plates:
                sys.exit(f"{path}: no Metadata/plate_N.gcode inside the .3mf")
            return archive.read(plates[0]).decode("utf-8", "replace")
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def read_settings(text):
    """Every '; key = value' comment line as a dict (the last occurrence wins)."""
    settings = {}
    for line in text.splitlines():
        match = re.match(r"^; ([A-Za-z_0-9 \[\]]+?) = (.*)$", line)
        if match:
            settings[match.group(1)] = match.group(2).strip()
    return settings


def is_noise(key):
    return (key in NOISE_EXACT or key.startswith(NOISE_PREFIX) or any(word in key for word in NOISE_CONTAINS))


def diff_settings(a, b, ignore=(), show_noise=False):
    """Sorted list of (key, value_in_a, value_in_b) that differ."""
    rows = []
    for key in sorted(set(a) | set(b)):
        if a.get(key) == b.get(key) or key in ignore:
            continue
        if not show_noise and is_noise(key):
            continue
        rows.append((key, a.get(key), b.get(key)))
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("a", help="first G-code (for example exported from the GUI)")
    parser.add_argument("b", help="second G-code (for example sliced from the command line)")
    parser.add_argument("--ignore", default="", help="comma-separated keys to skip")
    parser.add_argument("--all", action="store_true", help="also show identification, time and weight keys")
    args = parser.parse_args(argv)

    a, b = read_settings(read_text(args.a)), read_settings(read_text(args.b))
    if not a or not b:
        sys.exit("No '; key = value' settings block found in one of the files. Was it sliced by OrcaSlicer?")
    ignore = {k.strip() for k in args.ignore.split(",") if k.strip()}
    rows = diff_settings(a, b, ignore, args.all)
    for key, left, right in rows:
        print(f"{key}: {left}  ->  {right}")
    print(f"\n{len(rows)} setting(s) differ ({len(set(a) & set(b))} keys compared).")
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
