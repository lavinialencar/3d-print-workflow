# Privacy, secrets, and sharing your own setup

This repository is a **template**: a safe copy of a working personal setup, with everything personal removed. This page explains what
"personal" means here, how it was removed, and how to avoid leaking any of it if you fork this or publish your own.

## What can leak, and where it hides

| Item | Why it matters | Where it tends to hide |
|---|---|---|
| **Printer access code** | full LAN control of the printer | config files, shell history, pasted terminal output, screenshots |
| **ntfy topic** (public server) | it is the only password to your alerts | config files, pasted `curl` commands, docs |
| **IP and MAC address** | maps your home network | logs, router pages, `arp -a` output |
| **Printer serial number and device id** | identifies your device | the slicer's logs and the printer's status report (`sn`, `dev_id`) |
| **Account ids** | tie files to your Bambu account | user-folder names such as `BambuStudio/user/<number>/`, profile `.info` files (`user_id`, `setting_id`) |
| **Your e-mail and username** | identity | absolute paths (`/Users/<name>/...`), cloud-folder names like `GoogleDrive-<email>` |
| **Client and project names** | confidentiality | notes, examples, queue files |
| **Filament cost, order numbers** | financial detail | filament log |

The sneakiest are **absolute paths**: a path like `/Users/<name>/Library/CloudStorage/GoogleDrive-<email>/...` carries both your username and your e-mail address
and turns up in launchd files, skill files and logs.

## How this repository stays clean

1. **No real config.** Only `*.example.*` files, using the documentation-reserved address `192.0.2.10` (RFC 5737).
2. **`.gitignore`** blocks the real filenames as a safety net.
3. **Paths use `~` and `<PLACEHOLDERS>`**, never an absolute user path.
4. **Tests use synthetic data only**: no printer, no network, no personal file.
5. **CI runs a secret scanner** ([gitleaks](https://github.com/gitleaks/gitleaks)) on every push and pull request.
6. **Generated files** (a `.plist`, a log) are created on **your** machine and are never committed.

## Before you publish your own fork

Run this from the repository root. Replace the values with **yours**; do not put them in a file that gets committed:

```bash
# 1. things that should never appear anywhere
grep -rIn -i -E "your-username|your-email|<your-ip>|<your-mac>|<serial-prefix>" . --exclude-dir=.git

# 2. shape-based hints (no values needed)
grep -rIn -E "([0-9a-f]{2}:){5}[0-9a-f]{2}|192\.168\.[0-9]+\.[0-9]+|/Users/[A-Za-z0-9._-]+/" . --exclude-dir=.git

# 3. a real scanner, over the full history
gitleaks detect --source . -v
```

Also read every file **you added** with fresh eyes. A scanner finds patterns; it does not know your client's name.

### Git identity

Commits carry the author's name and e-mail **forever**. Use GitHub's private "noreply" address:

```bash
git config user.name  "Your Name"
git config user.email "<id>+<username>@users.noreply.github.com"   # GitHub, Settings, Emails, "Keep my email addresses private"
```

Set it **before** the first commit. Rewriting published history later is painful.

## If something leaks anyway

1. **Rotate first, clean later.** Regenerate the printer access code (the circular-arrow icon on the printer screen), pick a new ntfy topic,
   and update your local config. A leaked value is dead once it no longer works.
2. Remove it from the repository **and its history** (for example with `git filter-repo`), then force-push.
3. Assume any copy already fetched or cached is permanent, which is why step 1 comes first.

## Sharing the assistant's notes

If you use a knowledge base of notes and want to share parts of it, share the **method** and the **template**, not the notes: the notes are full of names,
dates and choices that are yours. The `knowledge-base-template/` folder shows the shape without the content.
