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

### What the part is for (`--use`)

A mesh cannot say that a plaque carries text, that a joint must move, or that a box holds water. That is the owner's answer, given with `--use` or asked as a question
when the part is unlabelled. An open container is the one thing geometry can honestly suggest (floors below the rim, mostly air), so that one is detected.

```bash
python3 scripts/analyze_part.py horse.stl --finish smooth --use flexi,multicolor
python3 scripts/analyze_part.py bin.3mf --purpose load --use container
```

| Use | Applied for you (smooth finish shown) | Notes only | Trust of its rules |
|---|---|---|---|
| **text** (text, plaque, keychain, nameplate) | `ironing_type = topmost`, `ironing_flow = 10%`, `ironing_spacing = 0.1`, `ironing_speed = 20` | 2 | disputed 2, sourced 4 |
| **multicolor** (several colours with the AMS) | notes only | 5 | disputed 1, sourced 3, unverified 1 |
| **flexi** (print-in-place, articulated, flexi toys) | layer 0.16 mm; `enable_support = 0`, `wall_loops = 3`, `elefant_foot_compensation = 0.2`, `outer_wall_speed = 50`, `initial_layer_speed = 20`, `bridge_flow = 0.95`, `brim_type = outer_only`, `brim_width = 4` | 2 | disputed 2, heuristic 1, sourced 7 |
| **fit** (mates with another part: snap, press fit, screw boss) | `wall_loops = 4` | 4 | disputed 1, heuristic 1, sourced 2, unverified 1 |
| **container** (box, organizer, tray, bin, lid) | `wall_loops = 3`, `sparse_infill_density = 12%` | 2 | sourced 3, unverified 1 |
| **watertight** (holds liquid, leak-proof) | layer 0.16 mm; `wall_loops = 4` | 1 | disputed 1, sourced 1 |
| **vase** (spiral vase) | layer 0.2 mm; `spiral_mode = 1` | 0 | sourced 1 |
| **figurine** (figurine, miniature, organic model) | layer 0.12 mm; `support_type = tree(auto)`, `support_style = organic`, `enable_support = 1`, `support_interface_top_layers = 2` | 4 | disputed 2, sourced 5, unverified 1 |
| **bracket** (hook, bracket, wall mount, load-bearing) | `wall_loops = 6` | 1 | disputed 1, sourced 1 |
| **lithophane** (lithophane or part seen against light) | layer 0.12 mm; `sparse_infill_density = 100%` | 1 | disputed 2 |

Highlights the numbers cannot show: text wants strokes at least 1.0 mm wide on a 0.4 mm nozzle; a print-in-place joint starts at 0.25 mm of clearance per side (sources
range from 0.1 to 0.5); an M3 heat-set insert wants a 4.2 mm hole as printed; a lid on a box takes 0.2 mm per side for a friction fit; coloured text wants at least 0.6 mm of depth.
Every rule, its source and its status print with the report.

### The machine side, which no shape can fix

Some quality lives in the printer and the filament profile: `python3 scripts/analyze_part.py --machine` prints the checklist with a source and a trust level on each line. The
short version: a filament profile copied from another slicer is a starting point, so flow ratio, max volumetric speed and temperature must be re-run on this printer, in the
Orca wiki's order (temperature, max volumetric speed, pressure advance, flow, retraction). A Bambu printer already calibrates its own flow dynamics and vibration compensation;
in Orca's calibration dialogs the flow calibration is switched off for it. Ringing, banding and arc fitting are covered there too, with the disagreements written down.

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

> **Read [06](06-slicing-with-an-assistant.md#pitfall-the-command-line-does-not-resolve-profile-inheritance-like-the-gui-and-the-fix-that-closes-it) first.**
> Comparing scenarios is only meaningful if the command-line slice matches what the GUI would produce; `fix_bambu_machine_profile.py` closes the gap
> for a Bambu printer. Verify it once with `gcode_settings_diff.py`.

## Two cases the shape alone does not solve

### A part that needs support: support fins

Instead of the slicer's tree or grid support, the support becomes part of the mesh: thin fins that hold the part and break off clean.
The idea comes from Slant 3D; [`printfins.com`](https://printfins.com) automates it, free, open source, running in the browser (the file never leaves
your computer). Think of it when a part must print tilted for strength (layers crossing the load, like a 45° wall bracket) and would be weak lying flat.

Three pieces, and it fails without any of them:

1. **A bed pad.** Without it the tilted part has nothing to stand on and tips over.
2. **Tines.** Small teeth that fuse the fin to the side of the part and lock it in place. Without them the fin only leans, the part moves and the print fails.
   They leave a small mark.
3. **The slicer's support turned off**, or it adds a tree on top of the fins.

Export as 3MF and fins and part come in as separate objects, so you can switch the fins off and slice the slicer-support version of the same plate to
compare time and grams. The author's own numbers (a few grams on a cube, hundreds of grams and many hours on a large part) are not verified here.
**State: not yet tested in this workflow.**

### A thin tip that comes out melted

A cone, a pin, the top of a tower: the tip comes out soft and deformed even with the part-cooling fan at 100%. The cause is layer time. At the tip each
layer takes a fraction of a second, too little for PLA to cool before the next one lands. The filament profile's *minimum layer time* tries to slow down,
but only down to the *minimum print speed*, and the tip is already there.

- **Do not** lower the minimum print speed: the nozzle lingers on hot plastic and you trade the melted tip for heat creep.
- **Do** give each layer more time to cool: print another part on the same plate, or add a small sacrificial tower beside it.
- Speed-up recipes that raise the minimum speed and cut the minimum layer time make this defect worse on any part with a tip.

In step 2, when the model or the analyzer shows a narrow tip near the top, ask: "will there be another part on the plate? if not, a sacrificial tower?".
**State: not yet tested in this workflow.**

## Lesser-known OrcaSlicer settings worth knowing

From The Next Layer's "Orca Slicer just added a ton of useful features" (YouTube `-EwyMzNSIOE`, Sep 2025). The creator had not tested
several of them, and none is print-proven in this workflow yet, so the analyzer never applies them; the assistant may suggest one
when the case shows up. Find each with the slicer's search box rather than by tab.

| Case | Setting | What it does |
|---|---|---|
| Automatic supports keep supporting bridges | don't support bridges | keeps auto supports, skips bridges, no painting or blockers |
| Downward-facing counterbored hole | bridge counterbore holes (sacrificial layer or partial bridge) | the Voron trick, applied to any downloaded model |
| A hole that must be exact | polyholes | prints the circle as a polygon of straight segments |
| A height that must land exactly (e.g. 20.05 mm) | precise Z height | makes the last layer thinner instead of rounding down |
| Tiny gaps in sharp corners of top and bottom layers | small area flow compensation | raises flow where the line is too thick to fill |
| Stringing from the prime tower, or warping | per-object skirt and draft shield | the shield catches strings and backs up a detached prime tower |
| A bridge the slicer will not do, or a set angle | bridge infill direction | fixes the bridge angle |
| Scarring where supports touched | ironing support interfaces | smoother support contact surface |
| Magnet holes in a part you will glue instead | close holes | ignores holes in X and Y |
| A stronger open mesh (grille, sieve) | infill multi-line | thicker infill lines without changing the openings |
| Two materials that do not bond | beam interlocking | stitches the materials together in X, Y and Z |

Quality of life: the plate lock icon keeps auto-arrange off a plate; preferences can skip the STEP resolution dialog, set how a 3MF
opens ("ask when relevant" only asks when the file holds more than geometry; "geometry only" drops its print settings) and skip the
home tab.

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
