# Slicing by part: measure the shape, ask the owner, then choose

A table of "good settings" is not enough. The right setting depends on the **shape** of the part and on what the owner wants from it. A sphere fights
the staircase effect. A bracket fights overhangs. A thin plate fights the nozzle width. This page describes the method, and
[`scripts/analyze_part.py`](../scripts/analyze_part.py) does the measuring.

```
   model (.stl / .3mf)
          |
          v
   1 MEASURE     the script reads the geometry           facts, no opinions
          |
          v
   2 ASK         only what the shape cannot answer       at most 4 questions, each with a default
          |
          v
   3 DECIDE      global settings + per-object overrides  every rule cites a source or says "heuristic"
          |
          v
   4 COMPARE     slice 2-3 scenarios, read real time     the slicer gives the numbers, not the script
   and grams
          |
          v
   5 SLICE       the chosen one, then you look at the print, and the result feeds the next decision
```

## 1. Measure

```bash
python3 scripts/analyze_part.py part.stl
python3 scripts/analyze_part.py plate.3mf --finish smooth --purpose functional
python3 scripts/analyze_part.py part.stl --json      # for the assistant
```

Needs Python 3.8+ and `numpy`. A 3MF plate is analysed **object by object**. Measured, per object:

| Measurement | How | Why it matters |
|---|---|---|
| Gentle-slope share (staircase) | area of faces between about 10 and 70 degrees from horizontal | curves and domes show layer steps most; this is where thinner layers pay off |
| Flat top | area of up-facing flat faces at the highest point | the only place ironing works |
| Flat faces up elsewhere | same, anywhere | floors and steps inside a part: ironing them costs time and is rarely seen |
| Round vertical walls | vertical faces whose direction is not a multiple of 90 degrees | round walls show the seam |
| Overhang needing support | down-facing area steeper than 40 degrees from horizontal, off the bed | OrcaSlicer's default support threshold |
| Longest bridge | short side of each flat, down-facing patch | bridges beyond about 40 mm sag whatever you set |
| Bed contact and aspect | area touching the bed, height over the square root of it | tall on a small footprint: brim |
| Wall thickness | rays cast from sampled surface points along the inward normal, 10th percentile | walls thinner than one line may not print |
| Six orientations | the numbers above, for each way of standing the part up | orientation is chosen with evidence |

It also repairs an inside-out mesh (negative volume) before measuring, because a flipped mesh swaps "up" and "down" and every number lies.

The orientation search only lets an orientation compete if the part can actually stand that way (enough bed contact, not too tall for its footprint).
Standing a 100 mm bar on a 3 mm edge removes the overhang and adds a failed print.

## 2. Ask

The owner should not be interrogated, and the assistant should not guess what only the owner knows. The script produces at most four questions, each one
triggered by something it measured:

| Trigger | Question |
|---|---|
| purpose unknown | what is it for: decoration, a working part, load-bearing? (walls and infill) |
| finish unknown | smooth or fast? Say how much time there is, and both get sliced |
| large flat top | is the top the face people see? (ironing costs time) |
| overhang, and a better orientation exists | may that face point up? |
| overhang, no better orientation | is a support scar acceptable on that face? |
| walls thinner than a line | thicken them in the model, or accept that they may not print? |

The finish preference is the single most valuable answer. A part that is finished smooth costs more time and filament, so the honest way to ask is
with numbers: slice the scenarios and show what each costs (step 4).

## 3. Decide: global and per-object

Some settings belong to the whole plate (temperatures, purge, first-layer basics), others to one object (layer height, seam, ironing, supports, brim).
When a plate holds several objects the script keeps the settings most objects share as **global** and lists the rest as **per-object overrides**.

| Setting | Rule | Source or status |
|---|---|---|
| Base preset | layer height snaps to a preset that exists for the printer (0.08, 0.12, 0.16, 0.20, 0.24 on a P2S 0.4) | presets shipped with OrcaSlicer 2.4.2 |
| Layer height | smooth: 0.12, or 0.08 when the part is short and mostly slopes; standard: 0.20 (0.16 if slopes dominate); fast: 0.24. Never above 80% of the nozzle | [Prusa: variable layer height](https://help.prusa3d.com/article/variable-layer-height-function_1750); the ceiling is a community rule |
| Slowdown note | High Quality presets also slow the outer wall (60 mm/s against 200), so the time cost is speed as much as layers | read from the shipped presets |
| Walls and infill | decorative 2 walls 10%, working 3 walls 15%, load-bearing 4 walls 25%; against the light: 100% | walls carry strength: community consensus; the backlit case is a lesson learned, see the knowledge-base template |
| Wall generator | Arachne (default), it varies line width to fit thin walls | [OrcaSlicer wiki: wall generator](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_wall_generator); there is an open report that Arachne can be lumpy on very small geometry |
| Ironing | smooth finish, flat top of 3 cm2 or more, slopes under 50%: `topmost`, and 4 to 5 top layers under it | [OrcaSlicer wiki: ironing](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_ironing); the layer count is a heuristic: ironing smooths, it does not fill gaps |
| Seam | round walls over 25% of the surface: `aligned`; load-bearing: `random` | [OrcaSlicer wiki: seam](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_seam) |
| Supports | overhang above 2% of the surface or 150 mm2: on; `tree(auto)` when the part touches the bed and bridges are short, else `normal(auto)` | [OrcaSlicer wiki: support](https://www.orcaslicer.com/wiki/print_settings/support/support_settings_support); the thresholds are heuristics |
| Bridges | warn above 40 mm | [Bambu Lab wiki: bridging](https://wiki.bambulab.com/en/software/bambu-studio/parameter/bridge) |
| Brim | aspect above 3, or under 1 cm2 of bed contact: 5 mm outer brim | heuristic |

**"Heuristic" means this project's own threshold**, chosen to be sensible and easy to change, not a number from a paper. They live in one function
(`recommend`) so you can tune them, and the tests pin down the intended behaviour.

## 4. Compare the scenarios

The script cannot know your printer's real time or filament use. It proposes three scenarios (Smooth, Balanced, Fast) with the layer count of each.
Slice them, read the real numbers with [`gcode_consumption.py`](../scripts/gcode_consumption.py), and show the owner:

```
Scenario    preset          layers   time     filament
Smooth      0.12 HQ         167      ?        ?          <- filled from the slice
Balanced    0.20 Standard    100      ?        ?
Fast        0.24 Standard     83      ?        ?
```

Then the owner answers the one question that only they can: "how much time do I have, and how smooth do I want it?".

> **Read [06](06-slicing-with-an-assistant.md#pitfall-the-command-line-does-not-resolve-profile-inheritance-like-the-gui) first.** Comparing scenarios is
> only meaningful if the command-line slice matches what the GUI would produce. Verify that once with `gcode_settings_diff.py`.

## What this does not do

- It does not slice, and it does not know time or grams.
- It looks at geometry only: it cannot see that a face is visible, that a part must survive sunlight, or that it touches food. Those are the owner's answers.
- Thickness is sampled (a few hundred rays), not exhaustive, and the smallest sample is noisy at edges, so the report leads with the 10th percentile.
- Units are assumed to be millimetres. Overlapping shells inside one mesh (a post and a slab exported without a boolean union) leave internal faces that
  count as overhang.

## Try it

```bash
python3 -m venv .venv && .venv/bin/pip install numpy
.venv/bin/python scripts/analyze_part.py part.stl --finish smooth --purpose functional
.venv/bin/python -m unittest tests.test_analyze_part -v
```

Next: [09 The conductor skill](09-the-conductor-skill.md).
