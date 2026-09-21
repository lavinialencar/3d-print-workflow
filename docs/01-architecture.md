# Architecture: what runs where, and why

![What runs where](../assets/architecture.svg)

The whole design rests on four decisions. Knowing them lets you change the parts without breaking the whole.

## 1. Everything stays on your network

The assistant, the slicer and the monitor run on your computer. They reach the printer over your **local
network** (for a Bambu Lab printer, in LAN Only mode; for Klipper or OctoPrint, their own web API). The only thing that leaves your house is a small push
notification, sent through [ntfy](https://ntfy.sh).

| Link | Bambu Lab | Klipper / OctoPrint | Who uses it |
|---|---|---|---|
| Slicer to printer, send a job | FTPS, port 990 | the printer's own upload | the slicer |
| Monitor to printer, read state | MQTT over TLS, port 8883 | HTTP JSON API (Moonraker `7125`, OctoPrint `80`) | `print_monitor.py` |
| Camera | RTSP over TLS, port 322 | the web UI's stream | the slicer or web UI |
| Monitor to phone | HTTPS to ntfy | HTTPS to ntfy | `print_monitor.py` |

## 2. The monitor is plain Python, not the assistant

You could ask an AI assistant to poll the printer on a schedule. Do not: every poll would cost tokens and
every hiccup would need a whole session. Instead `print_monitor.py` is under 200 lines of standard-library
Python, run by the operating system's scheduler. The assistant is needed only when **you** ask for something.

## 3. A thin conductor skill, and a knowledge base in plain notes

The assistant needs three kinds of information, and they change at different speeds:

| Kind | Example | Where it lives | Changes |
|---|---|---|---|
| **Order and rules** | "never start a print", "explain every decision" | the conductor skill (~60 lines) | almost never |
| **Knowledge** | your printer, tolerances, defaults | knowledge base notes | now and then |
| **Data** | grams used, the queue | the same notes, different files | every print |

Keeping the skill thin means it is cheap to load into every session and hard to let rot. The facts live in
notes you can read, edit, search and version yourself. See [09-the-conductor-skill](09-the-conductor-skill.md).

## 4. Secrets never enter the repository or the notes

The printer's access code gives full LAN control, and on public ntfy.sh the topic name is the only password.
Both live in `~/.config/print-workflow/`, outside any synced folder. See [11-privacy-and-publishing](11-privacy-and-publishing.md).

## The parts, and what each one is for

| Part | What it does | Replaceable by |
|---|---|---|
| **Claude Code** | runs the skills, talks to the CAD tool | any agent that can run scripts and use MCP |
| **CAD tool + local MCP server** | lets the assistant create and edit geometry | Autodesk Fusion's local MCP server was used here; any CAD with a scripting or MCP interface can play the role, or model by hand |
| **OrcaSlicer** | slices, and sends the job over the LAN | PrusaSlicer and CuraEngine also work with the `gcode` skill; Bambu Studio can send but its command line is less reliable |
| **`gcode` skill** | slices from the command line and validates the G-code | running the slicer by hand |
| **`print_monitor.py`** | reads the printer's state through a small adapter and turns changes into pushes | a Home Assistant automation, a Node-RED flow... |
| **Printer adapter** | translates one printer family into a shared vocabulary (`bambu` uses the `bambu-labs` skill; `moonraker` and `octoprint` are plain HTTP) | your own, see [05](05-other-printers.md#adding-your-own-printer) |
| **ntfy** | delivers the push | Pushover, Telegram, email, a self-hosted ntfy |
| **Knowledge base** | remembers your printer and your history | any folder of Markdown files |

## What is deliberately not automated

Starting a print. Sending is a click you make; starting is a tap on the printer's own screen. A print that
starts by itself while nobody is next to the machine is a fire risk, and the cost of asking for one tap is tiny.

## Growing it: from a laptop to a home server

The monitor is the one part that benefits from an always-on machine: on a laptop it only works while the
laptop is awake. Because it is plain Python with no state beyond one small JSON file, it moves cleanly to a NAS or
a Raspberry Pi, usually as a container. What to carry over, and what to decide first, is in
[07-monitor-and-alerts](07-monitor-and-alerts.md#moving-it-to-an-always-on-machine).
