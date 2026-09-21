#!/usr/bin/env python3
"""print_monitor_launchd.py - run the monitor automatically on macOS with launchd.

launchd is the scheduler built into macOS. Running a plain Python script from it costs nothing
(no AI tokens involved) and survives reboots. It only runs while the Mac is awake.

Commands
    print      show the .plist that would be created (changes nothing)   <- start here
    install    create the .plist and load it
    uninstall  unload it and delete the .plist
    status     show whether it is loaded and the last exit code

Examples
    python3 scripts/print_monitor_launchd.py print
    python3 scripts/print_monitor_launchd.py install --interval 180
    python3 scripts/print_monitor_launchd.py status
    python3 scripts/print_monitor_launchd.py uninstall

Tip: if the repository lives inside a cloud-synced folder (Google Drive, iCloud), macOS privacy
rules may stop launchd from reading the script. After `install`, run `status` and check the log;
if you see "Operation not permitted", copy scripts/print_monitor.py to ~/.local/bin and use
--script to point there.
"""
import argparse
import os
import plistlib
import subprocess
import sys

DEFAULT_LABEL = "com.example.print-monitor"
HERE = os.path.dirname(os.path.abspath(__file__))


def build_plist(label, python, script, interval, log_path, send):
    arguments = [python, script] + (["--send"] if send else [])
    return {
        "Label": label,
        "ProgramArguments": arguments,
        "StartInterval": interval,
        "RunAtLoad": True,
        "StandardOutPath": log_path,
        "StandardErrorPath": log_path,
        "ProcessType": "Background",
    }


def plist_path(label):
    return os.path.expanduser(f"~/Library/LaunchAgents/{label}.plist")


def launchctl(*args):
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["print", "install", "uninstall", "status"])
    parser.add_argument("--label", default=DEFAULT_LABEL, help="reverse-DNS style name; change 'example' to your own")
    parser.add_argument("--interval", type=int, default=180, help="seconds between readings (default 180)")
    parser.add_argument("--script", default=os.path.join(HERE, "print_monitor.py"))
    parser.add_argument("--python", default=sys.executable, help="absolute path of the python to use")
    parser.add_argument("--log", default=os.path.expanduser("~/.config/print-workflow/monitor.log"))
    parser.add_argument("--dry-run-alerts", action="store_true",
                        help="schedule WITHOUT --send (monitor only logs what it would send)")
    args = parser.parse_args(argv)

    path = plist_path(args.label)
    domain = f"gui/{os.getuid()}"

    if args.command in ("print", "install"):
        data = build_plist(args.label, args.python, args.script, args.interval, args.log, not args.dry_run_alerts)
        if args.command == "print":
            sys.stdout.write(plistlib.dumps(data).decode())
            return 0
        if os.path.exists(path):
            sys.exit(f"{path} already exists. Run 'uninstall' first (or choose another --label).")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        os.makedirs(os.path.dirname(args.log), exist_ok=True)
        with open(path, "wb") as handle:
            plistlib.dump(data, handle)
        result = launchctl("bootstrap", domain, path)
        print(result.stderr.strip() or f"loaded {args.label}, every {args.interval}s")
        return result.returncode

    if args.command == "uninstall":
        launchctl("bootout", f"{domain}/{args.label}")
        if os.path.exists(path):
            os.remove(path)
        print(f"removed {args.label}")
        return 0

    result = launchctl("print", f"{domain}/{args.label}")
    if result.returncode != 0:
        print(f"{args.label} is not loaded")
        return 1
    for line in result.stdout.splitlines():
        if any(token in line for token in ("state =", "runs =", "last exit code")):
            print(line.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
