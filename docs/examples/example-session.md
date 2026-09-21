# An illustrative session

> **This is an illustration, not a transcript.** It shows how the conductor skill behaves so you know what to expect and what to insist on.
> Names and numbers are invented.

## The request

> **You:** I need a wall hook for a 25 mm broom handle. It will hold about 3 kg.

## Step 1: model (the assistant asks only what it cannot know)

> **Assistant:** Two questions. What does it screw into, wood or a wall plug, and roughly how far from the wall should the handle sit?
> I will assume M4 screws and a 3 mm clearance around the handle, since both are common, and I will say so at the end.
>
> **You:** Wood, 40 mm off the wall.

It builds the part in your CAD tool with every measure as a named parameter (`handle_d = 25`, `clearance = 3`, `standoff = 40`) and
**orients it in print position**: the wide back plate flat on the bed.

## Step 2: check (before anything is sliced)

> **Assistant:** Mesh check on the exported STL: watertight, yes. Volume 41 cm3 against a bounding box of 118 cm3, so it is not a solid block.
> It fits the bed with room to spare. Conference board attached as a PNG, with the part names on the drawing, the 3 mm clearance dimensioned,
> and the front and top marked.

## Step 3: recommend (and wait for you)

> **Assistant:** Slicing recommendation for `wall-hook`:
> - **Walls: 4** (your default is 2). It carries a load; *Process, Strength*.
> - **Orientation: back plate down.** The layer lines then run across the load instead of along it, which is the strong direction.
> - **Supports: none.** The hook's underside is a 45 degree chamfer, which prints clean.
> - **Brim: 5 mm.** The base is small for its height, and cold plates lift tall small-base parts.
>
> Want me to slice with that, or do you want to set it in the slicer yourself to see each change?

**You decide.** Nothing has been sliced yet.

## Step 4 and 5: slice, send

> **You:** Slice it.
>
> **Assistant:** Dry run first, then the real slice. Validated: extrusion moves present, temperatures set, nothing outside the bed.
> The warnings are Bambu-specific commands the validator does not know, which is normal. Estimated 41 g, about 2 h 10 min.
> The file is ready. Send it from the slicer, and start the print **on the printer's screen**.

## Step 6: monitor (you do nothing)

Your phone buzzes: *Print started.* An hour later, *Print paused, error code 32774.* You decode it with the snippet in the docs
(`0700 8006`, an AMS feed error), fix the feed path, resume. Later: *Print finished.*

## Step 7: log and learn

> **You:** It came out well, but the first layer was rough at one corner.
>
> **Assistant:** Logged: `wall-hook`, 41 g, success. I noted that a 5 mm brim was not quite enough on this base, and that next time for a small tall base
> I will suggest 8 mm. It is in your printer notes now.

That last line is the point of the whole design: the tenth recommendation is better than the first because every print leaves a note.

## What to insist on

- It **never** started the print for you.
- It **explained** every setting and where to find it.
- It said what it **assumed**.
- It waited for **you** at the recommendation.
- If any of these is missing, tighten the rules in your `SKILL.md`. See [09](../09-the-conductor-skill.md).
