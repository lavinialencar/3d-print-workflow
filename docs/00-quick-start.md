# Quick start: from zero to your first monitored print

**Time:** about 60 to 90 minutes the first time. **You need:** a 3D printer on your network (Bambu Lab, Klipper or OctoPrint), a Mac
(the scheduler is macOS; the scripts are portable), and some patience.

Every step ends with a **checkpoint**: a command or a sight that proves the step worked. Do not move on until the checkpoint passes. Most people who get
stuck skipped one.

```
 1 Printer      2 Network     3 Slicer       4 Assistant    5 Monitor      6 Notes
 reachable  --> fixed IP  --> Orca + your -->  CAD + skill --> alerts   --> knowledge
 from scripts                 profiles                                       base
```

## Pick your track

| You have | Read for step 1 | Extra reading |
|---|---|---|
| **Bambu Lab** (P2S verified; X1, A1, P1 untested) | [03 The Bambu Lab track](03-bambu-lab-track.md) | [04 Studio to Orca migration](04-orca-and-bambu-studio-migration.md) |
| **Klipper** (Moonraker) or **OctoPrint** | [05 Other printers](05-other-printers.md) | |

The Bambu track is the longest, because that ecosystem is the most closed. Everything else in this guide is the same for every printer.

## Before you start

| You need | Why | Check |
|---|---|---|
| macOS | the scheduler is written for it; Linux can adapt the scripts | `uname` prints `Darwin` |
| Python 3.8+ | all scripts use only the standard library, except the part analyzer (`numpy`) | `python3 --version` |
| OrcaSlicer 2.4+ (or PrusaSlicer, Cura) | the slicer with a command line | installed |
| Claude Code | drives the CAD tool and the skills (optional for alerts only) | `claude --version` |
| A phone with the ntfy app | receives the alerts | installed from your app store |

## Step 1: make the printer reachable (10 to 20 min)

- **Bambu Lab:** turn on **LAN Only** and **Developer Mode**, and note the **IP** and **access code**. LAN Only switches off the Bambu cloud and the Handy
  app, which is a real trade-off: read [03](03-bambu-lab-track.md) first.
- **Klipper or OctoPrint:** make sure the web API answers, and get an API key if needed: [05](05-other-printers.md).

> **Checkpoint 1:** you have the printer's IP and, if required, a code or key, and you know where each was shown.

## Step 2: give the printer a fixed address (10 min)

Reserve its IP in your router so it never changes: [02 Network basics](02-network-and-fixed-ip.md#reserve-the-ip-in-your-router).

> **Checkpoint 2:** `ping <printer-ip>` answers, and the printer's port is open (`nc -z <printer-ip> 8883 && echo open` for Bambu).

## Step 3: slicer and profiles (15 min)

Install OrcaSlicer, pick your printer and nozzle. If you are moving from Bambu Studio, convert your filament profile with
`scripts/studio_to_orca_filament.py`: it avoids three silent traps ([04](04-orca-and-bambu-studio-migration.md)).

> **Checkpoint 3:** your filament profile appears in the slicer's list, and slicing a test cube works.

## Step 4: connect the assistant (20 min, optional)

Install the `cad` plugin (it provides the `gcode` and `dfam-check` skills, and `bambu-labs` for Bambu), enable your CAD tool's local MCP server, register it
with Claude Code **at user scope**, and copy the conductor skill. See [01 Architecture](01-architecture.md) and [09 The conductor skill](09-the-conductor-skill.md).

> **Checkpoint 4:** `claude mcp list` shows your CAD server as connected, and the `print-conductor` skill appears in a new Claude Code session.

## Step 5: turn on the alerts (15 min)

Put your printer details and a private ntfy topic in `~/.config/print-workflow/`, subscribe on your phone, run the monitor once in dry-run mode, then schedule it.
All in [07 The monitor and alerts](07-monitor-and-alerts.md).

> **Checkpoint 5:** a test push reaches your phone, and `python3 scripts/print_monitor.py --print-status` prints the printer's state.

## Step 6: start your notes (10 min)

Copy `knowledge-base-template/` into your notes, fill in your printer profile, and point the skill at it.

> **Checkpoint 6:** the skill's "step zero" file (`flow.md`) exists and has your printer in it.

## Now print something small

Model or download a small part, let the assistant recommend the slicing, slice, send, and start it on the printer's screen. You will get a push when it starts,
and another when it ends or breaks. For a feel of what that looks like, read the [illustrative session](examples/example-session.md).

Something went wrong? See [10 Troubleshooting](10-troubleshooting.md).
