# Modeling and delivering a part

This is the method behind step 1 and 2 of the workflow. The short checklist version, ready to copy into your notes, is
[`knowledge-base-template/modeling-method.md`](../knowledge-base-template/modeling-method.md). Here is the reasoning.

## The principle: fail early, where it is cheap

A mistake in the model costs seconds to fix in the CAD tool, minutes to fix after slicing, and hours after a failed print. So
every check is placed as **early** as it can go. The order below is that order.

## 0. Look for it before you model it

The best model is often already made, printed and reviewed by other people. Searching first saves hours and starts from something that has survived real printers.

```bash
python3 scripts/find_models.py "controller wall mount" --sort makes
```

It prints one numbered shortlist from Printables and Thingiverse with the signals that matter:

| Signal | What it tells you |
|---|---|
| **makes** (people who posted a finished print) | the best hint that the model is printable; sort by it |
| downloads and likes | popularity, which is not the same as quality |
| licence | a *no derivatives* licence matters if you plan to adapt the part, and a *non-commercial* one if you plan to sell it |
| date | old models may predate today's printers and slicers |

**Thingiverse** is searched by the same script through its official API. It needs a free app token from your own account (create the app at `thingiverse.com/apps/create`, copy the **App Token**, not the Client ID or Secret, into `~/.config/print-workflow/thingiverse-token` with `pbpaste` so it never appears in a chat); the token is sent in a header, never in the URL, and the search hides adult and private things and drops hits that ignore half of your words. Thingiverse does not show download counts in search, so that column reads n/a; it does show **makes** and whether the licence allows derivatives. New apps may wait in an approval queue, and a 401 in the meantime is normal. The other sites are covered by a browser tool, because their search pages read fine in a real browser even though scripts are blocked: **MakerWorld** and **Thangs** (many paid models). Read the results list, never the download button. The counts these pages show do not say which is likes and which is downloads, so do not claim it. **Cults3D** shows a bot check: do not get around it, search there by hand. Thangs also offers search by image, useful when you only have a picture.
so the licence and the author's notes are seen. Only when nothing fits, or the user has a reference image or file of their own, does the assistant model from scratch.

The Printables endpoint is unofficial: it can change or start blocking requests. If it fails, the script says so and the assistant falls back to the web.

## 1. Ask only what you cannot know

| Ask | Do not ask |
|---|---|
| what the part is for and where it sits or attaches | a measure that has a market standard (the width of a utility-knife blade, of VHB tape) |
| exact dimensions **with a named axis** (X length, Y width, Z height) | a detail you can assume, such as an unspecified corner radius |
| the operation: recess, through hole, extrusion, union of shapes | the file name; pick a sensible one |
| one color, or several bodies? | |

Two habits are worth their weight in gold:

- **Never block on a minor detail.** Assume a reasonable value, name it as a parameter, say so in the delivery.
- **Treat "about 38 to 40 degrees" as an estimate.** Derive the angle from the geometry (`atan(height / run)`) and tell the person if the
  computed value differs from what they said.

## 2. Model for printing, not just for looking

1. **Every measure is a named parameter**, never a loose number in the middle of the geometry. The result explains itself and can be
   re-opened months later.
2. **Model in print orientation**: the largest flat face on the bed (Z = 0). Orientation is geometry, so it is under your control; support and plate
   settings are the slicer's. If no orientation avoids supports, say which face you recommend on the bed and where support is likely.
3. **Check the total size against your bed** before doing anything else.
4. **Look at it before you send it**: a rendered view catches a cut in the wrong place or a part that came out hollow by accident.

## 3. Check the exported mesh

A pretty render is not verification. Validate the **exported STL**:

```python
import trimesh
m = trimesh.load("part.stl")
m.is_watertight   # a closed mesh?
m.volume          # > 0. If it is almost equal to the bounding box's volume, the part came out SOLID
m.extents         # fits your bed?
```

The volume check is the one that pays for itself: a CAD script can export a **solid block** where a cavity was intended,
with no error, and the top view still looks normal. (`pip install trimesh` in a virtual environment; the `dfam-check` skill
covers part of this too.)

## 4. The conference board: a PNG made from the exported STL

For every part, produce one technical drawing **from the exported STL itself**, never an illustration and never a screenshot of the
preview. It lets you approve a part at a glance, without opening the slicer. It must show:

1. the **outline taken from the mesh** (a section through a plane), not a hand-drawn silhouette; a cross-section if the inside matters,
   a horizontal section if the arrangement in plan matters;
2. **the name of each part written on it**, not a numbered legend to cross-reference;
3. **real dimensions in mm**;
4. **arrows on the features that were decided**: notch, magnet pocket, seam, ramp, label tab, clearance;
5. **the orientation stated**: where the front is, where the top is;
6. deliver it as a **PNG**.

`matplotlib` over `trimesh` output does the job: `mesh.section(plane_origin=..., plane_normal=...)` gives the outline, and
`fig.savefig("board.png", dpi=200)` writes it. For an assembly, take two horizontal sections (body and rim), overlay them, and
offset each part to where it sits when assembled.

## 5. Deliver the whole package

| Deliver | Why |
|---|---|
| the **source** (script or CAD file) | so it can be re-opened and changed |
| **STL** | mandatory when there are several bodies or colors |
| **3MF** | the format most slicers open directly |
| the **conference board PNG** | approval at a glance |
| a **short text**: differences from the request, whether supports or a special orientation are likely, the **slicing recommendation** | so the person understands *why*, not just receives a file |

## Several colors or bodies

A 3MF made **outside** a slicer cannot carry per-object color or print settings; only the slicer writes those when it saves its own
project. So for a multi-color part, export **one STL per body or color**, plus the assembled set, and assign the colors in the slicer
after importing them as separate objects. Do not promise a "ready to print" multi-color 3MF from outside the app. (This is documented for
Bambu Studio; Orca is a fork, so it very probably behaves the same, but that was not verified here.)

## Auditing a downloaded file

`unzip -l file.3mf` tells you a lot before you open anything:

- only `3D/3dmodel.model` and metadata: **pure mesh**, with no print settings, so configure everything by hand;
- a `Metadata/` folder with `project_settings.config` and `plate_*.json`: a **complete slicer project**. Open the text files and check
  the printer and filament match yours.

An `.stl` carries no settings at all; analyse the mesh (size, watertight) and report whether it fits.
Also look for **duplicated overlapping objects**, a known problem in Bambu Studio and its forks, sometimes already present in the file you download.
