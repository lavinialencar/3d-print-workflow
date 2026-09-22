#!/usr/bin/env python3
"""package_gcode_as_3mf.py - wrap a plain G-code into a real Bambu .gcode.3mf, so the printer's AMS works.

Why this exists
    Found and confirmed on 22/09/2026: a Bambu printer ignores AMS mapping entirely for a plain `.gcode` file
    sent on its own (over FTPS, or dropped on the printer's SD/cache and opened from the touchscreen). It
    always pulls from the external spool holder, no matter what the G-code's own tool-change comments say and
    no matter what you pick on the touchscreen or in the AMS itself. This is not a bug you can toggle around;
    it is confirmed on the official Bambu Lab forum too ("Using AMS when exporting and printing GCODE-files
    (not 3MF!)", https://forum.bambulab.com/t/using-ams-when-exporting-and-printing-gcode-files-not-3mf/61668).
    The reason: what actually turns AMS mapping on is a separate file, `Metadata/slice_info.config`, that only
    exists inside a `.3mf` archive. A bare `.gcode` file has no such sidecar, so the printer has nothing to
    read AMS mapping from, however good the G-code itself is.

What this script does
    Takes a real, already-sliced Bambu/Orca project (a `.gcode.3mf`, exported from the GUI with
    File > Export > "Export sliced file...") as a TEMPLATE, and a plain `.gcode` file (for example, one
    produced by slicing from the command line, see docs/06), and writes a new `.gcode.3mf` that is the
    template with only its `Metadata/plate_N.gcode` (and the matching `.md5` sidecar) replaced by your G-code.
    Every other file in the template - crucially `Metadata/slice_info.config`, the file that makes AMS mapping
    work - is carried over untouched. The result opens and sends in OrcaSlicer, or over the network, exactly
    like the template did, but prints your G-code.

What this does NOT do
    It does not re-derive `slice_info.config` from your G-code. The template's filament declaration
    (`tray_info_idx`, type, id) has to already match what your G-code actually expects - in practice this
    means slicing your G-code with the same filament profile the template was sliced with. If they disagree,
    the print may ask for the wrong filament or its consumption estimate may be off; it is still your job to
    slice the standalone G-code with a filament profile compatible with the template, same as any other day.
    It also does not touch AMS SLOT selection - that still happens where it always did, in OrcaSlicer's own
    "Send print job" dialog or your printer's touchscreen, once the .3mf is loaded there.

How this was verified (22/09/2026, Bambu Lab P2S, OrcaSlicer 2.4.2)
    Exported a template `.gcode.3mf` for a 45-degree tilted, tree-supported test cube from the GUI. Packaged a
    plain `.gcode` for the same object (reinforced support settings, sliced separately) into that template
    with this script. `unzip -l` on the result showed the same `Metadata/slice_info.config` byte-for-byte as
    the template, `Metadata/plate_1.gcode` replaced with the new content, and the `.md5` sidecar updated to
    match. Not yet re-verified with a live print through this exact script (the equivalent hand-built swap was
    proven live earlier the same day); treat this as mechanically proven, not yet print-proven end to end.

Usage
    python3 scripts/package_gcode_as_3mf.py --template project.gcode.3mf --gcode part.gcode --out part.gcode.3mf
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import zipfile
from pathlib import Path

PLATE_RE = re.compile(r"^Metadata/plate_(\d+)\.gcode$")


class PackageError(RuntimeError):
    pass


def find_plate_paths(template: Path, plate: int | None = None) -> tuple[str, str]:
    """(plate_gcode_path, plate_md5_path) inside the template archive.

    Picks the lowest-numbered plate unless `plate` says otherwise. Raises PackageError if the template has
    no Metadata/plate_N.gcode at all - that means it is a design-time "Save Project" export, not a sliced
    "Export sliced file" one, and cannot be used as a template (see the note in the module docstring).
    """
    with zipfile.ZipFile(template) as archive:
        names = set(archive.namelist())
    plates = sorted(int(m.group(1)) for name in names if (m := PLATE_RE.match(name)))
    if not plates:
        raise PackageError(
            f"{template} has no Metadata/plate_N.gcode entry. It looks like a design-time project "
            '(File > Save Project), not a sliced one. Use File > Export > "Export sliced file..." instead.'
        )
    chosen = plate if plate is not None else plates[0]
    if chosen not in plates:
        raise PackageError(f"Plate {chosen} not found in {template}. Available plates: {plates}")
    plate_path = f"Metadata/plate_{chosen}.gcode"
    return plate_path, f"{plate_path}.md5"


def package(template: Path, gcode: Path, out: Path, plate: int | None = None) -> dict:
    """Write `out`: a copy of `template` with its plate G-code (and .md5) replaced by `gcode`'s content."""
    if not template.is_file():
        raise PackageError(f"Template project does not exist: {template}")
    if not gcode.is_file():
        raise PackageError(f"G-code input does not exist: {gcode}")
    if gcode.suffix.lower() != ".gcode":
        raise PackageError(f"Expected a plain .gcode input, got: {gcode.name}")

    plate_path, md5_path = find_plate_paths(template, plate)
    gcode_bytes = gcode.read_bytes()
    if not gcode_bytes:
        raise PackageError(f"G-code input is empty: {gcode}")
    gcode_md5 = hashlib.md5(gcode_bytes).hexdigest().upper()

    out.parent.mkdir(parents=True, exist_ok=True)
    found_plate = False
    found_md5 = False
    with zipfile.ZipFile(template, "r") as source, zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == plate_path:
                data = gcode_bytes
                found_plate = True
            elif info.filename == md5_path:
                data = gcode_md5.encode("ascii")
                found_md5 = True
            target.writestr(info, data)
        if not found_md5:
            # Older exports may not carry a .md5 sidecar; add one so the printer can still verify the transfer.
            target.writestr(md5_path, gcode_md5)

    if not found_plate:
        # find_plate_paths() already confirmed the entry exists, so getting here means a race (template
        # changed between the two reads) rather than a normal user error.
        raise PackageError(f"Template plate entry disappeared while packaging: {plate_path}")

    return {
        "template": str(template),
        "gcode": str(gcode),
        "out": str(out),
        "plate_gcode_path": plate_path,
        "plate_gcode_md5": gcode_md5,
        "plate_md5_sidecar_found_in_template": found_md5,
        "gcode_size_bytes": len(gcode_bytes),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--template", required=True, type=Path, help="a real, already-sliced .gcode.3mf (File > Export > Export sliced file...)")
    parser.add_argument("--gcode", required=True, type=Path, help="the plain .gcode to package (e.g. from a command-line slice)")
    parser.add_argument("--out", required=True, type=Path, help="where to write the packaged .gcode.3mf")
    parser.add_argument("--plate", type=int, default=None, help="plate number inside the template, default: the lowest one present")
    args = parser.parse_args(argv)

    try:
        result = package(args.template, args.gcode, args.out, args.plate)
    except PackageError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"Wrote {result['out']}")
    print(f"  replaced {result['plate_gcode_path']} with {result['gcode_size_bytes']} bytes from {args.gcode.name}")
    print(f"  md5: {result['plate_gcode_md5']}")
    print("Everything else, including Metadata/slice_info.config (the file that makes AMS mapping work), came from the template unchanged.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
