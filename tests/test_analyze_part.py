"""Tests for analyze_part.py. Meshes are built here from maths: no files, no printer, no personal data.

Each shape has a known answer, so a rule that drifts shows up as a failing test.
Needs numpy; skipped without it.

Run:  python3 -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

try:
    import numpy as np
    import analyze_part as ap  # noqa: E402
except ImportError:  # pragma: no cover
    np = None


def box(x0, y0, z0, x1, y1, z1):
    v = np.array([[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
                  [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]], float)
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = []
    for a, b, c, d in quads:
        tris += [[v[a], v[b], v[c]], [v[a], v[c], v[d]]]
    return np.array(tris)


def sphere(radius=10.0, rings=24, segments=48):
    tris = []
    for i in range(rings):
        t0, t1 = np.pi * i / rings, np.pi * (i + 1) / rings
        for j in range(segments):
            p0, p1 = 2 * np.pi * j / segments, 2 * np.pi * (j + 1) / segments

            def pt(t, p):
                return radius * np.array([np.sin(t) * np.cos(p), np.sin(t) * np.sin(p), np.cos(t)]) + [0, 0, radius]
            a, b, c, d = pt(t0, p0), pt(t0, p1), pt(t1, p1), pt(t1, p0)
            if i > 0:
                tris.append([a, d, b])
            if i < rings - 1:
                tris.append([b, d, c])
    return np.array(tris)


def cylinder(radius=10.0, height=20.0, segments=64):
    tris = []
    for j in range(segments):
        p0, p1 = 2 * np.pi * j / segments, 2 * np.pi * (j + 1) / segments
        a0, a1 = [radius * np.cos(p0), radius * np.sin(p0)], [radius * np.cos(p1), radius * np.sin(p1)]
        tris.append([[*a0, 0], [*a1, 0], [*a1, height]])
        tris.append([[*a0, 0], [*a1, height], [*a0, height]])
        tris.append([[0, 0, 0], [*a1, 0], [*a0, 0]])
        tris.append([[0, 0, height], [*a0, height], [*a1, height]])
    return np.array(tris)


def extrude_polygon(points, y0, y1):
    """Watertight prism from a simple polygon in the XZ plane (ear clipping), extruded along Y."""
    pts = [tuple(p) for p in points]
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))
    if area < 0:
        pts.reverse()
    idx, ears = list(range(len(pts))), []

    def inside(p, a, b, c):
        d = lambda p1, p2, p3: (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        d1, d2, d3 = d(p, a, b), d(p, b, c), d(p, c, a)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    while len(idx) > 3:
        for k in range(len(idx)):
            a, b, c = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            pa, pb, pc = pts[a], pts[b], pts[c]
            if (pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0]) <= 0:
                continue
            if any(inside(pts[o], pa, pb, pc) for o in idx if o not in (a, b, c)):
                continue
            ears.append((a, b, c))
            idx.pop(k)
            break
    ears.append(tuple(idx))
    tris = []
    for a, b, c in ears:
        p3 = lambda q, y: [q[0], y, q[1]]
        tris.append([p3(pts[a], y0), p3(pts[b], y0), p3(pts[c], y0)])   # front cap, faces -Y
        tris.append([p3(pts[a], y1), p3(pts[c], y1), p3(pts[b], y1)])   # back cap, faces +Y
    for a, b in zip(pts, pts[1:] + pts[:1]):
        tris.append([[a[0], y0, a[1]], [b[0], y1, b[1]], [b[0], y0, b[1]]])
        tris.append([[a[0], y0, a[1]], [a[0], y1, a[1]], [b[0], y1, b[1]]])
    return np.array(tris, float)


def t_shape():
    """A wide slab on a narrow post: standing up it needs support under the slab, upside down it needs none."""
    profile = [(-5, 0), (5, 0), (5, 30), (30, 30), (30, 34), (-30, 34), (-30, 30), (-5, 30)]
    return extrude_polygon(profile, 0, 20)


def write_binary_stl(path, tris):
    import struct
    with open(path, "wb") as handle:
        handle.write(b"\0" * 80 + struct.pack("<I", len(tris)))
        for tri in tris:
            handle.write(struct.pack("<12fH", 0, 0, 0, *tri.reshape(-1), 0))


@unittest.skipIf(np is None, "numpy not installed")
class AnalyzeTests(unittest.TestCase):
    def test_cube_has_no_staircase_no_support_flat_top(self):
        f = ap.analyze("cube", box(0, 0, 0, 20, 20, 20))
        self.assertEqual(f["current"]["staircase_share"], 0)
        self.assertEqual(f["current"]["support_area_mm2"], 0)
        self.assertAlmostEqual(f["flat_top_mm2"], 400, delta=1)
        self.assertAlmostEqual(f["volume_cm3"], 8.0, delta=0.05)
        self.assertLess(f["round_vertical_share"], 0.01)

    def test_sphere_is_mostly_staircase_and_smooth_gets_thin_layers(self):
        f = ap.analyze("sphere", sphere())
        self.assertGreater(f["current"]["staircase_share"], 0.5)
        rec = ap.recommend(f, "smooth", "decorative", False)
        self.assertLessEqual(rec["layer_height"], 0.12)
        self.assertNotIn("ironing_type", rec["settings"])   # ironing does nothing on a curve

    def test_cylinder_walls_are_round_so_the_seam_is_managed(self):
        f = ap.analyze("cylinder", cylinder())
        self.assertGreater(f["round_vertical_share"], 0.3)
        rec = ap.recommend(f, "smooth", "decorative", False)
        self.assertEqual(rec["settings"]["seam_position"], "aligned")
        load = ap.recommend(f, "smooth", "load", False)
        self.assertEqual(load["settings"]["seam_position"], "random")

    def test_thin_plate_is_detected(self):
        f = ap.analyze("plate", box(0, 0, 0, 40, 40, 0.3))
        self.assertLess(f["thin_wall_mm"]["min"], 0.4)
        rec = ap.recommend(f, "standard", "functional", False)
        self.assertTrue(any("Thicken" in q for q in rec["questions"]))

    def test_overhang_prefers_standing_it_upside_down(self):
        f = ap.analyze("t", t_shape())
        self.assertAlmostEqual(f["current"]["support_area_mm2"], 1000, delta=1)   # slab underside minus the post
        best, worth = ap.best_orientation(f)
        self.assertTrue(worth)
        self.assertEqual(f["orientations"][best]["support_area_mm2"], 0)
        rec = ap.recommend(f, "standard", "functional", False)
        self.assertEqual(rec["settings"]["enable_support"], 1)
        self.assertTrue(any("Standing the part" in q for q in rec["questions"]))

    def test_never_suggests_standing_a_long_bar_on_its_edge(self):
        def m(h, contact, support):
            return {"height_mm": h, "bed_contact_mm2": contact, "support_area_mm2": support}
        features = {"orientations": {"+Z": m(6, 280, 130), "-Z": m(6, 280, 130), "+X": m(15, 3, 990),
                                     "-X": m(15, 3, 990), "+Y": m(101, 67, 29), "-Y": m(101, 38, 60)}}
        self.assertEqual(ap.best_orientation(features), ("+Z", False))

    def test_inside_out_mesh_gives_the_same_answer(self):
        good = ap.analyze("t", t_shape())
        flipped = ap.analyze("t", t_shape()[:, [0, 2, 1]])
        self.assertEqual(good["current"], flipped["current"])
        self.assertEqual(good["thin_wall_mm"], flipped["thin_wall_mm"])

    def test_flat_top_smooth_turns_on_ironing_with_enough_shell(self):
        f = ap.analyze("lid", box(0, 0, 0, 60, 40, 5))
        rec = ap.recommend(f, "smooth", "decorative", False)
        self.assertEqual(rec["settings"]["ironing_type"], "topmost")
        self.assertGreaterEqual(rec["settings"]["top_shell_layers"], 4)

    def test_backlit_forces_solid_infill(self):
        f = ap.analyze("tag", box(0, 0, 0, 40, 20, 3))
        rec = ap.recommend(f, "smooth", "decorative", True)
        self.assertEqual(rec["settings"]["sparse_infill_density"], "100%")

    def test_tall_narrow_part_gets_a_brim(self):
        f = ap.analyze("pin", box(0, 0, 0, 8, 8, 60))
        rec = ap.recommend(f, "standard", "functional", False)
        self.assertEqual(rec["settings"]["brim_type"], "outer_only")

    def test_questions_are_asked_when_intent_is_unknown(self):
        f = ap.analyze("cube", box(0, 0, 0, 20, 20, 20))
        rec = ap.recommend(f, None, None, False)
        text = " ".join(rec["questions"])
        self.assertIn("What is it for", text)
        self.assertIn("Smooth or fast", text)

    def test_layer_height_snaps_to_a_real_preset(self):
        for value in (0.09, 0.14, 0.31):
            self.assertIn(ap.snap_layer(value), ap.PRESETS)

    def test_global_and_object_settings_are_split(self):
        recs = {"a": {"settings": {"wall_loops": 3, "seam_position": "aligned"}},
                "b": {"settings": {"wall_loops": 3}},
                "c": {"settings": {"wall_loops": 3}}}
        plate, overrides = ap.split_global_and_object(recs)
        self.assertEqual(plate["wall_loops"], 3)
        self.assertEqual(overrides, {"a": {"seam_position": "aligned"}})

    def test_scenarios_have_more_layers_when_smoother(self):
        f = ap.analyze("cyl", cylinder())
        s = {x["label"]: x for x in ap.scenarios(f, "decorative", False)}
        self.assertGreater(s["Smooth"]["layers"], s["Fast"]["layers"])

    def test_reads_binary_stl_and_runs_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cube.stl")
            write_binary_stl(path, box(0, 0, 0, 10, 10, 10))
            parts = ap.load_parts(path)
            self.assertEqual(len(parts), 1)
            self.assertEqual(ap.main([path, "--json", "--finish", "smooth"]), 0)


if __name__ == "__main__":
    unittest.main()
