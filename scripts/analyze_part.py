#!/usr/bin/env python3
"""analyze_part.py - look at a part, measure it, and say how to slice it.

Why this exists
    A table of "good settings" is not enough: the right setting depends on the SHAPE. A sphere fights the
    staircase effect, a bracket fights overhangs, a thin plate fights the nozzle width. This script measures
    the geometry, then turns the measurements into (1) questions only the owner can answer, (2) slicer
    settings split into "global" and "this object only", and (3) scenarios worth slicing and comparing.

What it measures (units are assumed to be millimetres)
    size and volume | area by surface slope | staircase-prone area | flat top area | round vertical walls
    (visible seam) | overhang area that needs support | likely bridge span | bed contact | thinnest walls
    (ray cast) | and, for the six ways to stand the part up, the height, contact, overhang and staircase
    numbers, so the choice of orientation comes with evidence.

What it does NOT do
    It does not slice, and it does not know your printer's real time or filament use: it proposes scenarios,
    and the slice gives the real numbers. Everything here is a heuristic, each rule names its source in
    docs/12-slicing-by-part.md. Thickness is sampled, not exhaustive.

Usage
    python3 scripts/analyze_part.py part.stl
    python3 scripts/analyze_part.py plate.3mf --finish smooth --purpose functional
    python3 scripts/analyze_part.py part.stl --json            # machine-readable, for the assistant
Needs: Python 3.8+ and numpy.
"""
import argparse
import json
import math
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter

try:
    import numpy as np
except ImportError:  # pragma: no cover
    sys.exit("This script needs numpy: python3 -m venv .venv && .venv/bin/pip install numpy")

NOZZLE = 0.4                     # mm, override with --nozzle
OVERHANG_FROM_HORIZONTAL = 40.0  # OrcaSlicer default threshold angle (support wiki)
FLAT_COS = 0.985                 # |nz| above this counts as flat (about 10 degrees)
BRIDGE_WARN_MM = 40.0            # Bambu wiki guidance: longer bridges sag whatever you set

# Real preset names shipped for the Bambu Lab P2S 0.4 nozzle (OrcaSlicer 2.4.2 resources).
PRESETS = {0.08: "0.08mm High Quality @BBL P2S", 0.12: "0.12mm High Quality @BBL P2S",
           0.16: "0.16mm Standard @BBL P2S", 0.20: "0.20mm Standard @BBL P2S",
           0.24: "0.24mm Standard @BBL P2S"}


# --------------------------------------------------------------------------- reading meshes
def read_stl(path):
    with open(path, "rb") as handle:
        data = handle.read()
    if len(data) >= 84:
        count = struct.unpack("<I", data[80:84])[0]
        if 84 + count * 50 == len(data):
            dtype = np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")])
            return np.frombuffer(data, dtype, count, 84)["v"].astype(np.float64)
    text = data.decode("utf-8", "replace")
    nums = re.findall(r"vertex\s+(\S+)\s+(\S+)\s+(\S+)", text)
    if not nums:
        raise ValueError(f"{path}: not a readable STL")
    return np.array(nums, dtype=np.float64).reshape(-1, 3, 3)


def _parse_transform(text):
    if not text:
        return np.eye(4)
    m = [float(x) for x in text.split()]
    matrix = np.eye(4)
    matrix[:3, :3] = np.array([m[0:3], m[3:6], m[6:9]]).T   # 3MF is row-vector: v' = v * M
    matrix[:3, 3] = m[9:12]
    return matrix


def read_3mf(path):
    """Every build item of a 3MF as (name, triangles), components and transforms resolved."""
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".model")]
        objects = {}
        build = []
        for name in names:
            root = ET.fromstring(z.read(name))
            ns = {"m": root.tag.split("}")[0].strip("{")}
            for obj in root.iterfind(".//m:resources/m:object", ns):
                key = (name, obj.get("id"))
                mesh = obj.find("m:mesh", ns)
                entry = {"name": obj.get("name") or f"object-{obj.get('id')}", "tris": None, "components": []}
                if mesh is not None:
                    verts = np.array([[float(v.get(a)) for a in "xyz"] for v in mesh.iterfind("m:vertices/m:vertex", ns)])
                    tris = np.array([[int(t.get(a)) for a in ("v1", "v2", "v3")] for t in mesh.iterfind("m:triangles/m:triangle", ns)])
                    entry["tris"] = verts[tris] if len(tris) else np.zeros((0, 3, 3))
                for comp in obj.iterfind("m:components/m:component", ns):
                    path_attr = comp.get("{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path")
                    target = (path_attr.lstrip("/") if path_attr else name, comp.get("objectid"))
                    entry["components"].append((target, _parse_transform(comp.get("transform"))))
                objects[key] = entry
            if name.endswith("3dmodel.model"):
                for item in root.iterfind(".//m:build/m:item", ns):
                    build.append((name, item.get("objectid"), _parse_transform(item.get("transform"))))

    def resolve(key, matrix, depth=0):
        entry = objects.get(key)
        if entry is None or depth > 8:
            return []
        parts = []
        if entry["tris"] is not None and len(entry["tris"]):
            tri = entry["tris"]
            flat = np.c_[tri.reshape(-1, 3), np.ones(len(tri) * 3)] @ matrix.T
            parts.append(flat[:, :3].reshape(-1, 3, 3))
        for target, sub in entry["components"]:
            parts.extend(resolve(target, matrix @ sub, depth + 1))
        return parts

    items = []
    for name, oid, matrix in build:
        parts = resolve((name, oid), matrix)
        if parts:
            label = objects.get((name, oid), {}).get("name", f"object-{oid}")
            items.append((label, np.concatenate(parts)))
    if not items:  # no build section: take every object that has a mesh
        for key, entry in objects.items():
            if entry["tris"] is not None and len(entry["tris"]):
                items.append((entry["name"], entry["tris"]))
    return items


def load_parts(path):
    if path.lower().endswith(".3mf"):
        return read_3mf(path)
    return [(path.rsplit("/", 1)[-1], read_stl(path))]


# --------------------------------------------------------------------------- geometry
def face_data(tris):
    e1, e2 = tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0]
    cross = np.cross(e1, e2)
    length = np.linalg.norm(cross, axis=1)
    keep = length > 1e-12
    return tris[keep], cross[keep] / length[keep][:, None], length[keep] / 2.0


def signed_volume(tris):
    return float(np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2])).sum() / 6.0)


UP_AXES = {"+Z": (0, 0, 1), "-Z": (0, 0, -1), "+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0)}


def rotation_to_up(axis):
    """Rotation matrix that sends `axis` to +Z."""
    a = np.array(axis, float)
    z = np.array([0.0, 0.0, 1.0])
    if np.allclose(a, z):
        return np.eye(3)
    if np.allclose(a, -z):
        return np.diag([1.0, -1.0, -1.0])
    v = np.cross(a, z)
    c = float(a @ z)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k / (1 + c)


def _components_of_flat(tris, idx, tol=0.05):
    """Group flat, down-facing triangles into connected patches (shared corners). Returns index groups."""
    if len(idx) == 0:
        return []
    corners = np.round(tris[idx].reshape(-1, 3) / tol).astype(np.int64)
    ids = {}
    tri_corner = []
    for c in map(tuple, corners):
        tri_corner.append(ids.setdefault(c, len(ids)))
    tri_corner = np.array(tri_corner).reshape(-1, 3)
    parent = list(range(len(ids)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in tri_corner:
        for u, v in ((a, b), (b, c)):
            ru, rv = find(u), find(v)
            if ru != rv:
                parent[ru] = rv
    groups = {}
    for n, row in enumerate(tri_corner):
        groups.setdefault(find(row[0]), []).append(idx[n])
    return list(groups.values())


def orientation_metrics(tris, normals, areas, rotation):
    """Numbers for one way of standing the part up (rotation sends the chosen 'up' axis to +Z)."""
    t = tris @ rotation.T
    n = normals @ rotation.T
    z_min = float(t[:, :, 2].min())
    z_max = float(t[:, :, 2].max())
    zc = t[:, :, 2].mean(axis=1)
    total = float(areas.sum())
    on_bed = (n[:, 2] < -FLAT_COS) & (zc - z_min < 0.06)
    down = n[:, 2] < -np.cos(np.radians(OVERHANG_FROM_HORIZONTAL))
    support_mask = down & ~on_bed
    flat_down = (n[:, 2] < -FLAT_COS) & ~on_bed
    abs_nz = np.abs(n[:, 2])
    stair = (abs_nz > 0.35) & (abs_nz < FLAT_COS) & ~on_bed
    # widest gap that would have to be bridged: the short side of each flat, down-facing patch
    spans = []
    for group in _components_of_flat(t, np.flatnonzero(flat_down)):
        pts = t[group].reshape(-1, 3)
        dims = pts.max(axis=0) - pts.min(axis=0)
        spans.append(float(min(dims[0], dims[1])))
    return {
        "flat_overhang_mm2": round(float(areas[flat_down].sum()), 1),
        "height_mm": round(z_max - z_min, 2),
        "bed_contact_mm2": round(float(areas[on_bed].sum()), 1),
        "support_area_mm2": round(float(areas[support_mask].sum()), 1),
        "support_share": round(float(areas[support_mask].sum()) / total, 4),
        "staircase_share": round(float(areas[stair].sum()) / total, 4),
        "longest_bridge_mm": round(max(spans), 1) if spans else 0.0,
    }


def sample_thickness(tris, normals, areas, samples=240, seed=1):
    """Distance from sampled surface points to the opposite wall, along the inward normal."""
    m = len(tris)
    if m == 0:
        return []
    rng = np.random.default_rng(seed)
    if m > 250000:
        samples = 80
    probs = areas / areas.sum()
    picks = rng.choice(m, size=min(samples, m), replace=False, p=probs)
    weights = rng.dirichlet(np.ones(3), size=len(picks))
    origins = np.einsum("ij,ijk->ik", weights, tris[picks]) - normals[picks] * 1e-3
    dirs = -normals[picks]
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = v1 - v0, v2 - v0
    out = []
    for start in range(0, len(picks), 16):
        o = origins[start:start + 16][:, None, :]
        d = dirs[start:start + 16][:, None, :]
        pvec = np.cross(d, e2[None])
        det = np.einsum("ijk,jk->ij", pvec, e1)
        with np.errstate(all="ignore"):
            inv = 1.0 / det
            tvec = o - v0[None]
            u = np.einsum("ijk,ijk->ij", tvec, pvec) * inv
            qvec = np.cross(tvec, e1[None])
            v = np.einsum("ijk,ijk->ij", d.repeat(len(v0), 1), qvec) * inv
            t = np.einsum("jk,ijk->ij", e2, qvec) * inv
            hit = (np.abs(det) > 1e-12) & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4)
            t = np.where(hit, t, np.inf)
        out.extend(t.min(axis=1).tolist())
    return [x for x in out if np.isfinite(x)]


def analyze(name, tris, nozzle=NOZZLE):
    if len(tris) and signed_volume(tris) < 0:      # inside-out mesh: turn every triangle around
        tris = tris[:, [0, 2, 1]]
    tris, normals, areas = face_data(tris)
    if len(tris) == 0:
        raise ValueError(f"{name}: no triangles")
    total = float(areas.sum())
    lo, hi = tris.reshape(-1, 3).min(axis=0), tris.reshape(-1, 3).max(axis=0)
    size = hi - lo
    current = orientation_metrics(tris, normals, areas, np.eye(3))
    up = normals[:, 2] > FLAT_COS
    flat_up = float(areas[up].sum())
    at_top = up & (tris[:, :, 2].mean(axis=1) >= hi[2] - 0.3)
    top_flat = float(areas[at_top].sum())
    vertical = np.abs(normals[:, 2]) < 0.1
    azimuth = np.degrees(np.arctan2(normals[vertical, 1], normals[vertical, 0]))
    off_grid = np.abs(((azimuth + 45) % 90) - 45) > 3.0
    vertical_area = float(areas[vertical].sum())
    round_wall = float(areas[vertical][off_grid].sum())
    thickness = sample_thickness(tris, normals, areas)
    th = np.array(thickness if thickness else [np.nan])
    orient = {axis: orientation_metrics(tris, normals, areas, rotation_to_up(vec)) for axis, vec in UP_AXES.items()}
    contact = max(current["bed_contact_mm2"], 1e-6)
    return {
        "name": name,
        "size_mm": [round(float(x), 2) for x in size],
        "volume_cm3": round(abs(signed_volume(tris)) / 1000.0, 2),
        "surface_cm2": round(total / 100.0, 1),
        "current": current,
        "flat_top_mm2": round(top_flat, 1),
        "flat_up_mm2": round(flat_up, 1),
        "round_vertical_share": round(round_wall / total, 4),
        "vertical_share": round(vertical_area / total, 4),
        "thin_wall_mm": {
            "min": round(float(th.min()), 2) if thickness else None,
            "p10": round(float(np.percentile(th, 10)), 2) if thickness else None,
            "share_below_2_lines": round(float((th < 2 * nozzle).mean()), 3) if thickness else 0.0,
            "share_below_1_line": round(float((th < nozzle).mean()), 3) if thickness else 0.0,
            "samples": len(thickness)},
        "aspect": round(current["height_mm"] / math.sqrt(contact), 2),
        "orientations": orient,
    }


# --------------------------------------------------------------------------- rules
def best_orientation(features):
    """Fewest overhang mm2 first, then more bed contact, then lower height.

    An orientation only competes if it can actually stand: enough bed contact and not too tall for its
    footprint (standing a 100 mm bar on a 3 mm edge removes overhang and adds a failed print).
    """
    cur_key = "+Z"
    table = features["orientations"]
    now = table[cur_key]

    def stands(m):
        contact = m["bed_contact_mm2"]
        return contact >= max(100.0, 0.4 * now["bed_contact_mm2"]) and m["height_mm"] / math.sqrt(contact) <= 3.5

    candidates = {k: v for k, v in table.items() if k == cur_key or stands(v)}
    ranked = sorted(candidates.items(), key=lambda kv: (round(kv[1]["support_area_mm2"], -1), -kv[1]["bed_contact_mm2"], kv[1]["height_mm"]))
    best, data = ranked[0]
    better = data["support_area_mm2"] < 0.5 * now["support_area_mm2"] and now["support_area_mm2"] > 60
    return (best if better else cur_key), better


def snap_layer(x):
    return min(PRESETS, key=lambda k: abs(k - x))


# --------------------------------------------------------------------------- knowledge
# Every rule names where it comes from and how far to trust it:
#   sourced     a page gives this value or mechanism (URL in SRC)
#   disputed    sources disagree; the more conservative side is applied and the disagreement is shown
#   heuristic   this project's own threshold, easy to change here
#   unverified  reported but not confirmed from a real page: shown as a suggestion, never applied
SRC = {
    "orca-wall-gen": "https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_wall_generator",
    "orca-seam": "https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_seam",
    "orca-vlh": "https://www.orcaslicer.com/wiki/print_prepare/prepare_variable_layer_height",
    "obico-vlh": "https://www.obico.io/blog/orca-slicer-adaptive-and-variable-layer-height-guide-smoother-3d-prints/",
    "orca-ironing": "https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_ironing",
    "orca-support": "https://www.orcaslicer.com/wiki/print_settings/support/support_settings_support",
    "orca-bridging": "https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_bridging",
    "orca-patterns": "https://www.orcaslicer.com/wiki/print_settings/strength/strength_settings_patterns",
    "orca-brim": "https://www.orcaslicer.com/wiki/print_settings/others/others_settings_brim",
    "orca-precision": "https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_precision",
    "orca-tolerance": "https://github.com/OrcaSlicer/OrcaSlicer/wiki/tolerance_calib",
    "cnc-width": "https://www.cnckitchen.com/blog/the-effect-of-extrusion-width-on-strength-and-quality-of-3d-prints",
    "prusa-vlh": "https://help.prusa3d.com/article/variable-layer-height-function_1750",
    "prusa-support": "https://help.prusa3d.com/article/support-material_1698",
    "stacksheriff": "https://stacksheriff.com/3d-printing/orcaslicer-support-settings/",
    "bambu-forum-008": "https://forum.bambulab.com/t/surface-problem-at-0-08-height/53851",
    "orca-issue-6789": "https://github.com/OrcaSlicer/OrcaSlicer/issues/6789",
    "ellis-cooling": "https://ellis3dp.com/Print-Tuning-Guide/articles/cooling_and_layer_times.html",
    "3dprinterly-dome": "https://3dprinterly.com/how-to-3d-print-a-dome-or-sphere-without-supports/",
    "bambu-bridge": "https://wiki.bambulab.com/en/software/bambu-studio/parameter/bridge",
    "mandarin3d": "https://mandarin3d.com/blog/text-and-engravings-best-practices-for-readable-3d-printed-text",
    "printago-ironing": "https://printago.io/guides/orca-slicer-ironing",
    "bambu-multicolor-text": "https://forum.bambulab.com/t/help-on-first-layer-multi-color-text-prints-on-2nd-layer/170340",
    "orca-flush": "https://www.orcaslicer.com/wiki/print_settings/multimaterial/multimaterial_settings_flush_options",
    "eolas-purge": "https://eolasprints.com/en-us/blogs/advanced-3d-printing/bambu-lab-ams-multi-colour-explained",
    "qidi-dragon": "https://qidi3d.com/blogs/news/3d-print-articulated-dragons-guide",
    "sovol-pip": "https://www.sovol3d.com/blogs/news/print-in-place-3d-printing-how-to-design-hinges-joints-and-moving-parts-that-actually-work",
    "bambu-pip-forum": "https://forum.bambulab.com/t/print-in-place-hinge-tolerances/111715",
    "qidi-fits": "https://qidi3d.com/blogs/news/how-to-3d-print-interlocking-parts-and-assemblies",
    "cnc-inserts": "https://www.cnckitchen.com/blog/tips-and-tricks-for-heat-set-inserts",
    "prusa-watertight": "https://help.prusa3d.com/article/watertight-prints_112324",
    "obico-vase": "https://www.obico.io/blog/orca-slicers-spiral-vase-vase-mode-a-deep-dive/",
    "gridpilot": "https://gridpilot.us/blog/gridfinity-print-settings-guide",
    "bambu-large-prints": "https://forum.bambulab.com/t/large-prints-say-goodbye-to-warping/240898",
    "meshra-lid": "https://meshra.ai/blog/3d-printed-box-with-a-lid",
    "3dsourced-minis": "https://www.3dsourced.com/guides/fdm-3d-printing-miniatures-guide/",
    "bambu-figures": "https://forum.bambulab.com/t/best-filament-and-setting-for-action-figure-models/7134",
    "cnc-45": "https://www.cnckitchen.com/blog/stop-printing-flat-the-45-secret-for-stronger-parts",
    "qidi-brackets": "https://us.qidi3d.com/blogs/print-lab/3d-printed-shelf-brackets-load-capacity-design",
    "litho-guide": "https://www.3dprinterstuff.com/workshop/lithophane-3d-printing-guide",
    "litho-forum": "https://forum.bambulab.com/t/printing-lithophanes-flat-or-vertical/84574",
    "yt-ironing-grid": "https://www.youtube.com/watch?v=b0tqtJJ8Lf0",
    "yt-ironing-navy": "https://www.youtube.com/watch?v=vowkUstjZlE",
    "yt-p2s-review": "https://www.youtube.com/watch?v=ik9yv4BVGlg",
    "project": "this project",
}

# Setting names this script may write, all confirmed on 2026-09-21 to exist in the settings block that OrcaSlicer 2.4.2
# appends to its G-code. A typo here would be ignored silently by the slicer, so the tests check every applied key against it.
ORCA_KEYS = {
    "wall_loops", "sparse_infill_density", "wall_generator", "ironing_type", "top_shell_layers", "seam_position", "seam_slope_type",
    "enable_support", "support_type", "support_interface_top_layers", "thick_bridges", "brim_type", "brim_width",
    "inner_wall_line_width", "sparse_infill_line_width", "sparse_infill_pattern", "elefant_foot_compensation",
    "support_style", "outer_wall_speed", "initial_layer_speed", "bridge_flow", "spiral_mode", "ironing_flow", "ironing_speed",
    "ironing_spacing", "xy_hole_compensation",
}

SMALL_MM = 25.0          # largest side at or under this: a small part that can overheat
THICK_MM = 40.0          # smallest side at or over this, and solid (with THICK_CM3): a bulk part
THICK_CM3 = 40.0
FLAT_LARGE_MM2 = 4000.0  # bed contact of a wide, low part: warping risk
FLAT_LARGE_H = 6.0


# What the part is FOR, which a mesh cannot show. Chosen with --use, or asked as a question when unknown.
USES = {
    "text": ("text, plaque, keychain, nameplate", "raised or engraved lettering needs strokes wider than the nozzle"),
    "multicolor": ("several colours with the AMS", "colour changes cost purge time and filament"),
    "flexi": ("print-in-place, articulated, flexi toys", "the gap between moving parts must stay open"),
    "fit": ("mates with another part: snap, press fit, screw boss", "a printed hole is smaller than modelled"),
    "container": ("box, organizer, tray, bin, lid", "floors, walls and lids"),
    "watertight": ("holds liquid, leak-proof", "seams and thin walls are the leak path"),
    "vase": ("spiral vase", "one continuous wall, no seam"),
    "figurine": ("figurine, miniature, organic model", "fine detail, supports on visible faces"),
    "bracket": ("hook, bracket, wall mount, load-bearing", "the layers must not be pulled apart"),
    "lithophane": ("lithophane or part seen against light", "infill and layer height show through"),
}


def detect_uses(features):
    """Only what geometry can honestly suggest: an open container has floors below its rim and is mostly air."""
    size = features["size_mm"]
    solidity = features["volume_cm3"] * 1000.0 / max(size[0] * size[1] * size[2], 1e-6)
    if features["flat_up_mm2"] - features["flat_top_mm2"] >= 300 and solidity < 0.6:
        return ["container"]
    return []


def archetypes(features):
    """Which kinds of part this is, with the number that says so. A part can be several at once."""
    cur, thin, size = features["current"], features["thin_wall_mm"], features["size_mm"]
    found = {}
    if cur["staircase_share"] >= 0.30:
        found["curved"] = f"{cur['staircase_share']:.0%} of the surface is a gentle slope"
    if features["round_vertical_share"] >= 0.25:
        found["round_walls"] = f"{features['round_vertical_share']:.0%} of the surface is a round vertical wall"
    if thin["p10"] is not None and (thin["p10"] < 0.8 or thin["share_below_2_lines"] > 0.05):
        found["thin"] = f"wall thickness at the thin end is {thin['p10']} mm"
    if max(size) <= SMALL_MM:
        found["small"] = f"largest side is {max(size):.0f} mm"
    if size[2] / max(min(size[0], size[1]), 1e-6) > 3:
        found["tall_thin"] = f"{size[2]:.0f} mm tall on a footprint {min(size[0], size[1]):.0f} mm across"
    if min(size) >= THICK_MM and features["volume_cm3"] >= THICK_CM3 and thin["p10"] is not None and thin["p10"] >= 6:
        found["thick"] = f"smallest side is {min(size):.0f} mm and walls are {thin['p10']} mm at the thin end"
    if cur["height_mm"] <= FLAT_LARGE_H and cur["bed_contact_mm2"] >= FLAT_LARGE_MM2:
        found["flat_large"] = f"{cur['bed_contact_mm2'] / 100:.0f} cm2 on the bed, only {cur['height_mm']} mm tall"
    if cur["support_share"] > 0.02 or cur["support_area_mm2"] > 150:
        found["overhang"] = f"{cur['support_area_mm2']} mm2 steeper than {OVERHANG_FROM_HORIZONTAL:.0f} degrees"
    if cur["longest_bridge_mm"] >= 15:
        found["bridge"] = f"a bridge of about {cur['longest_bridge_mm']} mm"
    if features["flat_top_mm2"] >= 300:
        found["flat_top"] = f"{features['flat_top_mm2'] / 100:.1f} cm2 of flat top"
    return found


def recommend(features, finish, purpose, backlit, nozzle=NOZZLE, uses=()):
    cur, thin, size = features["current"], features["thin_wall_mm"], features["size_mm"]
    kinds = archetypes(features)
    uses = set(uses) | (set(detect_uses(features)) if not uses else set())
    reasons, questions, settings, notes, rules = [], [], {}, [], []

    def rule(kind, key, value, why, src, status="sourced", apply=True):
        """Record a rule. Applied ones also go into `settings`; unverified ones stay suggestions."""
        applied = apply and status != "unverified" and key is not None and value is not None
        if applied:
            settings[key] = value
        rules.append({"kind": kind, "key": key, "value": value, "why": why, "source": SRC.get(src, src),
                      "status": status, "applied": applied})

    # ---- layer height, from the finish you want and the shape
    stair, walls = cur["staircase_share"], {"decorative": 2, "functional": 3, "load": 4}.get(purpose, 2)
    if finish == "smooth":
        layer = 0.12
        reasons.append(f"finish=smooth -> 0.12 mm layers: thinner lines are less visible on every wall, and {stair:.0%} of the surface is a gentle slope")
        if "curved" in kinds:
            rule("curved", None, None, "Also turn on variable layer height (right-click the object, Adaptive, quality end): thin layers only where the slope is gentle. "
                 "One test printed a sphere 27.7% faster than uniform 0.2 with the ladder effect almost gone.", "obico-vlh")
            rule("curved", None, None, "0.08 mm is not always better: reports of blisters and strike artifacts at 0.08 on a Bambu P1S, with 0.12 more reliable. Slice both and look.",
                 "bambu-forum-008", "disputed", apply=False)
    elif finish == "fast":
        layer = 0.24
        reasons.append("finish=fast -> 0.24 mm layers (the practical ceiling for a 0.4 nozzle is 0.32)")
    else:
        layer = 0.16 if stair >= 0.30 else 0.20
        reasons.append(f"finish=standard, {stair:.0%} gentle slope -> {layer} mm layers")
    for u, value in (("flexi", 0.16), ("watertight", 0.16), ("vase", 0.20), ("lithophane", 0.12), ("figurine", 0.12)):
        if u in uses and not (finish == "fast" and u in ("figurine", "lithophane")):
            layer = value
            reasons.append(f"use={u} -> {value} mm layers: {USES[u][1]}")
    layer = snap_layer(layer)
    preset = PRESETS[layer]
    if layer == 0.16:
        notes.append("A reviewer of the P2S reports an overhang-related artifact with the 0.16 mm Standard profile, obvious on the P2S and not yet fixed by Bambu (October 2025, one video): check the overhangs of the first print, or use 0.12 or 0.20. " + SRC["yt-p2s-review"])
    if 0.08 <= layer <= 0.12:
        notes.append("The High Quality presets also slow the outer wall (60 mm/s against 200), so the extra time is speed as much as layers. Slice both and compare real times.")

    # ---- thin and delicate
    infill = {"decorative": 10, "functional": 15, "load": 25}.get(purpose, 15)
    if backlit:
        infill = 100
        reasons.append("part is seen against light -> near-solid infill, otherwise the grid shows through")
    if "thin" in kinds:
        fits = max(1, int(thin["p10"] / 0.42))
        if fits < walls:
            walls = fits
            rule("thin", "wall_loops", fits, f"walls are {thin['p10']} mm thick: only about {fits} line(s) of 0.42 mm fit, more walls cannot exist", "project", "heuristic")
        rule("thin", "wall_generator", "arachne", "Arachne varies line width to fit thin walls and text; Classic drops walls under about two lines. "
             "Reports disagree on very small geometry: if a detail looks lumpy, slice with Classic and step through the layers.", "orca-wall-gen", "disputed")
        if thin["p10"] < 0.4:
            questions.append(f"About {thin['share_below_1_line']:.0%} of the surface sits on walls thinner than one {nozzle} mm line (10th percentile {thin['p10']} mm). Thicken them in the model, or accept that they may not print?")
        if thin["p10"] < 0.6 and "small" in kinds:
            rule("thin", None, None, "For miniatures and very small text a 0.2 mm nozzle is the real tool (layers 0.04 to 0.14, but flow near 2 mm3/s and clogs more). "
                 "One forum thread reports 0.2 mm clogging on a P2S after an April 2026 firmware update.", "https://forum.bambulab.com/t/help-needed-0-2mm-nozzle-on-p2s/250888", "unverified", apply=False)
    else:
        settings["wall_generator"] = "arachne"
    settings["wall_loops"] = walls
    settings["sparse_infill_density"] = f"{infill}%"

    # ---- small parts overheat
    if "small" in kinds or "tall_thin" in kinds:
        rule("small", None, None, "Small parts and spires get too little time per layer to cool: keep 'slow down for layer cooling' on, or print several copies at once so each layer has time to cool.",
             "ellis-cooling", "sourced", apply=False)

    # ---- thick, solid bulk: save time and filament without losing strength
    if "thick" in kinds:
        rule("thick", "inner_wall_line_width", 0.6, "Strength follows the amount of material, not the nozzle: wide lines (about 150%) print the bulk faster. The outer wall keeps its normal width so the surface stays clean.", "cnc-width")
        rule("thick", "sparse_infill_line_width", 0.6, "Same rule for the infill. Artifacts start near 160%; wide lines need the hotend to keep up.", "cnc-width")
        if purpose != "load":
            rule("thick", "sparse_infill_pattern", "adaptivecubic", "Adaptive Cubic saves time and filament on large parts; Lightning only for non-structural ones.", "orca-patterns")
        elif purpose == "load":
            rule("thick", "sparse_infill_pattern", "gyroid", "Gyroid, Cubic or Quarter Cubic for strength.", "orca-patterns")
        rule("thick", "top_shell_layers", max(3, 5 if layer <= 0.12 else 4), "At least 3 top and bottom layers, more adds strength.", "https://www.orcaslicer.com/wiki/print_settings/strength/strength_settings_top_bottom_shells")
        if finish == "smooth":
            questions.append(f"This is a bulk part of {features['volume_cm3']} cm3: {int(round(size[2] / layer))} layers at {layer} mm. Is the surface visible on all sides? If only one face matters, 0.20 mm with wide inner lines can save hours.")

    # ---- flat tops and ironing
    flat_top = features["flat_top_mm2"]
    if finish == "smooth" and flat_top >= 300 and stair < 0.5:
        rule("flat_top", "ironing_type", "topmost", "Ironing smooths the last layer with a second, nearly dry pass: flat tops only.", "orca-ironing")
        rule("flat_top", None, None, "The slicer's default ironing (about 30 mm/s, 10% flow) made the top look worse than no ironing in one video; a speed by flow test plate found 30% and 50 mm/s best on that printer, and another video found 15 mm/s and 20%. Print a small test plate per filament instead of trusting a number.", "yt-ironing-grid", "disputed", apply=False)
        rule("flat_top", "top_shell_layers", 5 if layer <= 0.12 else 4, "Ironing smooths, it does not fill gaps: it needs solid layers under it.", "project", "heuristic")
        reasons.append(f"{flat_top / 100:.1f} cm2 of flat top -> ironing on the topmost surface, with enough solid layers under it")
        questions.append("Is the top face the one people see? Ironing adds time and only helps flat tops.")
    elif flat_top >= 300 and finish != "smooth":
        questions.append("There is a large flat top. Do you want it smooth (ironing, slower) or is the normal finish fine?")
    if finish == "smooth" and flat_top < 300 <= features["flat_up_mm2"]:
        questions.append("Flat faces look up inside the part (floors, steps) but the highest point is not flat. Iron those too? It adds time and only shows if someone sees them.")

    # ---- seam on round walls
    if "round_walls" in kinds:
        if purpose == "load":
            rule("round_walls", "seam_position", "random", "A load-bearing round part: random spreads the weak point along the wall.", "orca-seam")
        else:
            rule("round_walls", "seam_position", "aligned", "Aligned puts the seam in a hidden facet; on a smooth cylinder nothing hides it, so scarf goes on top.", "orca-seam")
            if min(size[0], size[1]) * 3.14 >= 20:
                rule("round_walls", "seam_slope_type", "external", "Scarf seam on the contour: the only seam type that leaves no visible mark. Needs pressure advance calibrated first, and a wall longer than the 20 mm scarf. "
                     "Sources disagree on scarf height (0 to 50% of a layer).", "orca-seam", "disputed")

    # ---- overhangs, supports, bridges
    if "overhang" in kinds:
        flat_share = cur["flat_overhang_mm2"] / max(cur["support_area_mm2"], 1)
        kind_support = "normal(auto)" if flat_share > 0.5 or cur["longest_bridge_mm"] >= 25 else "tree(auto)"
        rule("overhang", "enable_support", 1, f"{cur['support_area_mm2']} mm2 of overhang steeper than {OVERHANG_FROM_HORIZONTAL:.0f} degrees from horizontal", "orca-support")
        rule("overhang", "support_type", kind_support,
             "Large flat undersides: normal (grid) supports. Organic or curved parts: tree supports, which use less material and scar less." if kind_support == "normal(auto)" else
             "Tree supports for organic and curved parts: less material, easier to remove, fewer marks.", "stacksheriff")
        rule("overhang", "support_interface_top_layers", 2, "Two interface layers give a clean underside; three is rougher and more than three is hard to remove.", "stacksheriff")
        rule("overhang", None, None, "Top Z distance: 0.2 mm at 0.2 mm layers (0.15 to 0.25). The Prusa guide says 50 to 75% of the layer height. The profile default is kept.", "prusa-support", "disputed", apply=False)
        rule("overhang", None, None, "A cleaner alternative to supports: turn the part, chamfer the overhang to 45 degrees, or split it and glue.", "orca-support", "sourced", apply=False)
        questions.append("Is a support scar on the overhanging face acceptable, or is that face visible?")
        if "curved" in kinds:
            questions.append("This is a round part with a curved base: cut it in two, flat side down, and glue? It needs no supports and the surface is better.")
            rule("curved", None, None, "A sphere or dome split in two prints with no supports; a whole sphere needs tree supports at the base.", "3dprinterly-dome", apply=False)
    best, worth = best_orientation(features)
    if worth:
        questions.append(f"Standing the part with {best} up removes most overhang ({features['orientations'][best]['support_area_mm2']} mm2 against {cur['support_area_mm2']} now). Is that face allowed to be up, or does it need the current orientation?")
    if "bridge" in kinds:
        if cur["longest_bridge_mm"] > BRIDGE_WARN_MM:
            rule("bridge", None, None, f"A bridge of about {cur['longest_bridge_mm']} mm is longer than the {BRIDGE_WARN_MM:.0f} mm that sags whatever you set: split it with a support island or reorient.", "bambu-bridge", apply=False)
        else:
            rule("bridge", "thick_bridges", 1, "Thick bridges are stronger on longer spans, at the cost of a rougher underside.", "orca-bridging")

    # ---- tall and thin, wide and flat: adhesion
    if "tall_thin" in kinds:
        rule("tall_thin", "brim_type", "outer_only", "Tall on a small footprint: a brim widens the base.", "orca-brim")
        rule("tall_thin", "brim_width", 5, "5 mm; the slicer's automatic brim is capped at 20 mm and skipped below 5.", "orca-brim")
    if "flat_large" in kinds:
        rule("flat_large", "brim_type", "outer_only", "Large flat parts lift at the corners as PLA cools: a brim holds them (5 to 15 mm reported).", "orca-brim")
        rule("flat_large", "brim_width", 8, "Middle of the reported 5 to 15 mm range.", "orca-brim", "heuristic")
        rule("flat_large", "elefant_foot_compensation", 0.2, "About 0.2 to 0.3 mm over roughly 5 layers is typical, but no page confirms it for this printer.", "orca-precision", "unverified")
        notes.append("Wide, low part: wash the plate first, keep the fan low on the first layers and the bed near 60 to 65 C.")

    # ---- fits
    if purpose in ("functional", "load"):
        questions.append("Does it fit against another part (a hole, a pin, a snap)? If so, run Orca's tolerance test once and set the hole compensation from it: no page gives a universal value.")
        rule("fit", None, None, "Calibrate the X-Y hole and contour compensation with the tolerance test; starting points from a blog are 0.2 to 0.3 mm clearance and 0.1 to 0.15 mm interference.", "orca-tolerance", "unverified", apply=False)

    # ---- what the part is for
    if "text" in uses:
        rule("text", None, None, "Raised text on a 0.4 mm nozzle: strokes 1.0 mm wide at least (1.5 better), 0.5 mm high at least (0.8 better), letters 4 mm tall at least (6 better). Engraved: 0.5 mm wide (0.8 better) and 0.3 mm deep (0.5 better). Bold sans-serif capitals. A blog reports 0.4 to 0.6 mm strokes as the absolute floor.", "mandarin3d", "disputed", apply=False)
        rule("text", "ironing_type", "topmost", "Iron the top of raised text and plaques.", "printago-ironing")
        rule("text", None, None, "The best ironing speed and flow differ by filament and printer (15 mm/s and 20% in one video, 50 mm/s and 30% in another, and the default was worse than none in the second): print a speed by flow test plate once per filament.", "yt-ironing-navy", "disputed", apply=False)
        rule("text", "ironing_flow", "10%", "Low flow (8 to 18% reported), 0.1 mm line spacing, 15 to 30 mm/s. The Orca wiki lists the settings but gives no defaults.", "printago-ironing")
        rule("text", "ironing_spacing", 0.1, "0.1 mm line spacing.", "printago-ironing")
        rule("text", "ironing_speed", 20, "15 to 30 mm/s.", "printago-ironing")
        rule("text", None, None, "Wall generator for small letters is contested: a forum fix and a closed GitHub issue report lumpy Arachne on small text, the Orca wiki recommends Arachne for thin features. Slice both and step through the layers.", "https://github.com/OrcaSlicer/OrcaSlicer/issues/10364", "disputed", apply=False)
        if thin["p10"] is not None and thin["p10"] < 1.0:
            questions.append(f"Some strokes are about {thin['p10']} mm wide. Raised text wants 1.0 mm or more on a 0.4 mm nozzle. Thicken the letters?")
    if "multicolor" in uses:
        rule("multicolor", None, None, "Make coloured text a separate object or part and assign the filament to it: the paint tool gives uneven layers and colours. A 3 mm base with 0.8 mm text is a working example.", "bambu-multicolor-text", apply=False)
        rule("multicolor", None, None, "Coloured text at least 0.6 mm thick (3 layers at 0.2), about 1 mm for readable contrast, because PLA is somewhat translucent.", "https://forum.bambulab.com/t/how-to-get-one-layer-color-text/192873", apply=False)
        rule("multicolor", None, None, "Expect 15 to 25% of filament and time lost to purging on complex prints (a vendor blog, no per-change figure).", "eolas-purge", "unverified", apply=False)
        rule("multicolor", None, None, "Flush into infill or support only works with the prime tower on, and only on dark, opaque parts: never white, translucent or thin-walled, or the mixed colour shows through.", "orca-flush", apply=False)
        rule("multicolor", None, None, "Flush multiplier: about 0.6 for same-material changes (community), 1.2 to 2.0 when colour bleeds (one guide). Neither is confirmed on a primary page.", "https://www.3dprofilefix.com/guides/flushing-volumes-guide.html", "disputed", apply=False)
        questions.append("How many colour changes, and which colours? Light-to-light and dark-to-dark orders purge less than light-to-dark.")
    if "flexi" in uses:
        rule("flexi", None, None, "Modelled clearance of 0.25 mm per side is the start (0.20 to 0.30 for PLA): under 0.15 welds shut. Bambu forum users report 0.1 to 0.2 working with tuned flow; other guides say 0.3 to 0.5 for hinges and chains. Print a tolerance test in 0.1 mm steps first.", "qidi-dragon", "disputed", apply=False)
        rule("flexi", "enable_support", 0, "Supports jam joints.", "qidi-dragon")
        rule("flexi", "wall_loops", 3, "Three walls, Arachne, pins upright.", "sovol-pip")
        rule("flexi", "elefant_foot_compensation", 0.2, "The first layer squashes out and fuses the base; reported values run from 0.1 to 0.3 mm. Also model a 0.5 mm 45-degree chamfer on the bottom edges of mating parts.", "sovol-pip", "disputed")
        rule("flexi", "outer_wall_speed", 50, "Outer wall 40 to 60 mm/s gives cleaner gap edges.", "qidi-dragon")
        rule("flexi", "initial_layer_speed", 20, "First layer about 20 mm/s.", "qidi-dragon")
        rule("flexi", "bridge_flow", 0.95, "Under-extruded bridges (0.90 to 0.95) do not sag into the gap.", "sovol-pip")
        rule("flexi", "brim_type", "outer_only", "A 3 to 5 mm brim on complex bases.", "https://3dbite.com/articulated-and-print-in-place-models-how-they-actually-work/")
        rule("flexi", "brim_width", 4, "Middle of 3 to 5 mm.", "https://3dbite.com/articulated-and-print-in-place-models-how-they-actually-work/", "heuristic")
        rule("flexi", None, None, "Fan at 100% after layer 2 or 3, and let the part cool before flexing each joint through its full range, tail to head, without heat. The slicer's gap closing radius is 0.049 mm in this profile, far below half of a 0.2 mm gap, so it will not close it (read from the settings block; the reasoning is this project's).", "qidi-dragon", apply=False)
    if "fit" in uses:
        rule("fit", None, None, "Snap hook against catch: 0.10 to 0.20 mm on the latching face; a PLA hook at least 1.2 mm thick with a length to thickness ratio of 2:1 at least, 3:1 ideal; a lid on a box 0.20 to 0.25 mm per side.", "qidi-fits", apply=False)
        rule("fit", None, None, "Press fit: interference of 0.05 to 0.15 mm (one guide); another summary says clearance instead. Calibrate the X-Y hole compensation with Orca's tolerance test: values of +0.1 to +0.2 mm are quoted, and printed holes come out about 0.25 mm small.", "qidi-fits", "disputed", apply=False)
        rule("fit", None, None, "M3 heat-set insert: hole 4.2 mm as printed (4.0 if drilled), depth the insert length plus 0.5 to 1.5 mm, wall about 2 mm around it, boss 1.5 to 2 times the insert diameter, 4 to 6 walls.", "cnc-inserts", apply=False)
        rule("fit", "wall_loops", max(walls, 4), "Screw bosses want 4 to 6 walls.", "sovol-pip", "heuristic")
    if "container" in uses:
        heavy = purpose == "load"
        rule("container", "wall_loops", 4 if heavy else 3, "Organizers: 3 walls at least, 4 for heavy tools.", "gridpilot")
        rule("container", "sparse_infill_density", "25%" if heavy else "12%", "10 to 15% for light storage, 20 to 30% for heavy (a vendor blog).", "gridpilot")
        rule("container", None, None, "Top shell over sparse infill: 0.8 to 1.2 mm (5 to 6 layers at 0.2); raise infill to 20 to 25% if the top pillows. Sources disagree between 0.8 and 1.2.", "https://www.3dprofilefix.com/guides/how-to-fix-top-surface.html", "unverified", apply=False)
        rule("container", None, None, "Lid: 0.2 mm per side for a friction fit (0.10 to 0.15 snug, 0.30 to 0.40 loose), lip 4 to 8 mm, walls 1.6 to 2.4 mm. Print orientation of the lid: no source confirmed it.", "meshra-lid", apply=False)
        if max(size[0], size[1]) >= 150:
            rule("container", "brim_type", "outer_only", "Large open boxes warp: brim about 4 mm, bed 5 to 10 C warmer, rounded corners, gyroid infill.", "bambu-large-prints")
            rule("container", "brim_width", 4, "About 4 mm (Bambu forum guide).", "bambu-large-prints")
    if "watertight" in uses:
        rule("watertight", "wall_loops", 4, "Four walls is Prusa's minimum for PLA: perimeters matter far more than solid layers.", "prusa-watertight")
        rule("watertight", None, None, "Flow ratio +0.02 to +0.05 and nozzle 5 to 10 C hotter for fuller lines; seams and the solid-to-perimeter transitions are the main leak path. A forum thread wants monotonic-line bottoms with 5 to 7 layers, Prusa found 2 to 7 all waterproof.", "prusa-watertight", "disputed", apply=False)
    if "vase" in uses:
        rule("vase", "spiral_mode", 1, "Spiral vase: one continuous wall, no seam, no top layers, no infill (Orca forces them). Worth it for decorative pieces, not for heavy use or overhangs; Prusa found a single perimeter waterproof only with flow at 105 to 110%.", "obico-vase")
    if "figurine" in uses:
        rule("figurine", "support_type", "tree(auto)", "Tree supports touch the model only at branch tips.", "stacksheriff")
        rule("figurine", "support_style", "organic", "Organic tree style for figures; Bambu forum users suggest Hybrid instead.", "stacksheriff", "disputed")
        rule("figurine", "enable_support", 1, "Figures with limbs or weapons almost always need supports.", "3dsourced-minis")
        rule("figurine", "support_interface_top_layers", 2, "Two interface layers on detailed faces (three is rougher).", "stacksheriff")
        rule("figurine", None, None, "Tilt the model 45 degrees on X in Orca's gizmo when limbs stick out at 90 degrees: fewer and simpler supports. Or print upright so supports touch only the least visible underside.", "3dsourced-minis", apply=False)
        rule("figurine", None, None, "Layer height 0.12 to 0.16 for detail, 0.08 for showcase pieces; use variable layer height, thinner on face and hands.", "bambu-figures", apply=False)
        rule("figurine", None, None, "Support angle: 45 degrees (one guide) against 55 to 60 (another); they define the angle differently, so check the definition before using either.", "stacksheriff", "disputed", apply=False)
        rule("figurine", None, None, "For painting: about 220 grit to start, then 2 to 3 thin coats of filler primer; a 0.2 mm layer needs roughly three times the sanding of 0.05 mm. Wall count and infill for a hollow figure: no source found.", "https://3dprinterly.com/best-way-to-sand-smooth-3d-printed-objects-surfaces/", "unverified", apply=False)
    if "bracket" in uses:
        rule("bracket", "wall_loops", 6, "6 to 8 walls for brackets, with a 5:1 safety factor; other summaries say 4 to 6 with 40% infill.", "qidi-brackets", "disputed")
        rule("bracket", None, None, "Orient so the load runs along the layers, not pulling them apart: in one test, layers flat to the bed held 63 MPa, at 45 degrees 40 MPa, upright 31 MPa. Around every screw hole keep at least 3 mm of solid boss.", "cnc-45", apply=False)
    if "lithophane" in uses:
        rule("lithophane", "sparse_infill_density", "100%", "Infill casts shadows and bright spots. Two guides differ: all walls (99 loops) against 100% rectilinear with 1 to 2 walls.", "litho-guide", "disputed")
        rule("lithophane", None, None, "White PLA, thickness 0.6 to 0.8 mm at the brightest areas up to 3.0 mm at the darkest; upright for small pieces (brim 8 mm or more, 30 to 40 mm/s), flat for large ones, but the two sources disagree.", "litho-forum", "disputed", apply=False)
    if not uses and purpose is None:
        questions.append("What is it: text or keychain, print-in-place, box or organizer, figurine, bracket or hook, something that mates with another part, a vase, several colours? Each one changes the settings.")

    if purpose is None:
        questions.append("What is it for: decoration, a working part, or something carrying load? It sets walls and infill.")
    if finish is None:
        questions.append("Smooth or fast? Smooth is your usual choice; say how much time you have and I slice both and show the real numbers.")

    order = {"text": -3, "multicolor": -3, "flexi": -3, "fit": -3, "container": -3, "watertight": -3, "vase": -3, "figurine": -3, "bracket": -3, "lithophane": -3, "curved": 0, "thick": 1, "thin": 2, "overhang": 3, "round_walls": 4, "flat_top": 5, "tall_thin": 6, "flat_large": 7, "bridge": 8, "small": 9, "fit": 10}
    questions = list(dict.fromkeys(questions))
    return {"preset": preset, "layer_height": layer, "settings": settings, "reasons": reasons, "notes": notes,
            "questions": questions, "kinds": kinds, "uses": sorted(uses), "rules": sorted(rules, key=lambda r: order.get(r["kind"], 99)),
            "best_orientation": best, "orientation_worth_it": worth}


def scenarios(features, purpose, backlit, uses=()):
    """Slices worth comparing; the numbers come from the slicer, not from here."""
    out = []
    labels = [("smooth", "Smooth"), ("standard", "Balanced"), ("fast", "Fast")]
    for finish, label in labels:
        r = recommend(features, finish, purpose or "functional", backlit, uses=uses)
        out.append({"label": label, "finish": finish, "preset": r["preset"], "settings": r["settings"],
                    "layers": int(round(features["size_mm"][2] / r["layer_height"]))})
    return out


# The machine and filament side of quality, which no part shape can fix. Printed by --machine.
MACHINE = [
    ("Run the calibrations in this order: temperature, max volumetric speed, pressure advance, flow, retraction. Blogs put flow before pressure advance, so this order is the wiki's, not a consensus.",
     "https://www.orcaslicer.com/wiki/guides/calibration_guide", "disputed"),
    ("On a Bambu printer, untick 'Flow calibration' in Orca's calibration dialogs: the printer's own automatic calibration would conflict.",
     "https://www.orcaslicer.com/wiki/calibration/flow_ratio_calib", "sourced"),
    ("The printer calibrates flow dynamics (its pressure advance, one value per filament) and vibration compensation on its own. It does NOT choose flow ratio, temperature or max volumetric speed for a third-party filament.",
     "https://forum.bambulab.com/t/community-tech-talk-deep-dive-into-auto-flow-dynamics-calibration/225453", "sourced"),
    ("A filament profile copied from another slicer or printer is a starting point: flow ratio, max volumetric speed and temperature belong to that printer, nozzle and spool. Re-run them on this printer.",
     "https://3dbite.com/best-3d-printer-calibration-routine-bambu-a1-a2l/", "sourced"),
    ("Flow ratio: filament setting, sane range 0.95 to 1.05, changed in steps of 0.01 (the YOLO method).",
     "https://www.orcaslicer.com/wiki/material_settings/filament/material_flow_ratio_and_pressure_advance", "sourced"),
    ("Max volumetric speed: test 5 to 20 mm3/s in 0.5 steps, then take 10 to 20% off the result.",
     "https://www.orcaslicer.com/wiki/calibration/volumetric_speed_calib", "sourced"),
    ("Ringing and ghosting: outer wall acceleration lower than inner wall, top surface equal to outer wall. No number was found, and Input Shaping in the wiki is written for Klipper and Marlin.",
     "https://www.orcaslicer.com/wiki/print_settings/speed/speed_settings_acceleration", "unverified"),
    ("Visible banding on outer walls: untick 'slow printing down for better layer cooling', or use 'don't slow down outer walls'. Speed changes leave bands, notably in silk PLA.",
     "https://forum.bambulab.com/t/more-filament-settings-functionality-dont-slow-down-outer-walls/171832", "sourced"),
    ("Arc fitting is not a quality feature: it changes how the path is encoded, and a closed issue reports bumps on outer walls that turning it off fixed. Bambu's wiki says it is on by default for high speed.",
     "https://github.com/OrcaSlicer/OrcaSlicer/issues/7315", "disputed"),
    ("Plain PLA is usually fine undried; silk, carbon-fibre and wood filaments need drying (45 to 55 C for 6 to 8 h). Stringing and bubbles are the sign of damp filament.",
     "https://wiki.bambulab.com/en/filament/pla", "unverified"),
    ("Textured PEI plate: wash with dish detergent and water, keep fingers off it, never use acetone. Oils from skin ruin first-layer adhesion.",
     "https://wiki.bambulab.com/en/filament-acc/acc/pei-plate-clean-guide", "unverified"),
]


def split_global_and_object(per_object):
    """Settings shared by most objects go to the plate (global); the rest are per-object overrides."""
    keys = {k for r in per_object.values() for k in r["settings"]}
    plate, overrides = {}, {name: {} for name in per_object}
    for key in sorted(keys):
        values = [json.dumps(r["settings"].get(key)) for r in per_object.values()]
        common, freq = Counter(values).most_common(1)[0]
        if freq * 2 > len(values) or len(values) == 1:
            plate[key] = json.loads(common)
        for name, r in per_object.items():
            if json.dumps(r["settings"].get(key)) != common and key in r["settings"]:
                overrides[name][key] = r["settings"][key]
    return plate, {k: v for k, v in overrides.items() if v}


# --------------------------------------------------------------------------- report
def report(features, rec, name):
    cur = features["current"]
    lines = [f"== {name}", f"size {features['size_mm']} mm | volume {features['volume_cm3']} cm3 | surface {features['surface_cm2']} cm2",
             "", "What I see",
             f"  gentle slopes (staircase)      {cur['staircase_share']:>6.0%}   round vertical walls {features['round_vertical_share']:>4.0%}",
             f"  flat top                    {features['flat_top_mm2'] / 100:>5.1f} cm2   bed contact {cur['bed_contact_mm2'] / 100:.1f} cm2   aspect {features['aspect']}",
             f"  overhang needing support    {cur['support_area_mm2']:>6} mm2   longest bridge {cur['longest_bridge_mm']} mm",
             f"  wall thickness, thin end    {features['thin_wall_mm']['p10']} mm (10th percentile; smallest sample {features['thin_wall_mm']['min']} mm, noisy at edges)",
             "", "Kind of part: " + (", ".join(f"{k} ({v})" for k, v in rec["kinds"].items()) or "plain, nothing special"),
             "Use: " + (", ".join(rec["uses"]) or "not said"),
             "", "Standing up (up axis: height | contact | overhang | staircase)"]
    for axis, m in features["orientations"].items():
        mark = "  <- as given" if axis == "+Z" else ("  <- suggested" if axis == rec["best_orientation"] and rec["orientation_worth_it"] else "")
        lines.append(f"  {axis}   {m['height_mm']:>7} mm | {m['bed_contact_mm2']:>8} mm2 | {m['support_area_mm2']:>8} mm2 | {m['staircase_share']:>5.0%}{mark}")
    lines += ["", f"Base preset: {rec['preset']}  (layer {rec['layer_height']} mm)"]
    lines += [f"  {k} = {v}" for k, v in rec["settings"].items()]
    lines += ["", "Rules behind it  [status: sourced | disputed | heuristic | unverified = suggestion only]"]
    for r in rec["rules"]:
        what = f"{r['key']} = {r['value']}" if r["applied"] else ("suggestion" if r["status"] == "unverified" else "note")
        lines.append(f"  [{r['status']}] {r['kind']}: {what}")
        lines.append(f"      {r['why']}")
        lines.append(f"      {r['source']}")
    if rec["reasons"]:
        lines += ["", "Why"] + [f"  - {r}" for r in rec["reasons"]]
    if rec["notes"]:
        lines += ["", "Notes"] + [f"  - {r}" for r in rec["notes"]]
    if rec["questions"]:
        lines += ["", "Questions for the owner"] + [f"  ? {q}" for q in rec["questions"][:4]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("model", nargs="?", default="", help=".stl or .3mf (every object of a 3MF is analysed)")
    parser.add_argument("--finish", choices=["smooth", "standard", "fast"], help="surface preference")
    parser.add_argument("--purpose", choices=["decorative", "functional", "load"])
    parser.add_argument("--backlit", action="store_true", help="the part is seen against light")
    parser.add_argument("--use", default="", help="what the part is for, comma separated: " + ", ".join(USES))
    parser.add_argument("--machine", action="store_true", help="print the machine and filament side of quality and exit")
    parser.add_argument("--nozzle", type=float, default=NOZZLE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.machine:
        for text, source, status in MACHINE:
            print(f"[{status}] {text}\n    {source}")
        return 0
    if not args.model:
        parser.error("give a .stl or .3mf file (or use --machine)")
    uses = [u.strip() for u in args.use.split(",") if u.strip()]
    unknown = [u for u in uses if u not in USES]
    if unknown:
        parser.error(f"unknown --use {unknown}; choose from {', '.join(USES)}")

    parts = load_parts(args.model)
    if not parts:
        sys.exit("No mesh found.")
    results, recs = {}, {}
    for name, tris in parts:
        feats = analyze(name, tris, args.nozzle)
        results[name] = feats
        recs[name] = recommend(feats, args.finish, args.purpose, args.backlit, args.nozzle, uses)
    plate, overrides = split_global_and_object(recs)
    if args.json:
        payload = {"objects": {n: {"features": results[n], "recommendation": recs[n],
                                   "scenarios": scenarios(results[n], args.purpose, args.backlit, uses)} for n in results},
                   "plate_settings": plate, "object_overrides": overrides}
        print(json.dumps(payload, indent=2, default=float))
        return 0
    for name in results:
        print(report(results[name], recs[name], name), "\n")
    if len(results) > 1:
        print("== Plate (global) settings:", json.dumps(plate))
        print("== Per-object overrides:", json.dumps(overrides) if overrides else "none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
