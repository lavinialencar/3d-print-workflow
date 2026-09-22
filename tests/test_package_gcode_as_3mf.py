"""Tests for package_gcode_as_3mf.py. Fake .gcode.3mf archives built with zipfile, no real Orca needed.

Run:  python3 -m unittest discover -s tests -v
"""
import hashlib
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import package_gcode_as_3mf as pkg  # noqa: E402


def write_fake_template(path, plate=1, with_md5=True, other_files=None):
    """A minimal but structurally real .gcode.3mf: a plate gcode, its md5, and a slice_info.config
    that a real template would carry (the file this whole tool exists to preserve)."""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(f"Metadata/plate_{plate}.gcode", "; template gcode\nG28\n")
        if with_md5:
            z.writestr(f"Metadata/plate_{plate}.gcode.md5", hashlib.md5(b"; template gcode\nG28\n").hexdigest().upper())
        z.writestr("Metadata/slice_info.config", '<config><plate><filament id="1" type="PLA"/></plate></config>')
        z.writestr("Metadata/plate_1.json", "{}")
        for name, data in (other_files or {}).items():
            z.writestr(name, data)


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.template = os.path.join(self.tmp.name, "template.gcode.3mf")
        self.gcode = os.path.join(self.tmp.name, "part.gcode")
        self.out = os.path.join(self.tmp.name, "out.gcode.3mf")
        write_fake_template(self.template)
        with open(self.gcode, "w", encoding="utf-8") as handle:
            handle.write("; real command-line gcode\nG28\nG1 X10\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_replaces_plate_gcode_and_md5(self):
        from pathlib import Path
        result = pkg.package(Path(self.template), Path(self.gcode), Path(self.out))
        with zipfile.ZipFile(self.out) as z:
            content = z.read("Metadata/plate_1.gcode").decode("utf-8")
            md5 = z.read("Metadata/plate_1.gcode.md5").decode("ascii")
        self.assertEqual(content, "; real command-line gcode\nG28\nG1 X10\n")
        self.assertEqual(md5, hashlib.md5(content.encode("utf-8")).hexdigest().upper())
        self.assertEqual(result["plate_gcode_path"], "Metadata/plate_1.gcode")

    def test_slice_info_config_survives_untouched(self):
        from pathlib import Path
        pkg.package(Path(self.template), Path(self.gcode), Path(self.out))
        with zipfile.ZipFile(self.template) as z:
            before = z.read("Metadata/slice_info.config")
        with zipfile.ZipFile(self.out) as z:
            after = z.read("Metadata/slice_info.config")
        self.assertEqual(before, after)  # the whole point: AMS mapping metadata is never touched

    def test_missing_md5_sidecar_is_added_not_required(self):
        from pathlib import Path
        template_no_md5 = os.path.join(self.tmp.name, "no-md5.gcode.3mf")
        write_fake_template(template_no_md5, with_md5=False)
        result = pkg.package(Path(template_no_md5), Path(self.gcode), Path(self.out))
        self.assertFalse(result["plate_md5_sidecar_found_in_template"])
        with zipfile.ZipFile(self.out) as z:
            self.assertIn("Metadata/plate_1.gcode.md5", z.namelist())

    def test_design_time_project_without_plate_gcode_is_refused(self):
        from pathlib import Path
        design_time = os.path.join(self.tmp.name, "design.3mf")
        with zipfile.ZipFile(design_time, "w") as z:
            z.writestr("Metadata/plate_1.json", "{}")  # no plate_1.gcode: a "Save Project", not a sliced export
        with self.assertRaises(pkg.PackageError) as ctx:
            pkg.package(Path(design_time), Path(self.gcode), Path(self.out))
        self.assertIn("Save Project", str(ctx.exception))

    def test_non_gcode_input_is_refused(self):
        from pathlib import Path
        not_gcode = os.path.join(self.tmp.name, "part.stl")
        with open(not_gcode, "w", encoding="utf-8") as handle:
            handle.write("solid x\nendsolid x\n")
        with self.assertRaises(pkg.PackageError):
            pkg.package(Path(self.template), Path(not_gcode), Path(self.out))

    def test_empty_gcode_is_refused(self):
        from pathlib import Path
        empty = os.path.join(self.tmp.name, "empty.gcode")
        open(empty, "w").close()
        with self.assertRaises(pkg.PackageError):
            pkg.package(Path(self.template), Path(empty), Path(self.out))

    def test_missing_template_is_refused(self):
        from pathlib import Path
        with self.assertRaises(pkg.PackageError):
            pkg.package(Path(os.path.join(self.tmp.name, "nope.gcode.3mf")), Path(self.gcode), Path(self.out))

    def test_explicit_plate_number_selects_that_plate(self):
        from pathlib import Path
        multi = os.path.join(self.tmp.name, "multi.gcode.3mf")
        write_fake_template(multi, plate=1)
        with zipfile.ZipFile(multi, "a") as z:
            z.writestr("Metadata/plate_2.gcode", "; plate 2\n")
            z.writestr("Metadata/plate_2.gcode.md5", hashlib.md5(b"; plate 2\n").hexdigest().upper())
        result = pkg.package(Path(multi), Path(self.gcode), Path(self.out), plate=2)
        self.assertEqual(result["plate_gcode_path"], "Metadata/plate_2.gcode")
        with zipfile.ZipFile(self.out) as z:
            self.assertEqual(z.read("Metadata/plate_1.gcode").decode("utf-8"), "; template gcode\nG28\n")  # untouched
            self.assertEqual(z.read("Metadata/plate_2.gcode").decode("utf-8"), "; real command-line gcode\nG28\nG1 X10\n")

    def test_unknown_plate_number_is_refused(self):
        from pathlib import Path
        with self.assertRaises(pkg.PackageError):
            pkg.package(Path(self.template), Path(self.gcode), Path(self.out), plate=9)

    def test_main_cli_writes_output_and_prints_summary(self):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pkg.main(["--template", self.template, "--gcode", self.gcode, "--out", self.out])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.isfile(self.out))
        self.assertIn("slice_info.config", buf.getvalue())

    def test_main_cli_reports_error_without_traceback(self):
        code = pkg.main(["--template", "/nope.gcode.3mf", "--gcode", self.gcode, "--out", self.out])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
