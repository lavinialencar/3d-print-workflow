#!/usr/bin/env python3
"""gcode_consumption.py - read the filament consumption from an OrcaSlicer G-code file.

Reads `.gcode` or `.gcode.3mf` (the plate's G-code is read from inside the zip) and prints:
grams, length, layers, the filament profile used, and a ready-made Markdown row for a
filament usage log (see knowledge-base-template/filament-log.md).

It only reads. It writes nothing to disk.

IMPORTANT: this is the estimate made at slicing time. If a print is cancelled or fails,
the real consumption is lower than the number shown here.

Usage
    python3 scripts/gcode_consumption.py part.gcode --part "Bracket" --spool "Black-01"
    python3 scripts/gcode_consumption.py part.gcode.3mf --part "Bracket" --spool "AMS-A1" --status success
    python3 scripts/gcode_consumption.py part.gcode --json
"""
import argparse
import datetime
import json
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


def read_text(path):
    if path.lower().endswith(".3mf"):
        with zipfile.ZipFile(path) as archive:
            try:
                check_zip(archive)
            except ValueError as error:
                sys.exit(f"{path}: {error}")
            plates = sorted(n for n in archive.namelist() if re.match(r"Metadata/plate_\d+\.gcode$", n))
            if not plates:
                sys.exit("No Metadata/plate_N.gcode inside the .3mf (was it sliced?)")
            return archive.read(plates[0]).decode("utf-8", "replace")
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def header_value(text, key):
    match = re.search(r"^;\s*" + re.escape(key) + r"\s*[=:]\s*(.+)$", text, re.M)
    return match.group(1).strip() if match else None


def numbers(value):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", value or "")]


def parse(text):
    grams = numbers(header_value(text, "filament used [g]"))
    length_mm = numbers(header_value(text, "filament used [mm]"))
    return {
        "grams_per_filament": grams,
        "grams_total": round(sum(grams), 2),
        "length_m": round(sum(length_mm) / 1000, 2) if length_mm else None,
        "layers": header_value(text, "total layer number"),
        "filament_profile": (header_value(text, "filament_settings_id") or "").strip('"') or None,
        "estimated_time": header_value(text, "estimated printing time (normal mode)")
        or header_value(text, "total estimated time"),
    }


def markdown_row(info, part, spool, status, date):
    note = f"read from slicer G-code, status {status}"
    if status == "cancelled":
        note += "; nominal weight of the file, real use is lower"
    return f"| {date} | {part} | {spool} | {info['grams_total']} | {note} |"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file")
    parser.add_argument("--part", default="(part name)")
    parser.add_argument("--spool", default="(spool to confirm)")
    parser.add_argument("--status", default="to confirm", help="success, cancelled or 'to confirm'")
    parser.add_argument("--date", default=datetime.date.today().isoformat())
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    info = parse(read_text(args.file))
    if not info["grams_per_filament"]:
        sys.exit("No '; filament used [g]' line found. Was this file sliced by OrcaSlicer?")
    if args.json:
        print(json.dumps(info, indent=2))
        return 0

    print("Consumption estimated AT SLICING TIME (not the real use if the print is cancelled):")
    print(f"  grams per filament : {info['grams_per_filament']}  total: {info['grams_total']} g")
    for label, key in (("length", "length_m"), ("estimated time", "estimated_time"),
                       ("filament profile", "filament_profile"), ("layers", "layers")):
        if info[key]:
            unit = " m" if key == "length_m" else ""
            print(f"  {label:<19}: {info[key]}{unit}")
    print("\nRow for the usage log:")
    print(markdown_row(info, args.part, args.spool, args.status, args.date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
