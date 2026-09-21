# Troubleshooting

Find your symptom, read the likely cause, do the check. Ordered roughly by how often each one happens.

## The printer does not answer

| Symptom | Most likely cause | Check |
|---|---|---|
| `status` times out; `ping` gets no reply | **The printer is powered off**, or off the Wi-Fi | Look at it. It takes about a minute to boot and rejoin the network |
| `ping` fails and the address shows `(incomplete)` in `arp -a` | Nothing owns that IP right now | Powered off, or its IP changed. Read the IP on the printer's LAN screen |
| `ping` works, port 8883 refuses | LAN Only or Developer Mode is off | Check the two switches on the printer screen |
| It worked yesterday, not today | The router gave it a different IP | Reserve the IP ([02](02-network-and-fixed-ip.md#reserve-the-ip-in-your-router)) |
| It answers from the slicer but not from your terminal | macOS Local Network privacy for the app that runs your terminal | Compare: does `ping` to your **router** work from the same terminal? If yes, the network is fine |

A quick network test that separates "the network is broken" from "the printer is off":

```bash
ping -c 2 <router-ip>        # should answer; if not, the problem is your computer or Wi-Fi
ping -c 2 <printer-ip>       # if the router answers and this does not, the printer is the one that is silent
nc -z -G 3 <printer-ip> 8883 && echo "MQTT port open"
```

## The monitor

| Symptom | Cause | Fix |
|---|---|---|
| `bambu_lan_print.py not found` | the `cad` plugin is not installed, or is somewhere unusual | install it, or pass `--bambu-script <path>` / set `BAMBU_LAN_SCRIPT` |
| It runs by hand but the scheduled job does not | the script sits in a cloud-synced folder and launchd cannot read it | `python3 scripts/print_monitor_launchd.py status`, check the log, copy the script to `~/.local/bin` and reinstall with `--script` |
| No push arrives | the phone subscription does not match the topic (server, spelling, quotes) | send the one-off test push from [07](07-monitor-and-alerts.md); a `200` means the channel is fine and the subscription is wrong |
| Two pushes for everything | two schedulers are running (for example laptop and NAS) | uninstall one |
| I never get "print finished" | the state went `RUNNING` to `IDLE` and skipped `FINISH` between two readings | lower `--interval`; a print state shorter than one interval can be missed |

## Klipper and OctoPrint (experimental adapters)

| Symptom | Cause | Fix |
|---|---|---|
| `no host in .../printer.json` | the config file is missing or has no `host` | copy the matching example from `config/` and fill it in |
| `URLError` or `timed out` | wrong address or port, or the service is down | open the same URL in a browser; Moonraker is usually port `7125`, OctoPrint port `80` |
| HTTP 401 or 403 | missing or wrong API key, or your computer is not a trusted client | set `api_key`, or add your computer to Moonraker's `trusted_clients` |
| `response had no usable state` | an unexpected reply, or OctoPrint reports `Offline` | check the printer is connected inside OctoPrint; then report it, because a parser may need a case |
| OctoPrint never says finished | it has no explicit finished state | the adapter reports `Operational` at 100% completion as FINISH; a print cancelled early will not |

## OrcaSlicer and profiles

| Symptom | Cause | Fix |
|---|---|---|
| A copied filament profile never shows up | missing `version` (trap 1) | use `studio_to_orca_filament.py`; confirm with the log line `loaded N presets` |
| It shows up but the AMS list does not offer it | a child profile carries its parent's `filament_id` (trap 2) | build a **standalone** profile with the script |
| Command-line slicing aborts with `Assigning from an empty vector` | paired or `nil` values (trap 3) | same script |
| I edited Orca's config while it was open and it reverted | Orca rewrites its config on quit | quit with Cmd+Q **first**, edit, then reopen |
| Cmd+W closed the window but the app is still running | on macOS the app keeps living | Cmd+Q, or Dock, right click, Quit |
| The send dialog hangs after the access code | [reported for the P2S](https://github.com/OrcaSlicer/OrcaSlicer/issues/12621) | confirm LAN Only + Developer Mode; otherwise export the sliced 3MF and send it another way |

## The assistant and the CAD connector

| Symptom | Cause | Fix |
|---|---|---|
| Connector shows `ConnectionRefused` | the CAD app is closed, so its local server is not running | open the app **with a document active**, then start a new session |
| `claude mcp add` worked but the tools are missing in another folder | it was registered at **local** scope, tied to one folder | add it again with `--scope user` |
| New tools do not appear | servers are loaded when a session starts | start a **new** session |
| The skill does not trigger | the description does not match how you asked, or it was added mid-session | new session; sharpen the `description:` line |

## The print itself

| Symptom | Likely cause | What to look at |
|---|---|---|
| Paused with `HMS 0700 8006` | the AMS could not feed filament into the toolhead | filament tip, PTFE tube at the toolhead, spool tangle, clog. If it repeats at colour changes, the feed path of those slots |
| Corners lifting in the first layer | poor bed adhesion, common on cold plates with small bases | clean the plate, add a brim, enlarge the base in the model |
| Parts came out solid instead of hollow | the mesh check was skipped | compare `volume` with the bounding box ([08](08-modeling-and-delivery.md)) |

Decode any error code with the snippet in [07](07-monitor-and-alerts.md#understanding-an-error-code) and look it up in
[Bambu's HMS list](https://wiki.bambulab.com/en/hms/error-code).

## Still stuck?

Open an issue with the **redacted** output of the failing command. Before you paste anything, remove your IP, MAC, serial number, access code and
ntfy topic. See [11](11-privacy-and-publishing.md).
