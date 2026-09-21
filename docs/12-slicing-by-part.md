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

### Kinds of part, and what each one changes

A part can be several kinds at once. `analyze_part.py` names the kinds it found, with the number that says so, and every rule it applies prints its source and how far to trust it.

| Kind | Found when | What changes | Where it comes from |
|---|---|---|---|
| **curved** (sphere, dome) | 30% or more of the surface is a gentle slope | 0.12 mm layers, **variable layer height** in the slicer, and the idea of splitting a round part in two, flat side down, instead of supporting it | [Obico](https://www.obico.io/blog/orca-slicer-adaptive-and-variable-layer-height-guide-smoother-3d-prints/), [OrcaSlicer wiki](https://www.orcaslicer.com/wiki/print_prepare/prepare_variable_layer_height), [3dprinterly](https://3dprinterly.com/how-to-3d-print-a-dome-or-sphere-without-supports/) |
| **round walls** | 25% or more of the surface is a round vertical wall | seam `aligned`, plus a scarf seam (`seam_slope_type = external`) when the wall is longer than the 20 mm scarf; `random` for load-bearing parts | [OrcaSlicer wiki: seam](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_seam) |
| **thin** | walls under 0.8 mm at the thin end | `wall_loops` capped to the lines that fit (a 0.6 mm wall gets 1), Arachne kept, a question when a wall is thinner than one line, a 0.2 mm nozzle noted for miniatures | [OrcaSlicer wiki: wall generator](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_wall_generator) |
| **thick** (bulk) | smallest side 40 mm or more and 40 cm3 or more | wide inner walls and infill (0.6 mm, about 150%), Adaptive Cubic infill (Gyroid for load), and the question "is the surface visible on all sides?", because thin layers on a bulk part cost hours | [CNC Kitchen](https://www.cnckitchen.com/blog/the-effect-of-extrusion-width-on-strength-and-quality-of-3d-prints), [OrcaSlicer wiki: patterns](https://www.orcaslicer.com/wiki/print_settings/strength/strength_settings_patterns) |
| **overhang** | 150 mm2 or 2% of the surface steeper than 40 degrees | supports on; **normal** under large flat undersides, **tree** for curved and organic parts; 2 interface layers; the orientation question | [OrcaSlicer wiki: support](https://www.orcaslicer.com/wiki/print_settings/support/support_settings_support), [StackSheriff](https://stacksheriff.com/3d-printing/orcaslicer-support-settings/) |
| **bridge** | a flat underside spanning 15 mm or more | `thick_bridges` on; a warning past 40 mm | [OrcaSlicer wiki: bridging](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_bridging), [Bambu Lab wiki](https://wiki.bambulab.com/en/software/bambu-studio/parameter/bridge) |
| **tall and thin** | taller than three times its footprint | outer brim, cooling note | [OrcaSlicer wiki: brim](https://www.orcaslicer.com/wiki/print_settings/others/others_settings_brim) |
| **wide and flat** | over 40 cm2 on the bed and under 6 mm tall | outer brim (8 mm), warping notes | same, plus a Prusa forum case |
| **flat top** | 3 cm2 or more at the highest point | ironing on the topmost surface, with solid layers under it | [OrcaSlicer wiki: ironing](https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_ironing) |
| **fits** | the part is functional | a question about mating parts, and Orca's tolerance test to set hole compensation | [OrcaSlicer wiki: tolerance](https://github.com/OrcaSlicer/OrcaSlicer/wiki/tolerance_calib) |

**Four trust levels.** `sourced`: a page gives the value or the mechanism. `disputed`: sources disagree, the more conservative side is applied and both are shown. `heuristic`: this project's own threshold. `unverified`: reported but not confirmed from a real page, so it is shown as a suggestion and **never applied**. The tests enforce that, and also that every setting written is a name that really exists in OrcaSlicer 2.4.2 (a misspelled key is ignored silently by the slicer).

**Disagreements found while gathering this, and how they were settled:**

| Question | The two sides | What the script does |
|---|---|---|
| Best wall order for a smooth surface | the wiki calls inner, outer, inner the best; OrcaSlicer's own help text says the *precise wall* option is ignored in that order | keeps the default order with precise wall on, and leaves inner, outer, inner as an A/B test |
| 0.08 mm layers | usable (Obico) against blisters and artifacts on a Bambu printer, 0.12 more reliable ([forum](https://forum.bambulab.com/t/surface-problem-at-0-08-height/53851)) | 0.12, and 0.08 only by comparing slices |
| Arachne or Classic on tiny detail | better on text and thin walls, against reports of lumpy results | Arachne, with the advice to slice both when a detail looks wrong |
| Support Z distance | 0.2 mm at 0.2 layers against 50 to 75% of the layer height (Prusa) | keeps the profile default |
| Slow down for curled perimeters on domes | cools overhangs, against choppy speeds and artifacts ([issue 9480](https://github.com/OrcaSlicer/OrcaSlicer/issues/9480)) | not changed; worth an A/B on a dome |

**Not confirmed, so only suggested:** elephant-foot compensation values, cooling numbers for small parts, the 0.2 mm nozzle's behaviour on a P2S after a recent firmware, hole-compensation starting values, and any universal snap-fit gap.

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
