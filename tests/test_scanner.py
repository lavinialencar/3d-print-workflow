"""Tests for tools/scan_personal_data.py, with obviously fake seeded leaks."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import scan_personal_data as scan  # noqa: E402


def labels(text, forbid=()):
    return {label for _, label, _ in scan.scan_text(text, forbid)}


class ScannerTests(unittest.TestCase):
    def test_catches_private_ip_but_not_documentation_range(self):
        self.assertIn("private IPv4 address", labels("host: 192.168.1.44"))
        self.assertIn("private IPv4 address", labels("host: 10.0.0.5"))
        self.assertEqual(labels("host: 192.0.2.10"), set())

    def test_catches_mac(self):
        self.assertIn("MAC address", labels("mac aa:bb:cc:dd:ee:ff"))
        self.assertIn("MAC address", labels("mac aa:b:cc:d:ee:f"))       # macOS drops leading zeros

    def test_catches_absolute_home_path_but_not_placeholders(self):
        self.assertIn("absolute home path", labels("/Users/jane/Library/x"))
        self.assertIn("absolute home path", labels("/home/jane/x"))
        self.assertEqual(labels("/Users/<name>/Library and ~/Library and /Users/you/x"), set())

    def test_catches_email_but_allows_noreply_and_example(self):
        self.assertIn("e-mail address", labels("contact jane.doe@gmail.com"))
        self.assertEqual(labels("12345+jane@users.noreply.github.com and a@example.com"), set())

    def test_catches_cloud_folder_with_email(self):
        self.assertIn("cloud folder with e-mail", labels("GoogleDrive-jane@gmail.com/My Drive"))

    def test_catches_ntfy_topic_shape(self):
        self.assertIn("ntfy-style topic", labels('"topic": "print-0123456789abcdef0123"'))
        self.assertEqual(labels('"topic": "print-REPLACE-WITH-A-LONG-RANDOM-STRING"'), set())

    def test_catches_secret_assignment(self):
        self.assertIn("secret-looking assignment", labels('"access_code": "abcd1234efgh5678ijkl"'))

    def test_forbid_list_matches_case_insensitively_and_hides_value(self):
        found = scan.scan_text("hello Jane", forbid=["jane"])
        self.assertEqual(found[0][1], "forbidden string")
        self.assertEqual(found[0][2], "<hidden>")

    def test_scan_ignore_marker_skips_a_line(self):
        self.assertEqual(labels("192.168.1.44  # scan-ignore"), set())



class LinkCheckerTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
        import check_links
        self.check = check_links.check
        self.slugify = check_links.slugify

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = os.path.join(self.tmp.name, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(text)

    def test_slug_matches_github_style(self):
        self.assertEqual(self.slugify("What is proven, and what is not"), "what-is-proven-and-what-is-not")
        self.assertEqual(self.slugify("The `gcode` skill"), "the-gcode-skill")

    def test_good_links_and_anchors_pass(self):
        self.write("a.md", "# Title\n\n## Second part\n\nSee [b](docs/b.md#deep-dive) and [here](#second-part).\n")
        self.write("docs/b.md", "# B\n\n## Deep dive\n")
        self.assertEqual(self.check(self.tmp.name), [])

    def test_missing_file_is_reported(self):
        self.write("a.md", "[nope](missing.md)\n")
        self.assertEqual(len(self.check(self.tmp.name)), 1)

    def test_missing_anchor_is_reported(self):
        self.write("a.md", "[x](b.md#not-there)\n")
        self.write("b.md", "# B\n")
        self.assertIn("missing anchor", self.check(self.tmp.name)[0])

    def test_broken_image_is_reported_and_external_links_are_ignored(self):
        self.write("a.md", '<img src="assets/nope.svg"> and [web](https://example.com/x) and ![i](gone.png)\n')
        problems = self.check(self.tmp.name)
        self.assertEqual(len(problems), 2)

    def test_links_inside_code_fences_are_ignored(self):
        self.write("a.md", "```\n[not real](missing.md)\n```\n")
        self.assertEqual(self.check(self.tmp.name), [])

if __name__ == "__main__":
    unittest.main()
