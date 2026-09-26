"""Tests for the scripts. Only synthetic data: no printer, no network, no personal files.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import plistlib
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import gcode_consumption as gc          # noqa: E402
import print_monitor as mon               # noqa: E402
import print_monitor_launchd as launchd   # noqa: E402
import studio_to_orca_filament as conv  # noqa: E402


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as handle:
        json.dump(data, handle)


class MonitorTests(unittest.TestCase):
    BAMBU = {"print": {"gcode_state": "RUNNING", "subtask_name": "Bracket_v2", "mc_percent": 41,
                       "layer_num": 20, "total_layer_num": 300, "mc_print_error_code": "0",
                       "ams": {"tray": [{"id": "0"}]}}}

    def reading(self, state, **extra):
        base = {"state": state, "job": "A_b", "percent": 10, "layer": 1, "total_layers": 5,
                "remaining_min": None, "error": None}
        base.update(extra)
        return base

    # --- bambu adapter
    def test_bambu_report_is_normalized_and_zero_error_is_dropped(self):
        reading = mon.normalize_bambu(self.BAMBU)
        self.assertEqual((reading["state"], reading["job"], reading["percent"]), ("RUNNING", "Bracket_v2", 41))
        self.assertIsNone(reading["error"])

    def test_bambu_real_error_code_is_kept(self):
        report = {"print": {"gcode_state": "PAUSE", "mc_print_error_code": "32774"}}
        self.assertEqual(mon.normalize_bambu(report)["error"], "32774")

    def test_bambu_report_without_state_is_no_reading(self):
        self.assertIsNone(mon.normalize_bambu({"print": {}}))

    # --- moonraker adapter (experimental: sample payloads only)
    def moonraker(self, state, progress=0.5, message=""):
        return {"result": {"status": {
            "print_stats": {"filename": "part.gcode", "state": state, "message": message,
                            "info": {"current_layer": 12, "total_layer": 80}},
            "virtual_sdcard": {"progress": progress}}}}

    def test_moonraker_states_map_to_neutral_states(self):
        for raw, expected in (("standby", "IDLE"), ("printing", "RUNNING"), ("paused", "PAUSE"),
                              ("complete", "FINISH"), ("error", "FAILED"), ("cancelled", "CANCELLED")):
            self.assertEqual(mon.normalize_moonraker(self.moonraker(raw))["state"], expected)

    def test_moonraker_progress_layers_and_error_message(self):
        reading = mon.normalize_moonraker(self.moonraker("error", 0.257, "Heater failed"))
        self.assertEqual((reading["percent"], reading["layer"], reading["total_layers"]), (26, 12, 80))
        self.assertEqual(reading["error"], "Heater failed")

    def test_moonraker_garbage_is_no_reading(self):
        self.assertIsNone(mon.normalize_moonraker({"result": {}}))
        self.assertIsNone(mon.normalize_moonraker(self.moonraker("weird-state")))

    # --- octoprint adapter (experimental: sample payloads only)
    def octoprint(self, state, completion=42.0, left=1200):
        return {"state": state, "job": {"file": {"name": "part.gcode"}},
                "progress": {"completion": completion, "printTimeLeft": left}}

    def test_octoprint_states_map_to_neutral_states(self):
        for raw, expected in (("Printing", "RUNNING"), ("Paused", "PAUSE"), ("Pausing", "PAUSE"),
                              ("Error", "FAILED"), ("Offline after error", "FAILED"),
                              ("Cancelling", "CANCELLED"), ("Operational", "IDLE")):
            self.assertEqual(mon.normalize_octoprint(self.octoprint(raw))["state"], expected)

    def test_octoprint_operational_at_100_percent_means_finished(self):
        self.assertEqual(mon.normalize_octoprint(self.octoprint("Operational", 100.0))["state"], "FINISH")

    def test_octoprint_offline_is_no_reading_and_time_left_is_minutes(self):
        self.assertIsNone(mon.normalize_octoprint(self.octoprint("Offline")))
        self.assertEqual(mon.normalize_octoprint(self.octoprint("Printing", 10, 600))["remaining_min"], 10)

    # --- decisions
    def test_first_reading_never_alerts(self):
        messages, new = mon.decide({"state": None}, self.reading("RUNNING"))
        self.assertEqual(messages, [])
        self.assertEqual(new["state"], "RUNNING")

    def test_transitions_alert_with_expected_titles(self):
        for state, title in (("FINISH", "Print finished"), ("FAILED", "Print failed"), ("PAUSE", "Print paused"),
                             ("CANCELLED", "Print cancelled"), ("RUNNING", "Print started")):
            messages, _ = mon.decide({"state": "IDLE"}, self.reading(state))
            self.assertEqual(messages[0][0], title)

    def test_same_state_is_silent_and_idle_is_not_announced(self):
        self.assertEqual(mon.decide({"state": "RUNNING"}, self.reading("RUNNING"))[0], [])
        self.assertEqual(mon.decide({"state": "RUNNING"}, self.reading("IDLE"))[0], [])

    def test_offline_alert_fires_once_after_threshold(self):
        state, fired = {"state": "RUNNING"}, 0
        for _ in range(6):
            messages, state = mon.decide(state, None, offline_after=3)
            fired += len(messages)
        self.assertEqual(fired, 1)

    def test_reading_resets_offline_counters(self):
        _, new = mon.decide({"state": "RUNNING", "failures": 5, "warned_offline": True}, self.reading("RUNNING"))
        self.assertEqual((new["failures"], new["warned_offline"]), (0, False))

    def test_message_includes_error_and_layer_when_known(self):
        _, text, priority = mon.build_message(self.reading("PAUSE", error="32774", layer=7, total_layers=407))
        self.assertIn("32774", text)
        self.assertIn("layer 7 of 407", text)
        self.assertEqual(priority, "high")

    def test_backend_defaults_to_bambu_and_reads_printer_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(mon.choose_backend(None, tmp), "bambu")
            write(os.path.join(tmp, "printer.json"), {"backend": "moonraker", "host": "192.0.2.20"})
            self.assertEqual(mon.choose_backend(None, tmp), "moonraker")
            self.assertEqual(mon.choose_backend("octoprint", tmp), "octoprint")

    def test_job_name_is_stripped_of_escapes_and_capped(self):
        job = "\x1b[2J\x1b]0;pwned\x07Evil\njob\u202e" + "x" * 500
        _, text, _ = mon.build_message(self.reading("FINISH", job=job, error=None))
        self.assertNotIn("\x1b", text)
        self.assertNotIn("\n", text)
        self.assertNotIn("\u202e", text)
        self.assertLessEqual(len(mon.clean_text(job)), mon.JOB_MAX)
        self.assertTrue(text.startswith("]0;pwned Evil job"))

    def test_ntfy_sends_the_token_as_bearer_only_when_set(self):
        sent = []

        class Response:
            def read(self):
                return b""

        def fake_urlopen(request, timeout=0):
            sent.append(request)
            return Response()

        original = mon.urllib.request.urlopen
        mon.urllib.request.urlopen = fake_urlopen
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "ntfy.json")
                write(path, {"server": "https://ntfy.example.org", "topic": "t", "token": "tk_made_up"})
                self.assertTrue(mon.send_ntfy(path, "T", "x", "default"))
                write(path, {"topic": "t"})
                self.assertTrue(mon.send_ntfy(path, "T", "x", "default"))
        finally:
            mon.urllib.request.urlopen = original
        self.assertEqual(sent[0].get_header("Authorization"), "Bearer tk_made_up")
        self.assertEqual(sent[0].full_url, "https://ntfy.example.org")
        self.assertIsNone(sent[1].get_header("Authorization"))
        self.assertEqual(sent[1].full_url, "https://ntfy.sh")

    def test_http_backends_honour_https_and_refuse_other_schemes(self):
        urls = []
        original = mon.http_get_json
        mon.http_get_json = lambda url, api_key, timeout: urls.append(url) or {}
        try:
            with tempfile.TemporaryDirectory() as tmp:
                write(os.path.join(tmp, "printer.json"), {"host": "192.0.2.30", "scheme": "https", "api_key": "k"})
                mon.read_http_backend("octoprint", tmp)
                write(os.path.join(tmp, "printer.json"), {"host": "192.0.2.20"})
                mon.read_http_backend("moonraker", tmp)
                write(os.path.join(tmp, "printer.json"), {"host": "192.0.2.20", "scheme": "ftp"})
                reading, error = mon.read_http_backend("moonraker", tmp)
        finally:
            mon.http_get_json = original
        self.assertEqual(urls[0], "https://192.0.2.30:443/api/job")
        self.assertTrue(urls[1].startswith("http://192.0.2.20:7125/"))
        self.assertEqual(len(urls), 2)
        self.assertIsNone(reading)
        self.assertIn("scheme", error)

    def test_http_backend_without_host_reports_a_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            reading, error = mon.read_http_backend("moonraker", tmp)
            self.assertIsNone(reading)
            self.assertIn("no host", error)


GCODE = """; HEADER_BLOCK_START
; total layer number: 100
; filament used [mm] = 1295.16
; filament used [g] = 3.86
; filament_settings_id = "My PLA @Printer 0.4 nozzle"
"""


class GcodeConsumptionTests(unittest.TestCase):
    def test_parse(self):
        info = gc.parse(GCODE)
        self.assertEqual(info["grams_total"], 3.86)
        self.assertEqual(info["length_m"], 1.3)
        self.assertEqual(info["layers"], "100")
        self.assertEqual(info["filament_profile"], "My PLA @Printer 0.4 nozzle")

    def test_multi_filament_sums(self):
        info = gc.parse("; filament used [g] = 2.5, 1.5\n")
        self.assertEqual(info["grams_total"], 4.0)

    def test_markdown_row_flags_cancelled(self):
        row = gc.markdown_row(gc.parse(GCODE), "Bracket", "Black-01", "cancelled", "2026-01-01")
        self.assertIn("real use is lower", row)
        self.assertTrue(row.startswith("| 2026-01-01 | Bracket | Black-01 | 3.86 |"))

    def test_reads_gcode_inside_3mf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "plate.gcode.3mf")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Metadata/plate_1.gcode", GCODE)
            self.assertEqual(gc.parse(gc.read_text(path))["grams_total"], 3.86)

    def test_zip_bomb_3mf_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bomb.gcode.3mf")
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("Metadata/plate_1.gcode", b"G1\n" * (1024 * 1024))  # ~1000:1 once deflated
            with self.assertRaises(SystemExit):
                gc.read_text(path)
            with self.assertRaises(SystemExit):
                gdiff.read_text(path)

    def test_oversized_total_is_refused_even_at_a_normal_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.gcode.3mf")
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("Metadata/plate_1.gcode", GCODE)
                archive.writestr("Metadata/plate_2.gcode", GCODE)
            old = gc.ZIP_MAX_TOTAL
            gc.ZIP_MAX_TOTAL = len(GCODE) + 1  # stands in for 500 MB
            try:
                with self.assertRaises(SystemExit):
                    gc.read_text(path)
            finally:
                gc.ZIP_MAX_TOTAL = old


class StudioToOrcaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.orca = self.tmp.name
        fdir = os.path.join(self.orca, "system", "VENDOR", "filament")
        write(os.path.join(fdir, "fdm_common.json"),
              {"name": "fdm_common", "nozzle_temperature": ["200"], "slow_down_min_speed": ["20"],
               "filament_cost": ["10"], "filament_id": "GFCOMMON", "instantiation": "false"})
        write(os.path.join(fdir, "Base PLA.json"),
              {"name": "Base PLA", "inherits": "fdm_common", "filament_id": "GFA00", "version": "01.10.00.00",
               "filament_cost": ["24.99"], "filament_max_volumetric_speed": ["21", "40"],
               "filament_vendor": ["Vendor"]})

    def tearDown(self):
        self.tmp.cleanup()

    def studio(self, **extra):
        profile = {"name": "My PLA", "filament_id": "P123", "inherits": "", "from": "User",
                   "filament_cost": ["95"], "filament_vendor": ["Mine"],
                   "slow_down_min_speed": ["20", "20"],            # paired value
                   "filament_max_volumetric_speed": ["12", "12"],
                   "nozzle_temperature": ["nil"],                  # nil must be skipped
                   "compatible_printers": ["Printer 0.4 nozzle"],
                   "studio_only_key": ["1"]}                       # unknown to Orca: dropped
        profile.update(extra)
        return profile

    def build(self, studio):
        base = conv.resolve(self.orca, "Base PLA")
        return conv.convert(studio, base, "My PLA", "2.4.2.0")

    def test_resolve_merges_parents_child_wins(self):
        base = conv.resolve(self.orca, "Base PLA")
        self.assertEqual(base["nozzle_temperature"], ["200"])      # from parent
        self.assertEqual(base["filament_cost"], ["24.99"])         # child overrides parent

    def test_profile_is_standalone_with_own_id_and_valid_version(self):
        profile, _ = self.build(self.studio())
        self.assertEqual(profile["inherits"], "")
        self.assertEqual(profile["filament_id"], "P123")
        self.assertEqual(profile["version"], "2.4.2.0")
        self.assertEqual(profile["type"], "filament")
        self.assertEqual(profile["from"], "User")
        self.assertNotIn("instantiation", profile)

    def test_user_values_win_and_pitfalls_are_handled(self):
        profile, overridden = self.build(self.studio())
        self.assertEqual(profile["filament_cost"], ["95"])
        self.assertEqual(profile["filament_max_volumetric_speed"], ["12", "12"])   # same length: kept
        self.assertEqual(profile["nozzle_temperature"], ["200"])                    # nil skipped
        self.assertEqual(profile["slow_down_min_speed"], ["20"])                    # trimmed = equal to base
        self.assertNotIn("studio_only_key", profile)
        self.assertNotIn("nozzle_temperature", overridden)

    def test_paired_value_is_trimmed_to_base_length(self):
        profile, _ = self.build(self.studio(slow_down_min_speed=["25", "25"]))
        self.assertEqual(profile["slow_down_min_speed"], ["25"])

    def test_missing_system_profile_exits_with_help(self):
        with self.assertRaises(SystemExit):
            conv.resolve(self.orca, "Does Not Exist")

    def test_cli_writes_json(self):
        studio_path = os.path.join(self.orca, "studio.json")
        write(studio_path, self.studio())
        out = os.path.join(self.orca, "out")
        code = conv.main(["--studio-profile", studio_path, "--base", "Base PLA", "--orca-dir", self.orca,
                          "--version", "2.4.2.0", "--out-dir", out])
        self.assertEqual(code, 0)
        with open(os.path.join(out, "My PLA.json")) as handle:
            self.assertEqual(json.load(handle)["filament_id"], "P123")


class LaunchdTests(unittest.TestCase):
    def test_plist_roundtrip_and_flags(self):
        data = launchd.build_plist("com.example.x", "/usr/bin/python3", "/tmp/m.py", 180, "/tmp/log", True)
        loaded = plistlib.loads(plistlib.dumps(data))
        self.assertEqual(loaded["StartInterval"], 180)
        self.assertEqual(loaded["ProgramArguments"][-1], "--send")

    def test_dry_run_alerts_omit_send(self):
        data = launchd.build_plist("com.example.x", "/usr/bin/python3", "/tmp/m.py", 60, "/tmp/log", False)
        self.assertNotIn("--send", data["ProgramArguments"])



import gcode_settings_diff as gdiff  # noqa: E402


class SettingsDiffTests(unittest.TestCase):
    A = "; wall_loops = 2\n; sparse_infill_density = 20%\n; print_settings_id = Standard\n; total layer number: 100\n"
    B = "; wall_loops = 4\n; sparse_infill_density = 20%\n; print_settings_id = Mine\n; only_in_b = 1\n"

    def test_reads_semicolon_settings(self):
        self.assertEqual(gdiff.read_settings(self.A)["wall_loops"], "2")

    def test_reports_only_real_differences_and_hides_identification(self):
        rows = gdiff.diff_settings(gdiff.read_settings(self.A), gdiff.read_settings(self.B))
        keys = [row[0] for row in rows]
        self.assertIn("wall_loops", keys)
        self.assertIn("only_in_b", keys)
        self.assertNotIn("print_settings_id", keys)
        self.assertNotIn("sparse_infill_density", keys)

    def test_ignore_and_all_flags(self):
        a, b = gdiff.read_settings(self.A), gdiff.read_settings(self.B)
        self.assertNotIn("wall_loops", [r[0] for r in gdiff.diff_settings(a, b, ignore={"wall_loops"})])
        self.assertIn("print_settings_id", [r[0] for r in gdiff.diff_settings(a, b, show_noise=True)])

    def test_identical_files_have_no_differences(self):
        settings = gdiff.read_settings(self.A)
        self.assertEqual(gdiff.diff_settings(settings, dict(settings)), [])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            first, second = os.path.join(tmp, "a.gcode"), os.path.join(tmp, "b.gcode")
            open(first, "w").write(self.A)
            open(second, "w").write(self.A)
            self.assertEqual(gdiff.main([first, second]), 0)
            open(second, "w").write(self.B)
            self.assertEqual(gdiff.main([first, second]), 1)

if __name__ == "__main__":
    unittest.main()
