#!/usr/bin/env python3
"""fix_bambu_machine_profile.py - patch a Bambu machine profile so the command line matches the GUI.

Why this exists
    Root cause found and confirmed on 22/09/2026, comparing a GUI-exported G-code against a command-line
    slice of the identical part: OrcaSlicer's `--load-settings` reads the machine JSON you give it, but
    does NOT walk its `inherits` chain. A Bambu machine file (for example "Bambu Lab P2S 0.4 nozzle.json")
    inherits from a common base ("fdm_bbl_3dp_001_common" or similar) that holds about 30 keys the printer
    file itself never repeats: `printable_area` (the real bed size), `printer_structure`, `machine_pause_gcode`,
    `bed_temperature_formula`, `enable_filament_ramming`, cooling and chamber defaults, and more. Loaded
    through the CLI, those keys silently fall back to the slicer's built-in schema defaults instead of the
    machine's real values (a 256x256 P2S bed came out as the generic 200x200, `printer_structure` came out
    "undefine"). This is the same class of bug the upstream fix PR #15438 targets, and this project's install
    at the time (OrcaSlicer 2.4.2) does not have it: https://github.com/OrcaSlicer/OrcaSlicer/pull/15438

What this script does
    Reads one machine profile from OrcaSlicer's bundled BBL profile folder, walks its `inherits` chain (as
    many parents as needed), and writes a copy of the ORIGINAL file with only the missing keys added from its
    ancestors. It does not touch or override anything already present in the child file, so any of your own
    customisation stays exactly as it was. This is a narrow patch, not a full flatten: a full flatten of the
    whole tree was tried and made the CLI reject the file outright (a different, still-unexplained failure),
    so patching only what is actually missing is the version that is proven to work.

What it does NOT fix
    Settings that live only in a saved project or in the GUI's own state, never in any profile file: which
    build plate is physically on the machine (`curr_bed_type`), a project-only filament assignment, and the
    fact that two AMS slots loaded with the very same filament let the GUI skip the purge tower while a
    command-line run of the same two profiles does not always reach the same conclusion. Set `curr_bed_type`
    yourself in your process profile if your plate is not the default "Cool Plate".

How this was verified (22/09/2026, Bambu Lab P2S, OrcaSlicer 2.4.2)
    A plain 20 mm test cube was sliced in the GUI (Bambu Lab P2S, 0.4 mm, "0.20mm Standard @BBL P2S", a
    standalone "3D Fila PLA básico" filament in two AMS slots) and the G-code exported. The same cube was then
    sliced from the command line with `--load-settings "<machine>;<process>"`. As found before, the raw files
    disagreed on 175 of 630 compared settings, including the bed's own printable area. After patching the
    machine profile with this script, and flattening the process profile's own (much shorter) inheritance
    chain, the disagreement dropped to 76 settings, none of them wall, layer, infill, shell, support, seam or
    speed settings: every setting that actually shapes the print already matched. The 76 that remained were
    host/connectivity metadata (printhost, thumbnails format), the two-AMS-slot bookkeeping described above,
    and the build plate type, which this script does not and should not guess for you.

Usage
    python3 scripts/fix_bambu_machine_profile.py "Bambu Lab P2S 0.4 nozzle" --out patched-machine.json
    python3 scripts/fix_bambu_machine_profile.py "Bambu Lab P2S 0.4 nozzle" --bbl-dir /path/to/BBL
    # then slice with the patched file instead of the original:
    OrcaSlicer --load-settings "patched-machine.json;<process>.json" --load-filaments <filament>.json \\
               --slice 0 --outputdir out part.stl
"""
import argparse
import glob
import json
import os
import sys

DEFAULT_BBL_DIRS = [
    "/Applications/OrcaSlicer.app/Contents/Resources/profiles/BBL",
    os.path.expanduser("~/Library/Application Support/OrcaSlicer/system/BBL"),
]


def find_profile(bbl_dir, kind, name):
    """A profile file by name, first as machine/process, then anywhere under the BBL tree (common bases live
    outside the machine/ and process/ subfolders)."""
    direct = os.path.join(bbl_dir, kind, name + ".json")
    if os.path.isfile(direct):
        return direct
    matches = glob.glob(os.path.join(bbl_dir, "**", name + ".json"), recursive=True)
    if not matches:
        raise FileNotFoundError(f"no '{name}.json' under {bbl_dir}")
    return matches[0]


def resolve_chain(bbl_dir, kind, name, seen=None):
    """The full, merged profile for `name`, parent-first, so the child's own keys win. Raises on a cycle."""
    seen = seen or set()
    if name in seen:
        raise ValueError(f"inherits cycle at '{name}'")
    path = find_profile(bbl_dir, kind, name)
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    parent_name = data.get("inherits")
    merged = resolve_chain(bbl_dir, kind, parent_name, seen | {name})[0] if parent_name else {}
    merged = dict(merged)
    merged.update(data)
    return merged, path


def missing_inherited_keys(bbl_dir, kind, name):
    """(raw_file_dict, missing_keys_dict, raw_path): keys the child file's own JSON does not have, that its
    ancestors do. These are exactly the keys `--load-settings` silently drops."""
    full, path = resolve_chain(bbl_dir, kind, name)
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)
    missing = {k: v for k, v in full.items() if k not in raw}
    return raw, missing, path


def patch(bbl_dir, kind, name):
    raw, missing, path = missing_inherited_keys(bbl_dir, kind, name)
    patched = dict(raw)
    patched.update(missing)
    return patched, missing, path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help='profile name as OrcaSlicer shows it, e.g. "Bambu Lab P2S 0.4 nozzle"')
    parser.add_argument("--kind", default="machine", choices=["machine", "process"], help="default: machine")
    parser.add_argument("--bbl-dir", help="OrcaSlicer's bundled BBL profile folder (default: search common locations)")
    parser.add_argument("--out", default="patched-profile.json", help="where to write the patched copy")
    parser.add_argument("--quiet", action="store_true", help="only print the output path")
    args = parser.parse_args(argv)

    bbl_dirs = [args.bbl_dir] if args.bbl_dir else DEFAULT_BBL_DIRS
    last_error = None
    for bbl_dir in bbl_dirs:
        if not bbl_dir or not os.path.isdir(bbl_dir):
            continue
        try:
            patched, missing, source = patch(bbl_dir, args.kind, args.name)
            break
        except FileNotFoundError as error:
            last_error = error
    else:
        sys.exit(f"Could not find '{args.name}' under any of: {', '.join(d for d in bbl_dirs if d)}\n({last_error})")

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(patched, handle, indent=2, ensure_ascii=False)

    if args.quiet:
        print(args.out)
        return 0
    print(f"Read:    {source}")
    print(f"Patched: {args.out}  ({len(missing)} inherited key(s) added, {len(patched)} total)")
    if missing:
        print("\nKeys the child file never had, filled in from its ancestors:")
        for key in sorted(missing):
            value = missing[key]
            print(f"  {key} = {value!r}"[:100])
    else:
        print("\nNothing was missing: this profile already carries every key its ancestors define.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
