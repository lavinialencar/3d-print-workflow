# Filament log

Plain Markdown on purpose: an assistant can edit it directly, and it diffs well.

Remaining weight is **not** computed automatically. Recalculate by hand at every update
(`remaining = nominal weight - used so far`), and now and then weigh a real spool and write
"weighed" if it disagrees, then adjust the nominal weight to recalibrate.

## Spools

| Spool ID | Brand | Color | Nominal (g) | Used so far (g) | Remaining (g) | % left | Weighed (g) | Weighed on |
|---|---|---|---|---|---|---|---|---|
| `<Brand-Color-01>` | `<brand>` | `<color>` | 1000 | 0 | 1000 | 100% | | |

## Usage log (one row per print)

The grams come from the slicer G-code (`scripts/gcode_consumption.py` prints a ready-made row).
**That number is the estimate for the whole part.** If the print was cancelled or failed, the real
use is lower, so mark it in the notes column.

| Date | Part | Spool ID | Grams (estimate) | Notes |
|---|---|---|---|---|
| `<YYYY-MM-DD>` | `<part>` | `<spool>` | `<g>` | `<success / cancelled / read from slicer G-code>` |

## Per month

| Month | Prints | Success | Cancelled | Grams (success only) |
|---|---|---|---|---|
| `<YYYY-MM>` | | | | |

## Where the outcome comes from

- The printer's own state report says `FINISH` or `FAILED` (the monitor sees it and alerts you).
- The slicer's **Device > Storage** tab lists the files on the printer, with time and grams, but it
  does **not** say whether a print finished. Use it as a source for grams, not for outcome.
