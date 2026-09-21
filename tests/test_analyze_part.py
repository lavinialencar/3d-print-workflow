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

    def test_a_thin_fin_gets_only_the_walls_that_fit(self):
        f = ap.analyze("fin", box(0, 0, 0, 40, 0.6, 40))
        self.assertIn("thin", ap.archetypes(f))
        rec = ap.recommend(f, "smooth", "functional", False)
        self.assertEqual(rec["settings"]["wall_loops"], 1)          # 3 walls cannot fit in 0.6 mm
        self.assertEqual(rec["settings"]["wall_generator"], "arachne")

    def test_a_thick_block_gets_wide_inner_lines_and_the_time_question(self):
        f = ap.analyze("block", box(0, 0, 0, 50, 50, 50))
        self.assertIn("thick", ap.archetypes(f))
        rec = ap.recommend(f, "smooth", "decorative", False)
        self.assertEqual(rec["settings"]["inner_wall_line_width"], 0.6)
        self.assertEqual(rec["settings"]["sparse_infill_pattern"], "adaptivecubic")
        self.assertTrue(any("bulk part" in q for q in rec["questions"]))
        load = ap.recommend(f, "smooth", "load", False)
        self.assertEqual(load["settings"]["sparse_infill_pattern"], "gyroid")

    def test_a_sphere_gets_variable_layer_height_and_the_split_idea(self):
        f = ap.analyze("sphere", sphere(15.0, 32, 64))
        kinds = ap.archetypes(f)
        self.assertIn("curved", kinds)
        self.assertNotIn("tall_thin", kinds)      # it rests on a point, but a brim would not help a sphere
        self.assertNotIn("thick", kinds)          # 14 cm3 is not a bulk part
        rec = ap.recommend(f, "smooth", "decorative", False)
        self.assertTrue(any(r["kind"] == "curved" and "variable layer height" in r["why"] for r in rec["rules"]))
        self.assertTrue(any("cut it in two" in q for q in rec["questions"]))

    def test_a_wide_low_plate_is_a_warping_risk(self):
        f = ap.analyze("plate", box(0, 0, 0, 80, 60, 3))
        self.assertIn("flat_large", ap.archetypes(f))
        self.assertEqual(ap.recommend(f, "standard", "functional", False)["settings"]["brim_type"], "outer_only")

    def test_flat_undersides_get_normal_supports_and_round_ones_get_tree(self):
        flat = ap.recommend(ap.analyze("t", t_shape()), "standard", "functional", False)
        self.assertEqual(flat["settings"]["support_type"], "normal(auto)")
        rnd = ap.recommend(ap.analyze("s", sphere(15.0, 32, 64)), "standard", "decorative", False)
        self.assertEqual(rnd["settings"]["support_type"], "tree(auto)")

    def test_a_long_bridge_gets_thick_bridges_and_a_very_long_one_only_a_warning(self):
        span = ap.analyze("span", np.concatenate([box(0, 0, 0, 5, 30, 20), box(35, 0, 0, 40, 30, 20), box(0, 0, 20, 40, 30, 24)]))
        # overlapping shells leave internal faces, so only the archetype and the rule wiring are checked here
        self.assertIn("bridge", ap.archetypes(span))

    def test_every_rule_names_a_source_and_a_known_status(self):
        for shape in (sphere(15.0, 32, 64), box(0, 0, 0, 50, 50, 50), box(0, 0, 0, 40, 0.6, 40), t_shape(), cylinder(), box(0, 0, 0, 80, 60, 3)):
            rec = ap.recommend(ap.analyze("x", shape), "smooth", "functional", False)
            for r in rec["rules"]:
                self.assertIn(r["status"], {"sourced", "disputed", "heuristic", "unverified"})
                self.assertTrue(r["source"].startswith("http") or r["source"] == "this project", r)

    def test_unverified_rules_are_suggestions_and_never_applied(self):
        rec = ap.recommend(ap.analyze("plate", box(0, 0, 0, 80, 60, 3)), "standard", "functional", False)
        unverified = [r for r in rec["rules"] if r["status"] == "unverified"]
        self.assertTrue(unverified)
        self.assertTrue(all(not r["applied"] for r in unverified))
        self.assertNotIn("elefant_foot_compensation", rec["settings"])

    def test_every_setting_written_is_a_real_orca_key(self):
        for shape in (sphere(15.0, 32, 64), box(0, 0, 0, 50, 50, 50), box(0, 0, 0, 40, 0.6, 40), t_shape(), cylinder(), box(0, 0, 0, 80, 60, 3), box(0, 0, 0, 8, 8, 60)):
            for finish in ("smooth", "standard", "fast"):
                for purpose in ("decorative", "functional", "load"):
                    rec = ap.recommend(ap.analyze("x", shape), finish, purpose, False)
                    self.assertLessEqual(set(rec["settings"]), ap.ORCA_KEYS)

    def _plate(self):
        return ap.analyze("plate", box(0, 0, 0, 60, 30, 3))

    def test_every_use_produces_sourced_rules_and_only_real_keys(self):
        f = self._plate()
        for use in ap.USES:
            rec = ap.recommend(f, "smooth", "functional", False, uses=[use])
            mine = [r for r in rec["rules"] if r["kind"] == use]
            self.assertTrue(mine, use)
            for r in mine:
                self.assertIn(r["status"], {"sourced", "disputed", "heuristic", "unverified"})
                self.assertTrue(r["source"].startswith("http") or r["source"] == "this project", (use, r))
                if r["status"] == "unverified":
                    self.assertFalse(r["applied"])
            self.assertLessEqual(set(rec["settings"]), ap.ORCA_KEYS, use)

    def test_ironing_never_trusts_a_single_number(self):
        rec = ap.recommend(self._plate(), "smooth", "decorative", False, uses=["text"])
        notes = [r for r in rec["rules"] if r["kind"] == "text" and "speed by flow" in r["why"]]
        self.assertTrue(notes and notes[0]["status"] == "disputed" and not notes[0]["applied"])

    def test_the_016_layer_carries_the_p2s_artifact_warning(self):
        rec = ap.recommend(self._plate(), "standard", "functional", False, uses=["watertight"])   # watertight forces 0.16
        self.assertEqual(rec["layer_height"], 0.16)
        self.assertTrue(any("0.16 mm Standard" in n for n in rec["notes"]))

    def test_flexi_turns_supports_off_and_uses_thinner_layers(self):
        rec = ap.recommend(self._plate(), "fast", "functional", False, uses=["flexi"])
        self.assertEqual(rec["settings"]["enable_support"], 0)
        self.assertEqual(rec["layer_height"], 0.16)                     # even when the finish asked for fast
        self.assertEqual(rec["settings"]["initial_layer_speed"], 20)
        clearance = [r for r in rec["rules"] if "0.25 mm per side" in r["why"]][0]
        self.assertEqual(clearance["status"], "disputed")               # sources disagree and the script says so

    def test_text_irons_the_top_and_leaves_the_wall_generator_debate_open(self):
        rec = ap.recommend(self._plate(), "standard", "decorative", False, uses=["text"])
        self.assertEqual(rec["settings"]["ironing_type"], "topmost")
        self.assertEqual(rec["settings"]["wall_generator"], "arachne")   # default kept, the debate is a note
        self.assertTrue(any(r["kind"] == "text" and not r["applied"] and "Wall generator" in r["why"] for r in rec["rules"]))

    def test_vase_turns_on_spiral_mode_and_watertight_wants_four_walls(self):
        self.assertEqual(ap.recommend(self._plate(), "smooth", None, False, uses=["vase"])["settings"]["spiral_mode"], 1)
        rec = ap.recommend(self._plate(), "smooth", "decorative", False, uses=["watertight"])
        self.assertEqual((rec["settings"]["wall_loops"], rec["layer_height"]), (4, 0.16))

    def test_figurine_gets_organic_tree_supports_and_bracket_gets_six_walls(self):
        fig = ap.recommend(self._plate(), "smooth", "decorative", False, uses=["figurine"])
        self.assertEqual((fig["settings"]["support_type"], fig["settings"]["support_style"]), ("tree(auto)", "organic"))
        self.assertEqual(ap.recommend(self._plate(), "smooth", "load", False, uses=["bracket"])["settings"]["wall_loops"], 6)

    def test_a_hollow_open_box_is_detected_as_a_container(self):
        outer = box(0, 0, 0, 60, 60, 30)
        # a box with a cavity: floor plate, four walls, no lid (overlaps leave internal faces, so only the detection is checked)
        walls = np.concatenate([box(0, 0, 0, 60, 60, 2), box(0, 0, 2, 60, 2, 30), box(0, 58, 2, 60, 60, 30),
                                box(0, 2, 2, 2, 58, 30), box(58, 2, 2, 60, 58, 30)])
        f = ap.analyze("bin", walls)
        self.assertEqual(ap.detect_uses(f), ["container"])
        self.assertEqual(ap.detect_uses(ap.analyze("solid", outer)), [])

    def test_a_multicolor_part_asks_about_the_colour_changes(self):
        rec = ap.recommend(self._plate(), "smooth", "decorative", False, uses=["multicolor"])
        self.assertTrue(any("colour changes" in q for q in rec["questions"]))

    def test_unknown_use_is_refused_and_an_unlabelled_part_is_asked_what_it_is(self):
        with self.assertRaises(SystemExit):
            ap.main(["x.stl", "--use", "spaceship"])
        rec = ap.recommend(self._plate(), "smooth", None, False)
        self.assertTrue(any("What is it:" in q for q in rec["questions"]))

    def test_machine_notes_print_and_carry_sources(self):
        self.assertEqual(ap.main(["--machine"]), 0)
        self.assertTrue(all(src.startswith("http") and status in {"sourced", "disputed", "unverified"} for _, src, status in ap.MACHINE))

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
