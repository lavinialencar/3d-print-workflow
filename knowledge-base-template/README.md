# Knowledge base template

Five plain Markdown files that give the conductor skill (and you) one place to look things up.
Copy this folder into your own notes (Obsidian, a Git repo, a synced folder, anything that holds
`.md` files), then fill in the `<PLACEHOLDERS>`.

| File | Job | Changes |
|---|---|---|
| [`flow.md`](flow.md) | The hub: map of where everything lives, the cycle, what is tested, pitfalls. The skill reads this first | often |
| [`printer-profile.md`](printer-profile.md) | Your hardware, material and slicing defaults, plus the format of the slicing recommendation | rarely |
| [`modeling-method.md`](modeling-method.md) | Checklist for modeling and delivering a part | rarely |
| [`filament-log.md`](filament-log.md) | Spools, per-print usage, monthly stats | every print |
| [`print-queue.md`](print-queue.md) | What to print next, in what order, with a naming convention | often |

## Rules that keep it from rotting

- **One home per fact.** If a fact lives in `printer-profile.md`, other files point to it, never copy it.
- **Update in place.** Do not create `notes-v2.md`. Edit the file and note the date inside it.
- **Date every claim about the state of things** ("tested 2026-09-20"). A note without a date
  cannot be trusted six months later.
- **No secrets.** Never write the printer's access code, your IP, or your ntfy topic in these
  files. They belong in `~/.config/print-workflow/` (see [`config/`](../config/README.md)).
