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
