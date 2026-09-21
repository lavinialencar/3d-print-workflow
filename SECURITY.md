# Security policy

## Scope

This project is a set of scripts and documents that talk to a 3D printer on **your own network**. The security-relevant surfaces are:

- how the scripts handle the printer's **access code** and your **ntfy topic** (both are effectively passwords);
- anything that could make a script write, upload or start something on the printer (by design the monitor is **read-only**);
- personal data leaking into the repository through examples, logs or commits.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem.

Use GitHub's private reporting: on the repository page, **Security, Report a vulnerability**. Include what you found, how to reproduce it,
and what you think the impact is.

**Do not include real secrets in a report.** If you need to show a config file, replace the access code, topic, IP, MAC and serial number with
placeholders.

You can expect an acknowledgement within a few days. This is a small volunteer project, so fixes are best effort, but a report that shows a secret
being written to a log or sent somewhere unexpected will be treated as urgent.

## If you accidentally leaked something

- **Printer access code:** regenerate it on the printer (the circular-arrow icon beside it), then update your local config.
- **ntfy topic:** choose a new random topic, update `ntfy.json`, and resubscribe on your phone.
- Then remove the value from the repository **and its history**, see [docs/09](docs/11-privacy-and-publishing.md#if-something-leaks-anyway).

## Design choices that reduce risk

- The monitor never uploads a file and never starts, pauses or cancels a print.
- It never prints the access code, and the config files are created with permission `600`.
- Real config lives outside the repository; `.gitignore` and the CI secret scan act as a safety net.
- The conductor skill forbids starting a print by itself and forbids writing the access code anywhere.
