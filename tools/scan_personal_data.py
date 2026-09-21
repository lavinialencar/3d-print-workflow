#!/usr/bin/env python3
"""scan_personal_data.py - fail if the repository contains things that look personal.

It looks for SHAPES, so it needs no knowledge of your secrets:
  - private IPv4 addresses (other than the documentation range 192.0.2.x)
  - MAC addresses
  - absolute home paths such as /Users/<name>/ or /home/<name>/
  - e-mail addresses (other than noreply and example domains)
  - cloud-folder names that embed an e-mail (GoogleDrive-<email>)
  - ntfy-style topics ("print-" or "p2s-" followed by 16+ hex characters)
  - long random-looking tokens assigned to secret-ish keys

You can ALSO pass exact strings you want to be sure never appear (your username, your IP...)
with --forbid or the FORBID environment variable (comma separated). Those never get stored.

Usage
    python3 tools/scan_personal_data.py                       # scan tracked + untracked files
    python3 tools/scan_personal_data.py --forbid "jane,10.0.0.7"
Exit code 0 = clean, 1 = findings.
"""
import argparse
import os
import re
import subprocess
import sys

SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", "node_modules"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".3mf", ".stl", ".gcode"}

PRIVATE_IPV4 = re.compile(r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b")
MAC = re.compile(r"\b(?:[0-9A-Fa-f]{1,2}:){5}[0-9A-Fa-f]{1,2}\b")
HOME_PATH = re.compile(r"(?:/Users/|/home/)(?!<|\$|~|\{|USER|user\b|you\b|name\b|username\b|your)[A-Za-z0-9._-]+/")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com|example\.(?:com|org)|noreply\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
CLOUD_EMAIL = re.compile(r"GoogleDrive-[A-Za-z0-9._%+-]+@")
NTFY_TOPIC = re.compile(r"\b(?:print|p2s)-[0-9a-f]{16,}\b")
SECRET_ASSIGN = re.compile(r"""(?i)(access[_-]?code|api[_-]?key|token|password|secret)["']?\s*[:=]\s*["'][A-Za-z0-9+/_=-]{16,}["']""")

CHECKS = (
    ("private IPv4 address", PRIVATE_IPV4),
    ("MAC address", MAC),
    ("absolute home path", HOME_PATH),
    ("e-mail address", EMAIL),
    ("cloud folder with e-mail", CLOUD_EMAIL),
    ("ntfy-style topic", NTFY_TOPIC),
    ("secret-looking assignment", SECRET_ASSIGN),
)

# A line containing one of these markers is a documented placeholder, not a leak.
ALLOW_MARKERS = ("scan-ignore", "192.0.2.", "REPLACE", "<printer-ip>", "<router-ip>")

# These files contain fake leaks ON PURPOSE (they test the scanner itself).
SELF_FILES = {os.path.join("tools", "scan_personal_data.py"), os.path.join("tests", "test_scanner.py")}


def repo_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard"],
                             capture_output=True, text=True, check=True).stdout.split("\n")
        return [os.path.join(root, p) for p in out if p]
    except Exception:
        found = []
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            found += [os.path.join(base, f) for f in files]
        return found


def scan_text(text, forbid=()):
    """Return a list of (line_number, label, matched_text)."""
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        if any(marker in line for marker in ALLOW_MARKERS):
            continue
        for label, pattern in CHECKS:
            for match in pattern.finditer(line):
                findings.append((number, label, match.group(0)))
        lowered = line.lower()
        for value in forbid:
            if value and value.lower() in lowered:
                findings.append((number, "forbidden string", "<hidden>"))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    parser.add_argument("--forbid", default=os.environ.get("FORBID", ""), help="comma-separated exact strings")
    args = parser.parse_args(argv)

    forbid = [x.strip() for x in args.forbid.split(",") if x.strip()]
    root = os.path.abspath(args.root)
    total = 0
    for path in sorted(repo_files(root)):
        if os.path.splitext(path)[1].lower() in SKIP_EXT or not os.path.isfile(path):
            continue
        if os.path.relpath(path, root) in SELF_FILES:
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (UnicodeDecodeError, OSError):
            continue
        for number, label, value in scan_text(text, forbid):
            total += 1
            shown = value if label != "forbidden string" else value
            print(f"{os.path.relpath(path, root)}:{number}: {label}: {shown}")
    if total:
        print(f"\n{total} finding(s). Remove them or, if a line is an intentional placeholder, add 'scan-ignore' to it.")
        return 1
    print("clean: no personal-looking data found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
