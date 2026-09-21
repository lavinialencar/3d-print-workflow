# The monitor and the alerts

Nobody watches a print for hours. `scripts/print_monitor.py` tells your phone when it starts, ends, fails or pauses, using nothing but your local network and a
free notification service.

It matters most for Bambu Lab owners: LAN Only mode switches off the Bambu Handy app, and with it the push notifications, so this replaces them.
It also works with Klipper (Moonraker) and OctoPrint; see [05](05-other-printers.md).

| Backend | Status |
|---|---|
| `bambu` | ✅ verified on a P2S |
| `moonraker` | 🟡 experimental, unit-tested on sample payloads |
| `octoprint` | 🟡 experimental, unit-tested on sample payloads |

## What it tells you

| You get a push when... | Title | Priority |
|---|---|---|
| a print starts | Print started | low |
| a print finishes | Print finished | default |
| a print fails | Print failed | high |
| a print pauses (with the error code) | Print paused | high |
| the printer stops answering for 3 readings in a row | Printer not responding | default |

Rules that keep it from being annoying:

- It only speaks on a **change** of state. Sitting in the same state produces nothing.
- The **first** reading after installing never alerts; it just records where things are.
- The "not responding" alert fires **once**, then waits until the printer answers again before it can fire again.

**It is read-only.** It cannot start, pause or cancel anything. It never prints your access code.

## Set it up

### 1. Two private config files

```bash
mkdir -p ~/.config/print-workflow && chmod 700 ~/.config/print-workflow
cp config/ntfy.example.json ~/.config/print-workflow/ntfy.json

# pick the ONE that matches your printer:
cp config/bambu-printers.example.json    ~/.config/print-workflow/bambu-printers.json   # Bambu Lab
cp config/printer.moonraker.example.json ~/.config/print-workflow/printer.json           # Klipper
cp config/printer.octoprint.example.json ~/.config/print-workflow/printer.json           # OctoPrint

chmod 600 ~/.config/print-workflow/*.json
```

Edit them with `open -e <file>`: the printer's address and credentials in the first, your topic in `ntfy.json`.
Details and the reasons for keeping them out of any synced folder are in [`config/README.md`](../config/README.md).

### 2. A private ntfy topic

On the public ntfy.sh server, **the topic name is the only password**. Make it long and random:

```bash
python3 -c "import secrets; print('print-' + secrets.token_hex(10))"
```

Put the result in `ntfy.json`, then open the ntfy app on your phone, add a subscription, and enter the same
topic on the same server. Do not paste the topic into a chat, an issue or a screenshot.

### 3. Try it without sending anything

```bash
python3 scripts/print_monitor.py --print-status     # prints the parsed state, exits
python3 scripts/print_monitor.py                    # dry run: shows what it WOULD send
```

> **Checkpoint:** `--print-status` prints JSON with a `state`. If it says `no reading`, the printer is off,
> the IP or code is wrong, or the `bambu-labs` skill is missing. See [troubleshooting](10-troubleshooting.md).

### 4. Send one test push

```bash
python3 - <<'PY'
import json, os, urllib.request
c = json.load(open(os.path.expanduser("~/.config/print-workflow/ntfy.json")))
body = json.dumps({"topic": c["topic"], "title": "Monitor test", "message": "It works.", "priority": 3}).encode()
print(urllib.request.urlopen(urllib.request.Request(c["server"], data=body,
      headers={"Content-Type": "application/json"}), timeout=15).status)
PY
```

`200` and a notification on your phone means the channel is right.

### 5. Schedule it

```bash
python3 scripts/print_monitor_launchd.py print       # look at what it will create
python3 scripts/print_monitor_launchd.py install     # every 180 s, with --send
python3 scripts/print_monitor_launchd.py status      # state, runs, last exit code
```

`status` should show `last exit code = 0` after the first run. To remove it later:

```bash
python3 scripts/print_monitor_launchd.py uninstall
```

launchd is macOS's built-in scheduler. It costs no AI tokens, survives reboots, and only runs while the Mac is
awake. **If the repository sits in a cloud-synced folder** (Google Drive, iCloud), macOS privacy rules can block the
job from reading the script: check the log at `~/.config/print-workflow/monitor.log`, and if you see
"Operation not permitted", copy `print_monitor.py` somewhere like `~/.local/bin` and use `--script`.

The log gets one line per reading. Delete it now and then.

## Understanding an error code

When a print pauses or fails, the printer reports a code. The push shows the low 16 bits (for example `32774`), and the full
value is in `print_error`. Both are just one number written two ways. Decode it like this:

```python
code = 117473286                      # print_error, decimal
print(f"HMS {code >> 16:04X} {code & 0xFFFF:04X}")   # -> HMS 0700 8006
```

Look the result up in [Bambu's error code list](https://wiki.bambulab.com/en/hms/error-code). For example, `0700 8006` is
"failed to feed the filament into the toolhead", an AMS feed error. Reported causes: a deformed filament tip, a badly seated PTFE
tube at the toolhead, a clog, or a tangled spool. If the **same code repeats at colour changes**, look at the feed path of the
slots that print uses.

## Limits, honestly

- It only runs while the computer is awake and on the same network as the printer.
- A printer that is **powered off** cannot say so. You get one "not responding" push after 3 readings, not a stream of them.
- Readings take about 12 seconds each and arrive every 3 minutes, so a state that lasts under that can be missed.
- `ntfy.sh` is a free public service. Use a self-hosted ntfy if you want guarantees.

## Moving it to an always-on machine

The one weakness of a laptop is that it sleeps. The monitor is plain Python with one small state file, so it moves
cleanly to a NAS, a Raspberry Pi or any server on the same network. What to carry over and decide (an **untested sketch**, not a
supported path):

- The monitor script and the `bambu_lan_print.py` file it calls (it lives in the `cad` plugin's cache on your computer).
- The printer config, holding the access code, as a **container secret**, never in a repository.
- Where ntfy runs. Your own ntfy server on the home network only reaches your phone at home unless you add a VPN or expose it.
  Keeping `ntfy.sh` as the relay avoids that.
- **Turn off the laptop's scheduled job on the same day**, or every alert arrives twice.
