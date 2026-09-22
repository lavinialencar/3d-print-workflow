"""Tests for fix_bambu_machine_profile.py. A tiny fake BBL tree, no real OrcaSlicer install needed.

Run:  python3 -m unittest discover -s tests -v
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import fix_bambu_machine_profile as fx  # noqa: E402


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle)


class FakeTreeTests(unittest.TestCase):
    """A two-level chain: common -> printer (the real Bambu shape: printable_area lives only in common)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bbl = self.tmp.name
        write(os.path.join(self.bbl, "machine", "fdm_common.json"),
              {"printable_area": ["0x0", "256x0", "256x256", "0x256"], "printer_structure": "corexy", "gcode_flavor": "marlin"})
        write(os.path.join(self.bbl, "machine", "My Printer 0.4 nozzle.json"),
              {"inherits": "fdm_common", "name": "My Printer 0.4 nozzle", "nozzle_diameter": ["0.4"]})

    def tearDown(self):
        self.tmp.cleanup()

    def test_resolve_chain_merges_parent_under_child(self):
        merged, path = fx.resolve_chain(self.bbl, "machine", "My Printer 0.4 nozzle")
        self.assertEqual(merged["printable_area"], ["0x0", "256x0", "256x256", "0x256"])
        self.assertEqual(merged["nozzle_diameter"], ["0.4"])
        self.assertTrue(path.endswith("My Printer 0.4 nozzle.json"))

    def test_missing_inherited_keys_finds_exactly_the_gap(self):
        raw, missing, _ = fx.missing_inherited_keys(self.bbl, "machine", "My Printer 0.4 nozzle")
        self.assertNotIn("printable_area", raw)                 # confirms the bug: the child file lacks it
        self.assertEqual(missing["printable_area"], ["0x0", "256x0", "256x256", "0x256"])
        self.assertEqual(missing["printer_structure"], "corexy")
        self.assertEqual(set(missing), {"printable_area", "printer_structure", "gcode_flavor"})

    def test_patch_never_overrides_a_key_the_child_already_has(self):
        write(os.path.join(self.bbl, "machine", "fdm_common.json"),
              {"printable_area": ["0x0", "256x0", "256x256", "0x256"], "gcode_flavor": "marlin"})
        write(os.path.join(self.bbl, "machine", "Overridden.json"),
              {"inherits": "fdm_common", "name": "Overridden", "gcode_flavor": "klipper"})
        patched, missing, _ = fx.patch(self.bbl, "machine", "Overridden")
        self.assertEqual(patched["gcode_flavor"], "klipper")    # the child's own choice survives
        self.assertNotIn("gcode_flavor", missing)
        self.assertEqual(patched["printable_area"], ["0x0", "256x0", "256x256", "0x256"])

    def test_three_level_chain_resolves_all_the_way_up(self):
        write(os.path.join(self.bbl, "machine", "fdm_root.json"), {"printer_technology": "FFF"})
        write(os.path.join(self.bbl, "machine", "fdm_common.json"),
              {"inherits": "fdm_root", "printable_area": ["0x0", "256x0", "256x256", "0x256"]})
        merged, _ = fx.resolve_chain(self.bbl, "machine", "My Printer 0.4 nozzle")
        self.assertEqual(merged["printer_technology"], "FFF")
        self.assertEqual(merged["printable_area"], ["0x0", "256x0", "256x256", "0x256"])

    def test_inherits_cycle_is_rejected_not_infinite_looped(self):
        write(os.path.join(self.bbl, "machine", "a.json"), {"inherits": "b", "name": "a"})
        write(os.path.join(self.bbl, "machine", "b.json"), {"inherits": "a", "name": "b"})
        with self.assertRaises(ValueError):
            fx.resolve_chain(self.bbl, "machine", "a")

    def test_a_profile_with_no_inherits_has_nothing_missing(self):
        write(os.path.join(self.bbl, "machine", "standalone.json"), {"name": "standalone", "nozzle_diameter": ["0.4"]})
        raw, missing, _ = fx.missing_inherited_keys(self.bbl, "machine", "standalone")
        self.assertEqual(missing, {})
        self.assertEqual(raw, {"name": "standalone", "nozzle_diameter": ["0.4"]})

    def test_common_base_found_outside_the_machine_subfolder(self):
        """Real Bambu trees keep the common base at the BBL root, not under machine/: the search must reach it."""
        write(os.path.join(self.bbl, "fdm_machine_common.json"), {"printer_technology": "FFF"})
        write(os.path.join(self.bbl, "machine", "Leaf.json"), {"inherits": "fdm_machine_common", "name": "Leaf"})
        merged, _ = fx.resolve_chain(self.bbl, "machine", "Leaf")
        self.assertEqual(merged["printer_technology"], "FFF")

    def test_unknown_profile_name_raises_a_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            fx.resolve_chain(self.bbl, "machine", "Does Not Exist")

    def test_main_writes_the_patched_file_and_reports_the_gap(self):
        with tempfile.TemporaryDirectory() as outdir:
            out = os.path.join(outdir, "out.json")
            code = fx.main(["My Printer 0.4 nozzle", "--bbl-dir", self.bbl, "--out", out])
            self.assertEqual(code, 0)
            with open(out, encoding="utf-8") as handle:
                written = json.load(handle)
            self.assertEqual(written["printable_area"], ["0x0", "256x0", "256x256", "0x256"])
            self.assertEqual(written["nozzle_diameter"], ["0.4"])   # the original file's own key survives

    def test_main_is_quiet_on_request(self):
        with tempfile.TemporaryDirectory() as outdir:
            out = os.path.join(outdir, "out.json")
            self.assertEqual(fx.main(["My Printer 0.4 nozzle", "--bbl-dir", self.bbl, "--out", out, "--quiet"]), 0)

    def test_main_reports_a_missing_bbl_dir_without_a_traceback(self):
        with self.assertRaises(SystemExit):
            fx.main(["Nope", "--bbl-dir", "/no/such/directory"])


if __name__ == "__main__":
    unittest.main()
