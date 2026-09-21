# The Bambu Lab track

Bambu Lab printers are excellent hardware in an ecosystem that is deliberately closed. Cloud accounts, a proprietary app, an authorization step for
third-party tools: fine until you want your own tools in the loop. This page is the pragmatic guide to doing that anyway.

> **Verified on a Bambu Lab P2S.** The X1, A1 and P1 families share the protocol, so this very probably applies, but it is untested here. Profile names and
> the AMS layout differ.

## What the closed ecosystem gets in your way

| You want | What happens | The way around | Where |
|---|---|---|---|
| Push alerts when a print ends | The Handy app does it, but only in cloud mode | Your own monitor over the local network | [07](07-monitor-and-alerts.md) |
| Send jobs from a third-party slicer | In cloud mode this goes through Bambu Connect, according to [Bambu's third-party page](https://wiki.bambulab.com/en/software/third-party-integration) | LAN Only + Developer Mode: direct, over your network | below |
| Read the printer's state from a script | Not offered in cloud mode | The same LAN access | [07](07-monitor-and-alerts.md) |
| Use a filament profile you built in Bambu Studio in Orca | It is silently ignored, or crashes command-line slicing | A converter script | [04](04-orca-and-bambu-studio-migration.md) |
| Have the AMS recognise your own profile | The parent profile's id wins | Standalone profiles | [04](04-orca-and-bambu-studio-migration.md) |
| Understand a pause code like `32774` | The screen says little | Decode it to an HMS code and look it up | [07](07-monitor-and-alerts.md#understanding-an-error-code) |
| Trust the slicer's project files | A known bug can duplicate an object almost exactly on top of the original | Look at the object list before slicing ([queue template](../knowledge-base-template/print-queue.md)) | reported in Bambu Studio's tracker, for example [#6424](https://github.com/bambulab/BambuStudio/issues/6424) |
| Slice in Orca with your printer's current profile | Orca's P2S profile lagged Bambu's for a while ([#11741](https://github.com/OrcaSlicer/OrcaSlicer/issues/11741)) | Use a recent Orca, and compare start G-code if in doubt | [06](06-slicing-with-an-assistant.md) |

None of this needs you to abandon the printer. It needs LAN Only mode, which is the next section.

## What LAN Only mode does, and what it costs

| | Cloud mode (default) | LAN Only mode |
|---|---|---|
| Bambu cloud account | used | **not used** |
| Bambu Handy app (remote camera, push notifications) | works | **stops working** (the printer's own screen says so) |
| Send a job from a third-party slicer | through Bambu Connect | direct, over your network |
| Read printer state from your own scripts | not possible | **possible** |
| Works away from home | yes | no |
| Firmware updates | automatic prompts | you handle them; check Bambu's wiki for the current procedure |

> **The trade-off, plainly:** you give up remote access and Handy's notifications, and you get a printer your own tools can talk to, that does not depend on a
> vendor's servers, and that is less exposed to the internet. This project replaces the lost notifications with its own monitor.

**You can undo it any time.** Switching LAN Only off returns the printer to the cloud. Developer Mode sits under LAN Only, so it switches off with it.

## Turn it on

On the printer's touchscreen, open the network settings and find **LAN Only**. Menu names vary a little between firmware versions. You will see three switches:

| Switch | What it does | Turn on? |
|---|---|---|
| **LAN Only** | cuts the cloud, enables local access | yes |
| **Developer Mode** | lets third-party tools connect without the vendor's authorization step | yes, for this project |
| **Liveview, LAN only** | serves the camera on your network | yes, if you want the camera in the slicer |

The screen then shows an **IP address** and an **access code**.

- The **IP** is not secret, but every script needs it. Reserve it: [02 Network basics](02-network-and-fixed-ip.md#reserve-the-ip-in-your-router).
- The **access code** is a password. Anyone on your network who has it can control the printer. If it leaks, regenerate it with the small circular-arrow
  icon next to it, then update your config file. Keep it out of notes, chats and repositories.

> **Checkpoint:** all three switches are green, and the screen shows an IP and a code.

## What talks to what

| Link | Protocol and port | Used by |
|---|---|---|
| Send a job | FTPS, 990 | the slicer |
| Read state | MQTT over TLS, 8883 | `scripts/print_monitor.py` |
| Camera | RTSP over TLS, 322 | the slicer's device tab |

> **Checkpoint:** `nc -z <printer-ip> 8883 && echo open` prints `open`.

## Configure the monitor for Bambu

```bash
mkdir -p ~/.config/print-workflow && chmod 700 ~/.config/print-workflow
cp config/bambu-printers.example.json ~/.config/print-workflow/bambu-printers.json
chmod 600 ~/.config/print-workflow/bambu-printers.json
open -e ~/.config/print-workflow/bambu-printers.json     # your IP and access code
python3 scripts/print_monitor.py --print-status
```

The monitor reads the printer through the `bambu-labs` skill of the open-source [text-to-cad](https://github.com/earthtojake/text-to-cad) project (MIT);
install its `cad` plugin following that project's README. Details in [07](07-monitor-and-alerts.md).

## Security notes

Everything in [02 Network basics](02-network-and-fixed-ip.md#security-notes) applies, and the access code deserves extra care: it gives full LAN control of
the printer.

Next: [04 Moving from Bambu Studio to Orca](04-orca-and-bambu-studio-migration.md).
