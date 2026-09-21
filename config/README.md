# config/

Example configuration files. **Copy them, never edit them in place, and never commit the real ones.**

| Example file | Real location (outside the repo) | What it holds |
|---|---|---|
| `bambu-printers.example.json` | `~/.config/print-workflow/bambu-printers.json` | printer IP and LAN access code |
| `printer.moonraker.example.json` | `~/.config/print-workflow/printer.json` | Klipper (Moonraker) host and port |
| `printer.octoprint.example.json` | `~/.config/print-workflow/printer.json` | OctoPrint host, port and API key |
| `ntfy.example.json` | `~/.config/print-workflow/ntfy.json` | ntfy server and your private topic |

`192.0.2.x` addresses are reserved for documentation (RFC 5737). Replace them with your printer's real IP.
Use only the file for **your** printer family; `printer.json` and `bambu-printers.json` are alternatives.

```bash
mkdir -p ~/.config/print-workflow && chmod 700 ~/.config/print-workflow
cp config/bambu-printers.example.json ~/.config/print-workflow/bambu-printers.json
cp config/ntfy.example.json           ~/.config/print-workflow/ntfy.json
chmod 600 ~/.config/print-workflow/*.json
open -e ~/.config/print-workflow/bambu-printers.json     # type your values; save with Cmd+S
```

Why these live **outside** the repository, and outside any cloud-synced folder:

- The **access code** (Bambu) or **API key** (OctoPrint) gives control of your printer.
- On the public ntfy.sh server the **topic name is the only password**: anyone who knows it can
  read and publish to it. Use a long random string, for example the output of
  `python3 -c "import secrets; print('print-' + secrets.token_hex(10))"`.

The `.gitignore` in this repository already blocks these filenames as a safety net, and the CI
runs a secret scanner on every push.
