# Modeling and delivery checklist

The short version. The reasoning behind each item is in `docs/08-modeling-and-delivery.md`.

## Before modeling, ask (only what has no market standard)

- [ ] What is it for, and where does it sit or attach?
- [ ] Exact dimensions with a named axis (X length, Y width, Z height)
- [ ] Operation: recess, through hole, simple extrusion, union of shapes
- [ ] One color or several bodies?
- [ ] A name for the file

Do **not** ask for measures with an obvious market standard (a utility-knife blade width, VHB
tape width): use the standard and just say you did. Never block on a minor detail: assume a
reasonable value, name it as a variable, and mention it in the delivery.

## While modeling

- [ ] Every measure is a **named parameter**, never a loose number in the geometry
- [ ] Angles are **computed** from geometry, not eyeballed
- [ ] Model **already in print orientation**: largest flat face on the bed
- [ ] Total size checked against the bed (`<X x Y x Z>`)

## Before delivering (all of it, every time)

- [ ] Export STL **and** 3MF (STL is mandatory when there are several bodies or colors)
- [ ] **Mesh check** on the exported STL: watertight, volume vs bounding box (nearly equal means the
      part came out solid), extents fit the bed
- [ ] **Conference board PNG** made from the exported STL, with part names written on the parts,
      real dimensions in mm, arrows on decided features, orientation stated
- [ ] File name like `description_LxWxH.ext`
- [ ] Text: any difference between what was asked and what was calculated; whether supports or a
      specific orientation are likely needed
- [ ] The slicing recommendation block (see `printer-profile.md`)
