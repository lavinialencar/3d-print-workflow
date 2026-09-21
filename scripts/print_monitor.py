#!/usr/bin/env python3
"""print_monitor.py - read-only print monitor for several printer families, with push alerts.

What it does
    Each time it runs it reads the printer's state, compares it with the previous run, and sends a
    push notification when something changes: print started, finished, failed, paused, cancelled,
    or the printer went silent.

What it never does
    It never uploads a file and never starts, pauses or cancels a print. Read-only, always.
    It never prints or logs an access code or API key.

Backends (choose with --backend, or put "backend" in printer.json)
    bambu       Bambu Lab printers over LAN Only + Developer Mode. VERIFIED on a P2S.
                Uses the `bambu-labs` skill's bambu_lan_print.py (MIT, text-to-cad project).
    moonraker   Klipper printers running Moonraker (HTTP JSON API).       EXPERIMENTAL
    octoprint   OctoPrint (REST API, needs an API key).                    EXPERIMENTAL
    The two experimental backends are unit-tested against sample payloads only. Adding a printer
    family is a small function: see docs/05-other-printers.md.

Requirements
    Python 3.8+ (standard library only), plus:
      bambu     ~/.config/print-workflow/bambu-printers.json   (config/bambu-printers.example.json)
      others    ~/.config/print-workflow/printer.json          (config/printer.moonraker.example.json ...)
      alerts    ~/.config/print-workflow/ntfy.json             (config/ntfy.example.json)

Usage
    python3 scripts/print_monitor.py --print-status   # print the parsed state and exit
    python3 scripts/print_monitor.py                  # dry run: shows what it WOULD send
    python3 scripts/print_monitor.py --send           # really sends

Schedule it with scripts/print_monitor_launchd.py (macOS) - see docs/07-monitor-and-alerts.md.
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

DEFAULT_CONFIG_DIR = os.path.expanduser(os.environ.get("PRINT_WORKFLOW_CONFIG_DIR", "~/.config/print-workflow"))
BACKENDS = ("bambu", "moonraker", "octoprint")

# Neutral vocabulary every backend translates into:
#   state          IDLE | PREPARING | RUNNING | PAUSE | FINISH | FAILED | CANCELLED
#   job            file or job name (str) or None
#   percent        0..100 or None        layer / total_layers   ints or None
#   remaining_min  minutes or None       error                  short text or None


# --------------------------------------------------------------------------- helpers
def walk(obj):
    """Yield every (key, value) pair in a nested JSON structure."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key, value
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def first_scalars(report, wanted):
    """The first scalar occurrence of each wanted key anywhere in a nested report."""
    found = {}
    for key, value in walk(report):
        if key in wanted and key not in found and not isinstance(value, (dict, list)):
            found[key] = value
    return found


def load_json(path, default):
    try:
        with open(path) as handle:
            return json.load(handle)
    except Exception:
        return default


def clean_error(value):
    """'0', 0, '' and None all mean 'no error'."""
    if value in (None, "", 0, "0"):
        return None
    return str(value)


def http_get_json(url, api_key=None, timeout=10):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if api_key:
        request.add_header("X-Api-Key", api_key)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


# --------------------------------------------------------------------------- normalizers (pure)
BAMBU_FIELDS = ("gcode_state", "subtask_name", "mc_percent", "layer_num", "total_layer_num",
                "mc_remaining_time", "mc_print_error_code", "print_error")


def normalize_bambu(report):
    """Bambu Lab status report -> neutral reading. Returns None if the report has no state."""
    fields = first_scalars(report, BAMBU_FIELDS)
    if "gcode_state" not in fields:
        return None
    return {
        "state": str(fields["gcode_state"]).upper().replace("PREPARE", "PREPARING"),
        "job": fields.get("subtask_name") or None,
        "percent": fields.get("mc_percent"),
        "layer": fields.get("layer_num"),
        "total_layers": fields.get("total_layer_num"),
        "remaining_min": fields.get("mc_remaining_time"),
        "error": clean_error(fields.get("mc_print_error_code")) or clean_error(fields.get("print_error")),
    }


MOONRAKER_STATES = {"standby": "IDLE", "printing": "RUNNING", "paused": "PAUSE",
                    "complete": "FINISH", "error": "FAILED", "cancelled": "CANCELLED"}


def normalize_moonraker(payload):
    """Response of GET /printer/objects/query?print_stats&virtual_sdcard -> neutral reading."""
    try:
        status = payload["result"]["status"]
        stats = status["print_stats"]
    except (KeyError, TypeError):
        return None
    state = MOONRAKER_STATES.get(str(stats.get("state", "")).lower())
    if state is None:
        return None
    progress = (status.get("virtual_sdcard") or {}).get("progress")
    info = stats.get("info") or {}
    return {
        "state": state,
        "job": stats.get("filename") or None,
        "percent": round(progress * 100) if isinstance(progress, (int, float)) else None,
        "layer": info.get("current_layer"),
        "total_layers": info.get("total_layer"),
        "remaining_min": None,
        "error": (stats.get("message") or None) if state == "FAILED" else None,
    }


def normalize_octoprint(payload):
    """Response of GET /api/job -> neutral reading. OctoPrint has no explicit 'finished' state,
    so 'Operational' with 100% completion is reported as FINISH."""
    if not isinstance(payload, dict) or "state" not in payload:
        return None
    raw = str(payload["state"]).lower()
    progress = payload.get("progress") or {}
    completion = progress.get("completion")
    if "error" in raw:
        state = "FAILED"
    elif raw in ("printing", "starting", "finishing", "sending file to sd"):
        state = "RUNNING"
    elif raw in ("pausing", "paused"):
        state = "PAUSE"
    elif raw == "cancelling":
        state = "CANCELLED"
    elif raw == "operational":
        state = "FINISH" if isinstance(completion, (int, float)) and completion >= 100 else "IDLE"
    elif raw in ("opening serial connection", "detecting serial connection", "connecting"):
        state = "IDLE"
    else:
        return None                       # 'Offline' and unknown states: treat as no reading
    left = progress.get("printTimeLeft")
    return {
        "state": state,
        "job": ((payload.get("job") or {}).get("file") or {}).get("name") or None,
        "percent": round(completion) if isinstance(completion, (int, float)) else None,
        "layer": None,
        "total_layers": None,
        "remaining_min": round(left / 60) if isinstance(left, (int, float)) else None,
        "error": None,
    }


# --------------------------------------------------------------------------- readers (network)
def find_bambu_script(explicit=None):
    for path in (explicit, os.environ.get("BAMBU_LAN_SCRIPT")):
        if path and os.path.exists(os.path.expanduser(path)):
            return os.path.expanduser(path)
    pattern = os.path.expanduser("~/.claude/plugins/cache/**/bambu-labs/scripts/bambu_lan_print.py")
    found = sorted(glob.glob(pattern, recursive=True))
    return found[-1] if found else None


def pick_bambu_printer(config_path, requested):
    if requested:
        return requested
    printers = (load_json(config_path, {}) or {}).get("printers") or {}
    return next(iter(printers), "printer")


def read_bambu(config_dir, printer_id, bambu_script, wait_seconds=12):
    script = find_bambu_script(bambu_script)
    if not script:
        return None, "bambu_lan_print.py not found (install the cad plugin or pass --bambu-script)"
    config_path = os.path.join(config_dir, "bambu-printers.json")
    try:
        run = subprocess.run(
            [sys.executable, script, "status", "--config", config_path,
             "--printer", pick_bambu_printer(config_path, printer_id),
             "--push-all", "--wait-seconds", str(wait_seconds)],
            capture_output=True, text=True, timeout=wait_seconds + 60)
        report = json.loads(run.stdout)
    except Exception as exc:              # printer off, network down, bad JSON: all mean "no reading"
        return None, type(exc).__name__
    reading = normalize_bambu(report)
    return reading, (None if reading else "report had no state")


def read_http_backend(backend, config_dir, timeout=10):
    config = load_json(os.path.join(config_dir, "printer.json"), {})
    host, api_key = config.get("host"), config.get("api_key") or None
    if not host:
        return None, f"no host in {os.path.join(config_dir, 'printer.json')}"
    try:
        if backend == "moonraker":
            url = f"http://{host}:{config.get('port', 7125)}/printer/objects/query?print_stats&virtual_sdcard"
            reading = normalize_moonraker(http_get_json(url, api_key, timeout))
        else:
            url = f"http://{host}:{config.get('port', 80)}/api/job"
            reading = normalize_octoprint(http_get_json(url, api_key, timeout))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return None, type(exc).__name__
    return reading, (None if reading else "response had no usable state")


def choose_backend(explicit, config_dir):
    if explicit:
        return explicit
    return (load_json(os.path.join(config_dir, "printer.json"), {}) or {}).get("backend", "bambu")


# --------------------------------------------------------------------------- decisions (pure)
def build_message(reading):
    """(title, text, priority) for a state worth announcing, else None."""
    name = str(reading.get("job") or "print").replace("_", " ")
    percent = reading.get("percent")
    where = ""
    if reading.get("layer") is not None and reading.get("total_layers"):
        where = f" (layer {reading['layer']} of {reading['total_layers']})"
    error = f" Error: {reading['error']}." if reading.get("error") else ""
    state = reading.get("state")
    if state == "FINISH":
        return "Print finished", f"{name} is done. Ready to remove from the plate.", "default"
    if state == "FAILED":
        return "Print failed", f"{name} failed at {percent}%{where}.{error} Worth a look.", "high"
    if state == "PAUSE":
        return "Print paused", f"{name} paused at {percent}%{where}.{error}", "high"
    if state == "CANCELLED":
        return "Print cancelled", f"{name} was cancelled at {percent}%{where}.", "default"
    if state == "RUNNING":
        return "Print started", f"{name} started printing.", "low"
    return None


def decide(previous, reading, offline_after=3):
    """Pure decision logic. `previous` is the saved state dict. Returns (messages, new_state)."""
    failures = previous.get("failures", 0)
    warned = previous.get("warned_offline", False)
    messages = []
    new = {"state": previous.get("state"), "failures": failures, "warned_offline": warned}
    if reading is None:
        new["failures"] = failures + 1
        if new["failures"] >= offline_after and not warned:
            messages.append(("Printer not responding",
                             f"No answer from the printer for {offline_after} readings in a row. "
                             "Powered off or off the network?", "default"))
            new["warned_offline"] = True
        return messages, new
    new["failures"], new["warned_offline"] = 0, False
    current = reading.get("state")
    if previous.get("state") is not None and current != previous.get("state"):
        message = build_message(reading)
        if message:
            messages.append(message)
    new["state"] = current
    return messages, new


def send_ntfy(path, title, text, priority):
    config = load_json(path, None)
    if not config or not config.get("topic"):
        print(f"[no channel] create {path} with server and topic to send")
        return False
    body = json.dumps({"topic": config["topic"], "title": title, "message": text,
                       "priority": {"low": 2, "default": 3, "high": 4}[priority]}).encode()
    request = urllib.request.Request(config.get("server", "https://ntfy.sh"), data=body,
                                     headers={"Content-Type": "application/json"})
    urllib.request.urlopen(request, timeout=15).read()
    return True


# --------------------------------------------------------------------------- main
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=BACKENDS, help="default: 'backend' in printer.json, else bambu")
    parser.add_argument("--send", action="store_true", help="really send notifications (default: dry run)")
    parser.add_argument("--print-status", action="store_true", help="print the parsed state and exit")
    parser.add_argument("--printer", default=os.environ.get("PRINTER_ID"),
                        help="bambu only: printer id inside bambu-printers.json (default: the first one)")
    parser.add_argument("--config-dir", default=DEFAULT_CONFIG_DIR)
    parser.add_argument("--bambu-script", default=None, help="bambu only: path to bambu_lan_print.py")
    parser.add_argument("--offline-after", type=int, default=3,
                        help="consecutive failed readings before the 'not responding' alert")
    args = parser.parse_args(argv)

    backend = choose_backend(args.backend, args.config_dir)
    if backend not in BACKENDS:
        sys.exit(f"unknown backend '{backend}', choose one of: {', '.join(BACKENDS)}")
    if backend == "bambu":
        reading, error = read_bambu(args.config_dir, args.printer, args.bambu_script)
    else:
        reading, error = read_http_backend(backend, args.config_dir)

    if args.print_status:
        print(json.dumps(reading, indent=2) if reading else f"no reading ({error})")
        return 0

    state_file = os.path.join(args.config_dir, "monitor-state.json")
    previous = load_json(state_file, {"state": None, "failures": 0, "warned_offline": False})
    if reading is None:
        print(f"no reading ({error})")
    else:
        print(f"[{backend}] state: {reading['state']} | {reading['job']} | {reading['percent']}%")

    messages, new_state = decide(previous, reading, args.offline_after)
    for title, text, priority in messages:
        if args.send:
            sent = send_ntfy(os.path.join(args.config_dir, "ntfy.json"), title, text, priority)
            print("SENT" if sent else "NOT SENT", "|", title, "|", text)
        else:
            print("DRY RUN (not sent) |", title, "|", text)
    if not messages:
        print("nothing to announce")

    os.makedirs(args.config_dir, exist_ok=True)
    with open(state_file, "w") as handle:
        json.dump(new_state, handle)
    os.chmod(state_file, 0o600)
    return 0


if __name__ == "__main__":
    sys.exit(main())
