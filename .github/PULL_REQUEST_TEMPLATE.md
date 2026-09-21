## What and why

<!-- One or two sentences. Link the issue if there is one. -->

## How I tested it

<!-- Printer model and firmware, OS, slicer version. If you could not test on hardware, say so. -->

## Checklist

- [ ] `python3 tools/scan_personal_data.py` prints `clean`
- [ ] `python3 -m unittest discover -s tests` passes
- [ ] No access code, ntfy topic, IP, MAC, serial number, account id, e-mail or home path anywhere, including in screenshots and logs
- [ ] New logic has tests on **synthetic** data
- [ ] If I changed what is verified, I updated the status table in the README and the changelog
- [ ] Nothing in this change can start, pause or cancel a print without an explicit, opt-in flag
