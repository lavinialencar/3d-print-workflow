# Printer profile and slicing defaults

**Version 1, `<DATE>`.** Facts about your hardware and your defaults. Slicing advice is a
starting point from community experience, never a substitute for a test print when a part is critical.

## Hardware

- Printer: `<MODEL>`, usable bed `<X x Y x Z mm>`. Always check a part's total size against this
  before delivering. If it does not fit, say so and suggest splitting it into interlocking parts.
- AMS: `<model or none>`
- Build plate: `<plate name and type>`. **Adhesion note:** `<e.g. tall parts with a small base are
  more likely to detach on a cold plate; consider a brim or a slightly larger base in the model>`
- Nozzle: `<diameter and material>`
- Filament: `<brand and type>`

| Filament parameter | Value |
|---|---|
| Nozzle temperature | `<range, recommended>` |
| Bed temperature | `<range, recommended>` |
| Retraction | `<distance and speed>` |

## Fit and tolerance (PLA, 0.4 mm nozzle, 0.2 mm layers, well calibrated)

Clearance **per side**; double it for the total gap between two parts.

| Fit | Clearance per side |
|---|---|
| Press fit | 0.0 to 0.1 mm |
| Snug, slight resistance | 0.1 to 0.15 mm |
| Sliding | 0.15 to 0.25 mm |
| Loose | 0.3 to 0.4 mm |
| Free rotation | 0.4 to 0.6 mm |

Your own measured values: `<...>`

## Slicing defaults

`<layer height / walls / infill / supports you use by default>`

## Format of the slicing recommendation (delivered with every new part)

Keep it short. Do not repeat your defaults; only list what **differs** for this part, each with
its reason and where to find it in the slicer:

```
Slicing recommendation for <part>:
- <setting>: <value>  (why; where: Process > Quality > ...)
- Orientation: <face on the bed>, because <reason>
- Supports: <yes/no/where>
- Adhesion: <brim or not>, because <reason>
```

## Community rules of thumb (verify on your machine)

- Overhang: below about 45 degrees usually prints clean; above about 50 degrees usually needs support.
- Bridging: 5 to 10 mm is the usual limit before supports or splitting.
- Vertical holes print smaller than nominal; for a critical diameter, print small and drill.
- Minimum hole diameter about 2 mm; below that, print without and drill.
- Tension should run parallel to the layers, never pull them apart.
