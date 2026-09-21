"""Tests for find_models.py. The network is never touched: the opener is a fake.

Run:  python3 -m unittest discover -s tests -v
"""
import io
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import find_models as fm  # noqa: E402

ITEMS = [
    {"id": "1", "name": "Wall Mount", "slug": "wall-mount", "likesCount": 400, "downloadCount": 5000, "makesCount": 2,
     "datePublished": "2025-03-29T17:36:48Z", "license": {"name": "CC BY"}, "user": {"publicUsername": "ana"}},
    {"id": "2", "name": "Wall Mount Pro", "slug": "wall-mount-pro", "likesCount": 100, "downloadCount": 900, "makesCount": 30,
     "datePublished": "2026-01-02T00:00:00Z", "license": None, "user": None},
]


def fake(payload):
    def opener(request, timeout=0):
        opener.request = request
        return io.BytesIO(json.dumps(payload).encode())
    return opener


class FindModelsTests(unittest.TestCase):
    def test_shape_builds_the_link_and_survives_missing_fields(self):
        shaped = fm.shape(ITEMS[1])
        self.assertEqual(shaped["url"], "https://www.printables.com/model/2-wall-mount-pro")
        self.assertIsNone(shaped["author"])
        self.assertIsNone(shaped["license"])
        self.assertEqual(shaped["published"], "2026-01-02")

    def test_sort_by_makes_puts_the_most_printed_first(self):
        shaped = [fm.shape(i) for i in ITEMS]
        self.assertEqual(fm.rank(shaped, "makes")[0]["id"], "2")
        self.assertEqual(fm.rank(shaped, "likes")[0]["id"], "1")
        self.assertEqual(fm.rank(shaped, "relevance")[0]["id"], "1")

    def test_search_sends_an_honest_user_agent_and_the_term(self):
        opener = fake({"data": {"result": {"items": ITEMS}}})
        self.assertEqual(len(fm.search("wall mount", 5, opener)), 2)
        self.assertIn("3d-print-workflow", opener.request.get_header("User-agent"))
        self.assertEqual(json.loads(opener.request.data)["variables"], {"q": "wall mount", "n": 5})

    def test_an_api_error_becomes_a_clear_failure_not_a_crash(self):
        opener = fake({"errors": [{"message": "blocked"}]})
        with self.assertRaises(RuntimeError):
            fm.search("x", 3, opener)
        self.assertEqual(fm.main(["x"], opener), 1)

    def test_network_failure_is_reported(self):
        def broken(request, timeout=0):
            raise urllib.error.URLError("offline")
        self.assertEqual(fm.main(["x"], broken), 1)

    def test_empty_result_suggests_modeling_from_scratch(self):
        self.assertIn("model it from scratch", fm.render([]))

    def test_render_lists_signals_and_link(self):
        text = fm.render([fm.shape(i) for i in ITEMS])
        self.assertIn("printed by others 30", text)
        self.assertIn("https://www.printables.com/model/1-wall-mount", text)


if __name__ == "__main__":
    unittest.main()
