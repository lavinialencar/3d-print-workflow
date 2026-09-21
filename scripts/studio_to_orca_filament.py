#!/usr/bin/env python3
"""studio_to_orca_filament.py - turn a Bambu Studio 2.x filament profile into one OrcaSlicer accepts.

Why this exists
    A user filament profile exported from Bambu Studio 2.x does NOT work when copied straight
    into OrcaSlicer. Three things go wrong (details in docs/04-orca-and-bambu-studio-migration.md):
      1. Orca silently ignores a user profile that has no valid "version" field.
      2. A profile that "inherits" another one gets the PARENT's filament_id, whatever the file says.
      3. Studio 2.x writes some values in pairs (one per nozzle type) or as "nil"; Orca 2.4 chokes
         on them ("Assigning from an empty vector") when slicing from the command line.

What it does
    Builds a STANDALONE Orca profile: the fully-resolved system profile you choose as a base,
    plus the values that differ in your Studio profile (custom name, vendor, cost, density,
    temperatures, cooling...). It keeps YOUR filament_id, drops "nil" values, trims paired
    values to the length Orca expects, and stamps a valid version.

Nothing is installed automatically. It writes a .json next to where you tell it (default: a
folder you can inspect first). Quit OrcaSlicer (Cmd+Q) before copying the result into Orca's
user folder, then reopen it.

Usage
    python3 scripts/studio_to_orca_filament.py \\
        --studio-profile "My PLA @Bambu Lab P2S 0.4 nozzle.json" \\
        --base "Bambu PLA Basic @BBL P2S" \\
        --out-dir ./out
    # then, with Orca closed:
    cp ./out/*.json "$HOME/Library/Application Support/OrcaSlicer/user/default/filament/"
"""
import argparse
import glob
import json
import os
import plistlib
import sys

DEFAULT_ORCA_DIR = "~/Library/Application Support/OrcaSlicer"
ORCA_APP_PLIST = "/Applications/OrcaSlicer.app/Contents/Info.plist"

# Keys that identify a profile rather than describe filament behaviour: never copied as overrides.
IDENTITY_KEYS = {
    "name", "from", "inherits", "version", "filament_settings_id", "setting_id", "filament_id",
    "compatible_printers", "instantiation", "type", "compatible_printers_condition",
    "compatible_prints", "compatible_prints_condition",
}


def load_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def find_system_profile(orca_dir, name):
    pattern = os.path.join(os.path.expanduser(orca_dir), "system", "*", "filament", f"{name}.json")
    matches = glob.glob(pattern)
    if not matches:
        sys.exit(f"System profile '{name}' not found under {orca_dir}/system/*/filament/. "
                 "Check the exact name (it is the file name without .json).")
    return matches[0]


def resolve(orca_dir, name):
    """Return the base profile with every 'inherits' parent merged in (child wins)."""
    chain = [load_json(find_system_profile(orca_dir, name))]
    while chain[-1].get("inherits"):
        chain.append(load_json(find_system_profile(orca_dir, chain[-1]["inherits"])))
    merged = {}
    for layer in reversed(chain):
        merged.update(layer)
    return merged


def orca_version(explicit=None):
    """Orca wants a 4-part version whose major matches the app's, e.g. 2.4.2.0."""
    if explicit:
        return explicit
    try:
        with open(ORCA_APP_PLIST, "rb") as handle:
            short = plistlib.load(handle)["CFBundleShortVersionString"]
        parts = short.split(".")
        return ".".join((parts + ["0", "0", "0", "0"])[:4])
    except Exception:
        return "2.4.2.0"


def convert(studio, base, name, version):
    """Pure function: returns (orca_profile, list_of_overridden_keys)."""
    profile = dict(base)
    overridden = []
    for key, value in studio.items():
        if key in IDENTITY_KEYS or key not in base or not isinstance(value, list):
            continue
        if any(item == "nil" for item in value):      # pitfall 3: 'nil' values
            continue
        if len(value) > len(base[key]):               # pitfall 3: paired values
            value = value[: len(base[key])]
        if value != base[key]:
            profile[key] = value
            overridden.append(key)
    profile.pop("instantiation", None)
    profile.update({
        "type": "filament",
        "name": name,
        "from": "User",
        "inherits": "",                                # pitfall 2: standalone, keeps own filament_id
        "filament_id": studio.get("filament_id") or base.get("filament_id"),
        "filament_settings_id": [name],
        "is_custom_defined": "1",
        "version": version,                            # pitfall 1: valid version, or Orca ignores it
    })
    compatible = studio.get("compatible_printers")
    if compatible:
        profile["compatible_printers"] = compatible
    return profile, sorted(overridden)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--studio-profile", required=True, help="filament .json exported/copied from Bambu Studio")
    parser.add_argument("--base", required=True, help="Orca system filament to build on, e.g. 'Bambu PLA Basic @BBL P2S'")
    parser.add_argument("--name", help="name of the resulting profile (default: same as the Studio profile)")
    parser.add_argument("--orca-dir", default=DEFAULT_ORCA_DIR)
    parser.add_argument("--version", help="override the version stamp (default: read from the installed Orca)")
    parser.add_argument("--out-dir", default="./out")
    parser.add_argument("--dry-run", action="store_true", help="show what would change, write nothing")
    args = parser.parse_args(argv)

    studio = load_json(args.studio_profile)
    name = args.name or studio.get("name") or os.path.splitext(os.path.basename(args.studio_profile))[0]
    base = resolve(args.orca_dir, args.base)
    profile, overridden = convert(studio, base, name, orca_version(args.version))

    print(f"Profile      : {name}")
    print(f"Built on     : {args.base} (fully resolved)")
    print(f"filament_id  : {profile['filament_id']}")
    print(f"version      : {profile['version']}")
    print(f"Your values kept ({len(overridden)}): {', '.join(overridden) or 'none'}")
    if args.dry_run:
        print("\nDry run: nothing written.")
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, f"{name}.json")
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(profile, handle, indent=4, ensure_ascii=False)
    print(f"\nWrote {out_path}")
    print("Next: quit OrcaSlicer (Cmd+Q), copy it into Orca's user/default/filament/ folder, reopen Orca.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
