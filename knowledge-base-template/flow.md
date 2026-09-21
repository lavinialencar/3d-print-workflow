# Printing flow, the hub

**Version 1, `<DATE>`.** The map of the printing workflow: what each tool does, where things live,
what is tested and what is not. The conductor skill reads this file first.

## Map: where things live

| I need | It is in |
|---|---|
| my printer, bed, plate, material, slicing defaults | `printer-profile.md` |
| how to model and deliver a part | `modeling-method.md` |
| spools, usage per print, monthly stats | `filament-log.md` |
| what to print next, naming convention | `print-queue.md` |
| slicer filament profiles (backup + how to reinstall) | `<PATH_TO_PROFILE_BACKUP>` |
| the printer's IP and access code or API key | `~/.config/print-workflow/` (`bambu-printers.json` or `printer.json`), **outside** any synced folder |
| notification channel | `~/.config/print-workflow/ntfy.json`, **outside** any synced folder |

## The cycle

```
1  Model      <CAD_TOOL>: model the part (you, or the assistant through a connector)
2  Export     STL or 3MF, millimetres
3  Check      mesh check + conference board PNG + dfam-check
4  Slice      OrcaSlicer, printer profile + your filament profile
5  Send       from the slicer (or the printer's screen)
6  Monitor    printer screen, slicer device tab, print_monitor.py alerts
7  Log        grams, outcome, spool -> filament-log.md
```

## Tools

| Tool | Job | How to use |
|---|---|---|
| `<CAD_TOOL>` | model | `<notes: open document, connector name, port>` |
| OrcaSlicer `<VERSION>` | slice | `<printer, nozzle, process, filament>` |
| `gcode` skill | slice and validate from the command line | needs a profile wrapper JSON, see docs/04 |
| `bambu-labs` skill (Bambu only) | read printer state over LAN | read-only use only; never start prints |
| `print_monitor.py` | push alerts | schedule with launchd |

## Tested state (date every line)

**Tested:**
- `<DATE>` `<what you verified yourself>`

**Not tested yet:**
- `<things that exist but you have not seen work>`

## Pitfalls that already cost time

- `<pitfall>` and the fix
