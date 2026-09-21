# Other printers: Klipper, OctoPrint, and adding your own

The workflow does not care which printer you have. Modeling, checking, recommending and slicing work with any printer a slicer supports. The one
part that is printer-specific is **reading the printer's state** for alerts, and that is a small adapter.

| Family | Backend | Status | What it needs |
|---|---|---|---|
| Bambu Lab | `bambu` | ✅ verified on a P2S | LAN Only + Developer Mode, see [03](03-bambu-lab-track.md) |
| Klipper (Moonraker) | `moonraker` | 🟡 experimental | Moonraker reachable on your network |
| OctoPrint | `octoprint` | 🟡 experimental | an OctoPrint API key |
| Anything else | your own | ⚪ contribute it | see the end of this page |

> **Experimental** means the parsing is unit-tested against sample payloads that follow the projects' public API documentation, and **has not been run on a real
> Klipper or OctoPrint printer** by the author. If you try it, please report what happened (there is an issue template for that).

## Klipper with Moonraker

Moonraker is the API server most Klipper setups (Mainsail, Fluidd) already run.

1. Find your printer's address and reserve it: [02](02-network-and-fixed-ip.md).
2. Check that Moonraker answers. It usually listens on port `7125`:

```bash
curl -s "http://<printer-ip>:7125/printer/objects/query?print_stats&virtual_sdcard"
```

You should see JSON with `print_stats` and a `state` such as `standby` or `printing`. If Moonraker only accepts trusted clients, add your
computer to its `trusted_clients`, or use an API key.

3. Create the config, outside the repository:

```bash
mkdir -p ~/.config/print-workflow && chmod 700 ~/.config/print-workflow
cp config/printer.moonraker.example.json ~/.config/print-workflow/printer.json
chmod 600 ~/.config/print-workflow/printer.json
open -e ~/.config/print-workflow/printer.json
```

4. Try it:

```bash
python3 scripts/print_monitor.py --print-status
```

How Moonraker's states map: `standby` to IDLE, `printing` to RUNNING, `paused` to PAUSE, `complete` to FINISH, `error` to FAILED, `cancelled` to CANCELLED.

## OctoPrint

1. In OctoPrint, create an **API key** (Settings, Application Keys, or the older global key).
2. Check it works:

```bash
curl -s -H "X-Api-Key: <your-key>" "http://<printer-ip>/api/job"
```

3. Create the config:

```bash
mkdir -p ~/.config/print-workflow && chmod 700 ~/.config/print-workflow
cp config/printer.octoprint.example.json ~/.config/print-workflow/printer.json
chmod 600 ~/.config/print-workflow/printer.json
open -e ~/.config/print-workflow/printer.json
```

An API key is a password: keep it out of notes, chats and repositories.

OctoPrint has no explicit "finished" state, so the adapter reports `Operational` with 100% completion as FINISH, and `Operational` otherwise as IDLE.

## Slicing and everything else

Steps 1 to 4 and 7 of the workflow (model, check, recommend, slice, log) do not depend on the printer. The `gcode` skill drives OrcaSlicer, PrusaSlicer or
CuraEngine, and needs a small profile wrapper with your bed size; see [06](06-slicing-with-an-assistant.md). Sending a job is whatever your printer
normally does (OctoPrint's upload, Mainsail, the slicer's own send button).

## Adding your own printer

The monitor is built around one idea: every printer family is translated into the same small vocabulary.

```python
# The neutral reading every adapter produces:
{"state": "RUNNING",          # IDLE | PREPARING | RUNNING | PAUSE | FINISH | FAILED | CANCELLED
 "job": "part.gcode", "percent": 42,
 "layer": 12, "total_layers": 80,      # None if unknown
 "remaining_min": 55,                   # None if unknown
 "error": None}                         # short text, or None
```

To add a family:

1. Write `normalize_<name>(payload)` in `scripts/print_monitor.py`: a **pure function** that takes the raw API response and returns that dictionary
   (or `None` when the response has no usable state). Do not put the network call inside it.
2. Add a reader that fetches the payload, and add the name to `BACKENDS`.
3. Add tests in `tests/test_scripts.py` with a **sample payload** copied from the API documentation. Redact anything personal first.
4. Add a row to the table above and to the README status table, and mark it experimental until someone has run it on hardware.

Pure normalizers keep the decisions ("alert on a change of state", "warn once when the printer goes silent") identical for every printer, and testable
without one.

Next: [06 Slicing with an assistant](06-slicing-with-an-assistant.md).
