---
name: print-conductor
description: Conductor for a 3D printing workflow (any printer, with a Bambu Lab track; OrcaSlicer or another slicer, a CAD tool, filament tracking). Use when the user asks to model a part, recommend or review slicing settings, slice, send to the printer, monitor a print, or log filament use, or asks what is tested in the workflow. Runs the cycle in the right order, points to the user's knowledge base, and never starts a print by itself.
---

# Print conductor

A deliberately **thin** skill. The knowledge lives in your knowledge base (notes), not here.
This file only holds the order of the cycle and the rules that must never be forgotten.

> Customize before use: replace every `<PLACEHOLDER>`. See `docs/09-the-conductor-skill.md`.

Knowledge base folder: `<KNOWLEDGE_BASE>` (called `KB` below), for example the folder you created from
`knowledge-base-template/`.

## Step zero

Read `KB/flow.md`: the map of where things live, what is tested and what is not, and the known
pitfalls. Then read only the part each step asks for, never whole files.

## Fixed rules

1. **Never start a print.** Send a file only when the user explicitly asks and is next to the
   printer. Starting is done on the printer's screen. Never run a "start print" flag on your own.
2. **The printer's access code or API key never goes in chat, in a note, or in the repository.** It lives only
   in `<PRIVATE_CONFIG_DIR>` (for example `~/.config/print-workflow/`, permission 600), typed by the user.
3. **The user is learning.** Every slicing decision comes with the reason and where to find it in the
   slicer. Recommend first; apply only after the user has seen it.
4. **Say what was tested and what was not.** Never claim success without a reading or without the
   user having seen it.
5. Edit notes **in place**. Re-read a file right before writing. Never create a new file to update an
   existing one.

## The cycle

1. **Model.** Read `KB/modeling-method.md`: what to ask, what not to ask, print orientation,
   tolerances, bed limit. Tool: `<CAD_TOOL>` (for example the Fusion MCP server, which needs the
   app open with an active document; if the connection is missing, say so).
2. **Check.** Mesh verification (watertight, volume against the bounding box, size against the bed)
   and a **conference board PNG**; the `dfam-check` skill if available.
3. **Recommend slicing.** Read the slicing section of `KB/printer-profile.md`; give the
   recommendation in the format defined there. Only highlight what differs from the defaults.
4. **Slice.** The `gcode` skill with OrcaSlicer (or PrusaSlicer, CuraEngine): `inspect`, `slice --dry-run`, `slice --execute`,
   `validate`.
5. **Send.** Through the slicer, done by the user. Not verified by you unless a reading shows it.
6. **Monitor.** `scripts/print_monitor.py` (read-only; adapters for Bambu Lab, Klipper and OctoPrint), or, for Bambu,
   the `bambu-labs` skill `status` command. If the printer does not answer, it is off or off the network.
7. **Log.** Grams from `scripts/gcode_consumption.py`; outcome (success or cancelled) and spool come
   from the user or from the printer state. Add the row to `KB/filament-log.md` and update the
   project note with what worked.

## Honest state

Keep a short list here of what is tested and what is not, and always re-read the "tested state"
section of `KB/flow.md` before claiming anything.
