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
    "project": "this project",
}

# Setting names this script may write, all confirmed on 2026-09-21 to exist in the settings block that OrcaSlicer 2.4.2
# appends to its G-code. A typo here would be ignored silently by the slicer, so the tests check every applied key against it.
ORCA_KEYS = {
    "wall_loops", "sparse_infill_density", "wall_generator", "ironing_type", "top_shell_layers", "seam_position", "seam_slope_type",
    "enable_support", "support_type", "support_interface_top_layers", "thick_bridges", "brim_type", "brim_width",
    "inner_wall_line_width", "sparse_infill_line_width", "sparse_infill_pattern", "elefant_foot_compensation",
}

SMALL_MM = 25.0          # largest side at or under this: a small part that can overheat
THICK_MM = 40.0          # smallest side at or over this, and solid (with THICK_CM3): a bulk part
THICK_CM3 = 40.0
FLAT_LARGE_MM2 = 4000.0  # bed contact of a wide, low part: warping risk
FLAT_LARGE_H = 6.0


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


def recommend(features, finish, purpose, backlit, nozzle=NOZZLE):
    cur, thin, size = features["current"], features["thin_wall_mm"], features["size_mm"]
    kinds = archetypes(features)
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
    layer = snap_layer(layer)
    preset = PRESETS[layer]
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

    if purpose is None:
        questions.append("What is it for: decoration, a working part, or something carrying load? It sets walls and infill.")
    if finish is None:
        questions.append("Smooth or fast? Smooth is your usual choice; say how much time you have and I slice both and show the real numbers.")

    order = {"curved": 0, "thick": 1, "thin": 2, "overhang": 3, "round_walls": 4, "flat_top": 5, "tall_thin": 6, "flat_large": 7, "bridge": 8, "small": 9, "fit": 10}
    questions = list(dict.fromkeys(questions))
    return {"preset": preset, "layer_height": layer, "settings": settings, "reasons": reasons, "notes": notes,
            "questions": questions, "kinds": kinds, "rules": sorted(rules, key=lambda r: order.get(r["kind"], 99)),
            "best_orientation": best, "orientation_worth_it": worth}


def scenarios(features, purpose, backlit):
    """Slices worth comparing; the numbers come from the slicer, not from here."""
    out = []
    labels = [("smooth", "Smooth"), ("standard", "Balanced"), ("fast", "Fast")]
    for finish, label in labels:
        r = recommend(features, finish, purpose or "functional", backlit)
        out.append({"label": label, "finish": finish, "preset": r["preset"], "settings": r["settings"],
                    "layers": int(round(features["size_mm"][2] / r["layer_height"]))})
    return out


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
    parser.add_argument("model", help=".stl or .3mf (every object of a 3MF is analysed)")
    parser.add_argument("--finish", choices=["smooth", "standard", "fast"], help="surface preference")
    parser.add_argument("--purpose", choices=["decorative", "functional", "load"])
    parser.add_argument("--backlit", action="store_true", help="the part is seen against light")
    parser.add_argument("--nozzle", type=float, default=NOZZLE)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    parts = load_parts(args.model)
    if not parts:
        sys.exit("No mesh found.")
    results, recs = {}, {}
    for name, tris in parts:
        feats = analyze(name, tris, args.nozzle)
        results[name] = feats
        recs[name] = recommend(feats, args.finish, args.purpose, args.backlit, args.nozzle)
    plate, overrides = split_global_and_object(recs)
    if args.json:
        payload = {"objects": {n: {"features": results[n], "recommendation": recs[n],
                                   "scenarios": scenarios(results[n], args.purpose, args.backlit)} for n in results},
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
