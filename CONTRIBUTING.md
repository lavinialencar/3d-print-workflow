# Contributing

Thank you for wanting to improve this. Three kinds of contribution are especially valuable:

1. **Compatibility reports.** "I ran this on an X1C / A1 / P1S / on Linux, and here is what worked." Use the *Tested on* issue template.
2. **Verifications.** Something the README marks 🟡 or ⚪ that you ran on real hardware.
3. **Fixes and new tools**, especially the roadmap items: a Linux scheduler, a tested container recipe, a mesh-check script.

## The one rule that matters most

> **Never commit personal data.** No access codes, ntfy topics, IP or MAC addresses, printer serial numbers, account ids, e-mail addresses, absolute
> home paths or client names, not even in an example, a screenshot, a log excerpt or a commit message.

Before every commit:

```bash
python3 tools/scan_personal_data.py       # must print "clean"
```

To also make sure your **own** specific values never slip in, pass them (they are never stored):

```bash
FORBID="your-username,your-ip,your-topic" python3 tools/scan_personal_data.py
```

Set your git identity to GitHub's private address **before** committing, as described in [docs/09](docs/11-privacy-and-publishing.md#git-identity).

## Running the tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tools/*.py
```

The tests use only synthetic data. They need no printer, no network and no personal file, and they must stay that way: a test that needs your printer
cannot run in CI. If you add a script, add tests for its pure logic.

## Code style

- Python 3.8+, **standard library only**. A new dependency needs a very good reason.
- Separate pure decisions from side effects (see `decide()` in `print_monitor.py`) so the logic is testable.
- Read-only by default. Anything that can change the printer or a file must be opt-in and loudly named.
- No secret in an argument, a log line or an exception message.

## Writing docs

- State what was **verified** and what was not. If you did not run it, say so.
- Every step ends with a checkpoint someone can check.
- Use `192.0.2.x` (documentation range) for IP examples and `<PLACEHOLDERS>` for anything personal. For an intentional fake that looks like a MAC or
  an address, add `scan-ignore` on the same line so the scanner knows.

## Pull requests

1. Keep them small and focused.
2. Fill in the checklist in the template. The scan and the tests must pass.
3. Say **how you tested it** and on what (printer model, firmware, OS, slicer version).
4. Update the README status table and the changelog if you changed what is verified.

## Reporting bugs

Use the issue templates. **Redact** the output of any command before pasting: remove your IP, MAC, serial number, access code and topic.
Security problems go through [SECURITY.md](SECURITY.md), not a public issue.
