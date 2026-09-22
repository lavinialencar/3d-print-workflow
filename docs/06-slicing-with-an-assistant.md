# Slicing with an assistant

"Slicing" means choosing the best print settings for *these* parts on *this* plate and turning the model into
G-code. Here the assistant does two separate jobs, and it helps to keep them apart:

| Job | What it means | Automated? |
|---|---|---|
| **Recommend** | look at the part and your printer profile, suggest settings **and explain why** | yes, and it always comes first |
| **Slice and validate** | run the slicer from the command line with a profile, check the G-code | yes |

**A recommendation is a starting point, not a guarantee.** The numbers come from community experience and your
own notes. Only a print tells you if they were right, which is why the cycle ends with you telling the assistant
how the part came out, so the next recommendation is better.

## The tools

The command-line slicing is provided by the `gcode` skill of the open-source
[text-to-cad](https://github.com/earthtojake/text-to-cad) project (MIT). Install its `cad` plugin following that project's
README; it also brings `dfam-check` and `bambu-labs`. The `gcode` skill drives OrcaSlicer, and it prefers Orca over
Bambu Studio because Studio's command line has been unstable on macOS.

Find your backends:

```bash
python3 <plugin>/skills/gcode/scripts/gcode_tool.py discover
```

`orcaslicer` should read `available: true`. If not: `brew install --cask orcaslicer`. (`prusa-slicer` and `curaengine` are the alternatives it also knows.)

## A profile wrapper, once

The skill needs a small JSON that tells it which of the slicer's own profiles to use and the limits of your machine. Save it next to your project
(not in this repository), say as `printer-profile.json`. The `machine` and `filament` blocks are only used to **check the G-code afterwards**; the
real behaviour comes from the slicer's native profiles.

`<ORCA>` below is `~/Library/Application Support/OrcaSlicer` written out in full (absolute paths are required).

**Any printer.** Export or pick your printer, process and filament profiles in the slicer, then point at them:

```json
{
  "backend": "orcaslicer",
  "native_settings": [
    "<ORCA>/user/default/machine/My Printer 0.4 nozzle.json",
    "<ORCA>/user/default/process/My 0.20mm Standard.json"
  ],
  "native_filaments": [ "<ORCA>/user/default/filament/My PLA.json" ],
  "machine":  { "name": "My Printer", "bed_size_mm": [220, 220], "z_height_mm": 250 },
  "filament": { "type": "PLA", "nozzle_temp_c": 210, "bed_temp_c": 60 }
}
```

The `gcode` skill also drives PrusaSlicer and CuraEngine (`"backend": "prusa-slicer"` or `"curaengine"`), each with its own native config.

**Bambu Lab, using Orca's shipped profiles.** Example for a P2S; use your model's names:

```json
{
  "backend": "orcaslicer",
  "native_config": "<ORCA>/system/BBL/process/0.20mm Standard @BBL P2S.json",
  "native_settings": [
    "<ORCA>/system/BBL/machine/Bambu Lab P2S 0.4 nozzle.json",
    "<ORCA>/system/BBL/process/0.20mm Standard @BBL P2S.json"
  ],
  "native_filaments": [
    "<ORCA>/user/default/filament/My PLA @Bambu Lab P2S 0.4 nozzle.json"
  ],
  "machine":  { "name": "Bambu Lab P2S 0.4 nozzle", "bed_size_mm": [256, 256], "z_height_mm": 256 },
  "filament": { "type": "PLA", "nozzle_temp_c": 220, "bed_temp_c": 55 }
}
```

## The four commands

```bash
G=<plugin>/skills/gcode/scripts/gcode_tool.py

python3 $G inspect  --input part.stl --json                       # is it a valid mesh?
python3 $G slice    --input part.stl --output part.gcode --profile printer-profile.json --backend auto --dry-run
python3 $G slice    --input part.stl --output part.gcode --profile printer-profile.json --backend auto --execute
python3 $G validate --gcode part.gcode --profile printer-profile.json --json
```

Always run `--dry-run` first: it prints the exact slicer command without running it.

### Reading the validation

`validate` checks that the file has extrusion moves and temperature commands, and that no absolute move leaves
your bed. It will also print **warnings about unknown commands** (`G29.1`, `M1002`, ...). Those are
Bambu-specific commands the validator does not know; it leaves them alone, and they are normal on a Bambu printer.

Validation is **static**. It does not prove the print will succeed. Look at the first layer.

## Pitfall: the command line does not resolve profile inheritance like the GUI, and the fix that closes it

This one is easy to miss and it matters for quality. Slicing the **same part** from the command line different ways produced G-code whose settings
differed in dozens of keys nobody asked to change, including the machine's own bed size.

**Root cause, confirmed on 2026-09-22.** A 20 mm test cube was sliced in the GUI (Bambu Lab P2S, `0.20mm Standard @BBL P2S`, a standalone filament
profile) and the G-code exported, then sliced from the command line with the same three profiles via `--load-settings`. The two G-codes disagreed on
175 of 630 compared settings. The most telling one: `printable_area` came back as the generic `200x200` instead of the P2S's real `256x256`. The
machine profile inherits about 30 keys, including its own bed size, wall generator default, pause G-code and cooling defaults, from a common base file
(`fdm_bbl_3dp_001_common` for Bambu machines). OrcaSlicer's `--load-settings` reads the exact file you give it and does **not** walk that `inherits`
chain, so every one of those 30 keys silently falls back to the slicer's built-in schema default instead of the machine's real value. This is the same
class of bug OrcaSlicer's own pull request [#15438](https://github.com/OrcaSlicer/OrcaSlicer/pull/15438), merged 2026-09-08, targets; the installed
version at the time of this test, v2.4.2 (2026-07-07), predates it.

**The fix that worked:** `scripts/fix_bambu_machine_profile.py` reads a machine profile, walks its `inherits` chain, and writes a copy of the *original*
file with only the missing keys filled in from its ancestors — nothing you already set is touched or overridden.

```bash
python3 scripts/fix_bambu_machine_profile.py "Bambu Lab P2S 0.4 nozzle" --out patched-machine.json
OrcaSlicer --load-settings "patched-machine.json;<process>.json" --load-filaments <filament>.json --slice 0 --outputdir out part.stl
```

A **full flatten** of the whole profile tree (every key from every ancestor, not just the missing ones) was tried first and made the CLI reject the
file outright, for a reason not yet understood — patching only what is missing is the version proven to work. The process profile's own (much shorter)
inheritance chain does need a full flatten, though, since a *child* process profile losing its parent's speeds and accelerations was a real, separately
observed failure mode; `--load-settings` on a bare child file gives you your overrides with everything else at the slicer's slow defaults.

**After the fix, verified with the same cube:** the disagreement dropped from 175 to 76 of 630 settings, and **none of the 76 remaining ones shape the
print** — wall count, layer height, infill, shells, supports, seam and every speed already matched exactly. What was left was host/connectivity
metadata (`printhost_*`, `thumbnails_format`), bookkeeping for a second AMS filament slot loaded with the identical filament (which the GUI's saved
project recognises as "no purge needed" in a way a fresh command-line invocation does not always reach the same conclusion on), and the physical build
plate type (`curr_bed_type`), which lives only in the GUI's project state and has to be set explicitly if it is not the default "Cool Plate":

```json
{ "curr_bed_type": "Supertack Plate" }
```

**So verify this on your printer too, with a reference.** `scripts/gcode_settings_diff.py` compares the settings the slicer records inside two G-code
files:

```bash
# 1. In the GUI, slice a part with your profile and export the G-code            -> gui.gcode
# 2. Slice the SAME part from the command line with the profile you want to trust -> cli.gcode
python3 scripts/gcode_settings_diff.py gui.gcode cli.gcode
```

An empty list, or only settings you changed on purpose or that are known-cosmetic (see above), means the command-line profile is equivalent to the GUI
for that machine. Do this once per printer before trusting an "automatic best quality" claim, including this project's: the 30 missing keys are specific
to how Bambu structures its profile inheritance, and a different vendor's common-base file will name different keys, even though the underlying bug
(the CLI not walking `inherits`) is the same.

**Confirmed again on more demanding geometry, 2026-09-22.** The cube above has flat faces and no overhang, the easy case. The same recipe was re-run on
the same cube tilted 45° with tree supports turned on, to see whether support-specific settings hold up too. Result: 76 of 632 compared settings still
differ, the exact same count and the exact same categories as the flat case (AMS second-slot bookkeeping, host/connectivity metadata) — every
support-related key (`support_type`, `support_style`, `enable_support`, `support_threshold_angle`, `support_interface_top_layers`,
`support_object_xy_distance`, `tree_support_brim_width`, ...) matched exactly. The fix generalises past a flat cube.

Two new, unrelated CLI-only crashes turned up while producing that geometry, both worth knowing before you rely on the command line for anything but a
flat, centred, brim-less test part:

1. **`--rotate` / `--rotate-x` / `--rotate-y` reliably segfault the CLI.** Any of these flags on a Bambu profile crashes with `SIGSEGV` inside
   `Slic3r::GUI::Plater::build_volume()`, called from the plate auto-arrange path (`PartPlateList::rebuild_plates_after_arrangement` →
   `add_instance` → `check_outside`) — GUI-only code that has no live `Plater` instance in a headless CLI run, so it dereferences a null pointer.
   `--scale` was not tested but treat it as suspect for the same reason. **Workaround: never rotate or scale through the CLI flags.** Bake the
   transform into the mesh yourself (rotate the STL's vertices in a small script, or export the already-transformed geometry from the GUI) and slice
   that file with no `--rotate*`/`--scale` flags at all.
2. **A brim on a tilted object near the bed edge, with tree supports on, crashes `Print::process` itself.** With `brim_type` at the GUI's own real
   value (`auto_brim`, or `outer_only`), slicing this same tilted+supported cube from the CLI crashed inside `Slic3r::make_brim` →
   `outer_inner_brim_area`, either as a `SIGSEGV` or as an uncaught `std::vector` exception depending on the run — non-deterministic, consistent with
   memory corruption from a degenerate polygon rather than a clean rejection. Isolated the actual trigger by bisecting on two things: `brim_type:
   no_brim` never crashes regardless of position, and moving the same object to the middle of the plate (still tilted, still supported, still
   `auto_brim`) never crashes either. So the crash needs all three: brim generation, tree support, and the part sitting close (tens of mm) to the
   printable-area boundary. **Workaround: keep parts well clear of the bed edge when slicing supported, tilted geometry from the CLI**, or set
   `brim_type` to `no_brim` as a quick diagnostic if a CLI slice ever dies with no useful error message.

Neither crash happened in the GUI for the same part and settings — both are CLI-only, and both are silent or near-silent (`run found error, exit`, or
nothing at all) unless you go looking in `~/Library/Logs/DiagnosticReports/OrcaSlicer-*.ips` for the actual signal and stack trace.

Before recommending, let the shape speak: [12 Slicing by part](12-slicing-by-part.md) measures the model and turns it into questions and settings.

## Settings matching is not enough: the tilted, tree-supported cube was physically printed too

Everything above proves the CLI and GUI produce the same *settings*. That is necessary but not sufficient — a real
print can still fail for reasons no settings diff catches. So the same tilted, tree-supported cube from above was
actually printed on a Bambu Lab P2S, not just sliced and compared.

**First attempt failed**, and the printer's own camera caught it: `HMS_0C00-0300-0003-0008`, "possible spaghetti
defect", paused the print partway through. The object had detached from its tree support mid-print. Cause: OrcaSlicer's
default support interface (`support_top_z_distance: 0.2mm`, `support_interface_spacing: 0.5mm`) is tuned to balance
holding the part up against being easy to snap off afterward — a reasonable default for an ordinary part, but too
weak for a small, steeply overhung contact area like a cube balanced on one edge with most of its mass in the air.

**Fix: tighten only the top interface** — `support_top_z_distance` to `0` and `support_interface_spacing` to `0.1mm`
— without changing anything else. Reprinted from scratch: finished at 100%, 140/140 layers, no failure, and the
part came out clean (some surface marking exactly where the support touched, which is normal and expected for any
FDM support contact, not a defect of this fix).

**A second, structural limit turned up along the way: a bare `.gcode` file cannot use AMS at all.** Sending a plain
`.gcode` straight to the printer over the network (FTPS upload + the `gcode_file` MQTT command — see
`scripts/bambu_lan_print.py` in the `bambu-labs` skill) uploads and starts the print fine, but the printer always
pulls from the external spool holder, never the AMS, no matter what you select on the touchscreen or load into the
AMS itself. This is not a bug to route around in the UI: AMS mapping lives in `Metadata/slice_info.config`, a file
that only exists inside a `.3mf` archive, and a bare `.gcode` has no such sidecar for the printer to read. Confirmed
independently on the [Bambu Lab community forum](https://forum.bambulab.com/t/using-ams-when-exporting-and-printing-gcode-files-not-3mf/61668).

**The fix: `scripts/package_gcode_as_3mf.py`.** Export a real, already-sliced project from the GUI once (File > Export >
"Export sliced file...") as a template, then swap its `Metadata/plate_N.gcode` for your command-line-produced G-code:

```bash
python3 scripts/package_gcode_as_3mf.py --template project.gcode.3mf --gcode part.gcode --out part.gcode.3mf
```

Everything else in the template, crucially `Metadata/slice_info.config`, is carried over untouched, so the packaged
file opens and sends with working AMS mapping exactly like the template did. The one requirement: the G-code has to
be sliced with a filament profile compatible with what the template declares (same `tray_info_idx`), which in
practice just means using the same filament profile you always do. Verified byte-for-byte (11 tests, and a real
template swapped with a real command-line G-code); not yet re-verified with a live print through this exact script —
the equivalent hand-built swap was proven live the same day, but treat the script itself as mechanically proven,
not yet print-proven end to end.

## The recommendation, in practice

Before slicing, the assistant reads your `printer-profile.md` and looks at the part: its size, its base, its
overhangs, what it is for. It then answers in a fixed, short format, listing **only what differs from your
defaults**, each with a reason and where to find it in the slicer:

```
Slicing recommendation for hook-bracket:
- Walls: 4 (default 2)  (it carries a load; Process > Strength)
- Orientation: flat side down, because the layer lines must run across the load
- Supports: none, all overhangs are below 45 degrees
- Adhesion: 5 mm brim, because the base is small and tall parts lift on a cold plate
```

You read it, you decide, and then it is applied. Two ways to apply it:

1. **In the slicer, by hand.** Slower, and the best way to learn: you see every setting move.
2. **Through a generated process profile**, then a command-line slice. Faster, less visible.

> Per-part overrides through the command line are the least-proven part of this workflow. Start with the
> first way until you trust the recommendations.

## After the print

Tell the assistant how the part came out. It records what worked in your notes (see
[knowledge-base-template](../knowledge-base-template/README.md)), and that record is what makes the tenth
recommendation better than the first.

For filament accounting, `scripts/gcode_consumption.py part.gcode` prints the grams and a ready-made log row.
That number is the **slicing-time estimate** for the whole part, so a cancelled print used less.

Next: [05 The monitor and alerts](07-monitor-and-alerts.md).
