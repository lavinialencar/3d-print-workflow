"""Tests for find_models.py. The network is never touched: the opener is a fake. Tokens here are made up.

Run:  python3 -m unittest discover -s tests -v
"""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import find_models as fm  # noqa: E402

PRINTABLES = [
    {"id": "1", "name": "Wall Mount", "slug": "wall-mount", "likesCount": 400, "downloadCount": 5000, "makesCount": 2,
     "datePublished": "2025-03-29T17:36:48Z", "license": {"name": "CC BY"}, "user": {"publicUsername": "ana"}},
    {"id": "2", "name": "Wall Mount Pro", "slug": "wall-mount-pro", "likesCount": 100, "downloadCount": 900, "makesCount": 30,
     "datePublished": "2026-01-02T00:00:00Z", "license": None, "user": None},
]
THINGIVERSE = [
    {"id": 10, "name": "Nice Hook", "like_count": 900, "make_count": 50, "created_at": "2024-05-01T10:00:00+00:00",
     "creator": {"name": "bob"}, "allows_derivatives": False, "public_url": "https://www.thingiverse.com/thing:10", "is_ai": False},
    {"id": 11, "name": "Adult thing", "like_count": 5000, "make_count": 90, "is_nsfw": True},
    {"id": 12, "name": "Private thing", "like_count": 5000, "make_count": 90, "is_private": True},
    {"id": 13, "name": "AI Hook", "like_count": 3, "make_count": 0, "creator": {"name": "cy"}, "allows_derivatives": True, "is_ai": True},
]


def fake(printables=None, thingiverse=None):
    """One opener for both sites; remembers every request it saw."""
    def opener(request, timeout=0):
        opener.requests.append(request)
        if "printables" in request.full_url:
            return io.BytesIO(json.dumps({"data": {"result": {"items": printables or []}}}).encode())
        return io.BytesIO(json.dumps({"total": len(thingiverse or []), "hits": thingiverse or []}).encode())
    opener.requests = []
    return opener


class PrintablesTests(unittest.TestCase):
    def test_shape_builds_the_link_and_survives_missing_fields(self):
        shaped = fm.shape_printables(PRINTABLES[1])
        self.assertEqual(shaped["url"], "https://www.printables.com/model/2-wall-mount-pro")
        self.assertIsNone(shaped["author"])
        self.assertIsNone(shaped["license"])
        self.assertEqual(shaped["published"], "2026-01-02")

    def test_search_sends_an_honest_user_agent_and_the_term(self):
        opener = fake(printables=PRINTABLES)
        self.assertEqual(len(fm.search_printables("wall mount", 5, opener)), 2)
        self.assertIn("3d-print-workflow", opener.requests[0].get_header("User-agent"))
        self.assertEqual(json.loads(opener.requests[0].data)["variables"], {"q": "wall mount", "n": 5})

    def test_an_api_error_becomes_a_clear_failure_not_a_crash(self):
        def blocked(request, timeout=0):
            return io.BytesIO(json.dumps({"errors": [{"message": "blocked"}]}).encode())
        with self.assertRaises(RuntimeError):
            fm.search_printables("x", 3, blocked)
        self.assertEqual(fm.main(["x", "--site", "printables"], blocked, token=""), 1)

    def test_network_failure_is_reported(self):
        def broken(request, timeout=0):
            raise urllib.error.URLError("offline")
        self.assertEqual(fm.main(["x", "--site", "printables"], broken, token=""), 1)


class ThingiverseTests(unittest.TestCase):
    def test_token_goes_in_a_header_never_in_the_url(self):
        opener = fake(thingiverse=THINGIVERSE)
        fm.search_thingiverse("hook", 4, "SECRETTOKEN", opener)
        request = opener.requests[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer SECRETTOKEN")
        self.assertNotIn("SECRETTOKEN", request.full_url)
        self.assertNotIn("access_token", request.full_url)

    def test_shape_reads_derivatives_makes_and_ai_flag(self):
        shaped = fm.shape_thingiverse(THINGIVERSE[0])
        self.assertEqual((shaped["makes"], shaped["license"], shaped["author"]), (50, "NO derivatives", "bob"))
        self.assertIsNone(shaped["downloads"])
        self.assertTrue(fm.shape_thingiverse(THINGIVERSE[3])["ai_generated"])
        self.assertEqual(fm.shape_thingiverse(THINGIVERSE[3])["license"], "derivatives allowed")

    def test_adult_and_private_things_never_reach_the_list(self):
        kept = [i["name"] for i in THINGIVERSE if fm.keep_thingiverse(i)]
        self.assertEqual(kept, ["Nice Hook", "AI Hook"])

    def test_loose_thingiverse_hits_are_dropped_when_they_ignore_your_words(self):
        popular = {"id": 20, "name": "Gingerbread House", "tags": [{"name": "christmas"}], "like_count": 9000}
        on_topic = {"id": 21, "name": "Horse Keychain", "tags": [{"name": "animal"}], "like_count": 5}
        by_tag = {"id": 22, "name": "Little Pony", "tags": [{"name": "horse"}, {"name": "keychain"}], "like_count": 7}
        one_word = {"id": 23, "name": "Bottle opener keychain", "tags": [], "like_count": 8}
        self.assertFalse(fm.matches_terms(popular, "horse keychain"))
        self.assertTrue(fm.matches_terms(on_topic, "horse keychain"))
        self.assertTrue(fm.matches_terms(by_tag, "horse keychain"))
        self.assertTrue(fm.matches_terms(one_word, "horse keychain"))     # half of the words is the floor
        self.assertTrue(fm.matches_terms(popular, "a"))                   # nothing to match on: keep

    def test_collect_applies_the_filter(self):
        opener = fake(thingiverse=[{"id": 20, "name": "Gingerbread House", "like_count": 9000},
                                   {"id": 21, "name": "Horse Keychain", "like_count": 5}])
        items, _ = fm.collect("horse keychain", 3, "thingiverse", opener, "tok")
        self.assertEqual([i["name"] for i in items], ["Horse Keychain"])

    def test_without_a_token_thingiverse_is_skipped_with_a_note(self):
        items, notes = fm.collect("x", 3, "thingiverse", fake(), None)
        self.assertEqual(items, [])
        self.assertIn("no token", notes[0])

    def test_a_401_explains_the_two_usual_causes(self):
        def unauthorized(request, timeout=0):
            raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, None)
        items, notes = fm.collect("x", 3, "thingiverse", unauthorized, "tok")
        self.assertEqual(items, [])
        self.assertIn("not approved yet", notes[0])

    def test_one_site_failing_does_not_hide_the_other(self):
        def half(request, timeout=0):
            if "printables" in request.full_url:
                raise urllib.error.URLError("offline")
            return io.BytesIO(json.dumps({"hits": THINGIVERSE}).encode())
        items, notes = fm.collect("x", 3, "all", half, "tok")
        self.assertEqual({i["site"] for i in items}, {"Thingiverse"})
        self.assertIn("Printables failed", notes[0])

    def test_token_is_read_from_the_file_or_the_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "token")
            with open(path, "w") as handle:
                handle.write("  abc123\n")
            os.environ.pop("THINGIVERSE_TOKEN", None)
            self.assertEqual(fm.load_token(path), "abc123")
            os.environ["THINGIVERSE_TOKEN"] = "fromenv"
            try:
                self.assertEqual(fm.load_token(path), "fromenv")
            finally:
                del os.environ["THINGIVERSE_TOKEN"]
            self.assertIsNone(fm.load_token(os.path.join(tmp, "missing")))


class UntrustedTextTests(unittest.TestCase):
    def test_public_url_is_used_only_on_https_thingiverse(self):
        good = dict(THINGIVERSE[0])
        self.assertEqual(fm.shape_thingiverse(good)["url"], "https://www.thingiverse.com/thing:10")
        for bad in ("http://www.thingiverse.com/thing:10", "https://evil.example/thing:10", "javascript:alert(1)",
                    "https://www.thingiverse.com.evil.example/x", "https://user@www.thingiverse.com/x",  # scan-ignore: credentials-in-URL test case
                    "https://thingiverse.com:8443/x", "https://thingiverse.com:abc/x", "https://www.thingiverse.com/\x1b[31m", 42):
            item = dict(good, public_url=bad)
            self.assertEqual(fm.shape_thingiverse(item)["url"], "https://www.thingiverse.com/thing:10", bad)
        self.assertEqual(fm.shape_thingiverse(dict(good, public_url="https://thingiverse.com/thing:10"))["url"],
                         "https://thingiverse.com/thing:10")

    def test_names_and_authors_lose_control_characters_and_are_capped(self):
        item = dict(PRINTABLES[0], name="\x1b[31mRed\x1b[0m\r\n  Hook\x07\x9b" + "y" * 300,
                    user={"publicUsername": "ana\u202e\tmoc"})
        shaped = fm.shape_printables(item)
        self.assertTrue(shaped["name"].startswith("Red Hook "))
        self.assertLessEqual(len(shaped["name"]), fm.TEXT_MAX)
        self.assertEqual(shaped["author"], "ana moc")
        thing = fm.shape_thingiverse(dict(THINGIVERSE[0], name="a\x00b", creator={"name": "\x1b]0;x\x07bob"}))
        self.assertEqual(thing["name"], "a b")
        self.assertNotIn("\x1b", fm.render([shaped, thing]))

    def test_an_api_error_message_is_cleaned_too(self):
        def opener(request, timeout=0):
            return io.BytesIO(json.dumps({"errors": [{"message": "\x1b[2Jboom"}]}).encode())
        _, notes = fm.collect("x", 1, "printables", opener, None)
        self.assertNotIn("\x1b", notes[0])


class RankAndRenderTests(unittest.TestCase):
    def setUp(self):
        self.items = [fm.shape_printables(i) for i in PRINTABLES] + [fm.shape_thingiverse(THINGIVERSE[0])]

    def test_sort_by_makes_mixes_sites_and_puts_the_most_printed_first(self):
        ranked = fm.rank(self.items, "makes")
        self.assertEqual([i["makes"] for i in ranked], [50, 30, 2])

    def test_downloads_sort_treats_a_missing_count_as_zero(self):
        self.assertEqual(fm.rank(self.items, "downloads")[-1]["site"], "Thingiverse")

    def test_render_tags_the_site_and_shows_na_for_hidden_downloads(self):
        text = fm.render(self.items)
        self.assertIn("[Thingiverse] Nice Hook", text)
        self.assertIn("downloads n/a", text)
        self.assertIn("NO derivatives", text)
        self.assertIn("https://www.printables.com/model/1-wall-mount", text)

    def test_empty_result_suggests_modeling_from_scratch(self):
        self.assertIn("model it from scratch", fm.render([]))

    def test_main_end_to_end_with_both_sites(self):
        opener = fake(PRINTABLES, THINGIVERSE)
        self.assertEqual(fm.main(["hook", "--sort", "makes", "--json"], opener, token="tok"), 0)
        self.assertEqual(len(opener.requests), 2)


if __name__ == "__main__":
    unittest.main()
