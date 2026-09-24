# Tool radar: what else exists, and what made it into the flow

The main cycle (model, check, slice, send, monitor, log) uses a small set of tools on purpose. Around it there is a fast-moving
ecosystem of websites, slicer forks and AI generators. This page keeps them in one place, each with a **status**, so that when the
user asks "is there a tool for X?" the assistant reads this page first instead of searching from scratch.

The conductor skill points here (rule 6). Add a row whenever a new tool shows up in a video, a search or a conversation. When a
tool becomes part of the cycle, move it into `KB/flow.md` and mark it **in the flow** here.

| Status | Meaning |
|---|---|
| **in the flow** | used for real, has a place in the cycle |
| **on demand** | the assistant opens it when that kind of job comes up |
| **radar** | known, not tested |
| **dropped** | evaluated and left out, with the reason |

Nothing on this page was installed. Most entries are websites; the assistant opens them in its own browser when needed, so the
user does not have to bookmark anything.

Last reviewed: 2026-09-23. Main source for the first batch: The Next Layer, "new 3D printing tools" video (YouTube `K3Fmc98ug2I`).

## Filament data

| Tool | What it does | Status |
|---|---|---|
| **3D Filament Profiles** (`3dfilamentprofiles.com`) | Database of about 26,000 filaments: exact color as hex, brand print settings, drying, **empty spool weight**, HueForge TD, similar colors across brands. Also spool inventory and 3MF-based consumption, which need an account | **in the flow** since 2026-09-23, read-only, no login |
| Fil Library (`filament.thenextlayer.com`) | Explains each filament type: what it is good for, strengths, weaknesses, with the video that introduced it | on demand, when the user considers a new material |

### Using the filament database

- Brand pages: `3dfilamentprofiles.com/filaments/<brand-slug>` and `3dfilamentprofiles.com/defaults/<brand-slug>`. Find the slug
  with the search box on `/brands` (brand names are often written without spaces).
- The tables load with JavaScript. With a browser tool, navigate and wait about 4 seconds before reading the page text.
- Three uses in the cycle:
  1. **Weigh a spool:** scale reading minus the brand's empty spool weight = filament left. A cross-check for the filament log.
  2. **Pick a color:** the hex value previews a multicolor part and matches a real object; typing a hex into the search finds close
     colors from other brands.
  3. **Before buying a new line or brand:** check the recommended nozzle temperature and the spool weight.
- **Keep the inventory in your own filament log.** The site's inventory needs an account, and creating accounts is the user's call.

## Gridfinity and drawer organization

| Tool | What it does | Status |
|---|---|---|
| **tooltrace.ai** | Photo of tools on a sheet of paper becomes a Gridfinity bin with a cutout per tool; picks the bin size itself. Generous free tier | on demand, first choice |
| Tracefinity | Same idea, open source, can be self-hosted, more options (chamfer, smoothing, custom shapes) | on demand, when you want no account |
| Gridpilot | Same idea, with quick circles for bits and sockets and per-pocket colors | radar; still buggy (Sep 2026) |
| GridfinityGenerator.com | Box generator with uneven dividers, partial scoops, labels | on demand; 3 free models |
| Perplexing Labs Gridfinity generator | Classic free generator: bins, baseplates, vase mode, cases | on demand |
| Onshape + Gridfinity FeatureScript | 3D cutout matching the tool's shape, with a public model library | radar |

## AI that generates a 3D model from text or an image

These produce **organic meshes** (figures, animals, decor, sculpture), not dimensioned parts with holes and fits. For a functional
part, keep using CAD. Whatever they output goes through the check step of the cycle (mesh verification, DfAM), because AI meshes
often come with thin walls, holes or an uneven base.

| Tool | What it does | Status |
|---|---|---|
| Meshy (`meshy.ai`) | Text or image to 3D, textures, topology control | radar |
| Tripo (`tripo3d.ai`) | Text, one or several images to 3D; also rigging and animation | radar |
| Hyper3D Rodin (`hyper3d.ai`) | 3D generation with clean topology; Blender integration, limited free trial key | radar |
| Schematik (`schematik.io`) | **Not 3D:** describe an electronics project in plain language, get code, wiring, parts and assembly steps for Arduino, ESP32 or Pico | radar; useful when a project pairs electronics with a printed enclosure |

## Making a model unique

| Tool | What it does | Status |
|---|---|---|
| Bump Mesh (CNC Kitchen) | Applies a real texture (leather, wood, stone...) to a plain STL and hides layer lines | radar; candidate optional step between modeling and slicing. Print time goes up 2 to 3 times |
| Prime 3D (3D Revolution) | Paints gradients and even photos onto a model's surface with very fine lines (dithering) | radar; costly on a single-nozzle printer, see below |

## Multicolor without the purge

On a single-nozzle printer with an AMS, every color change purges filament. Tools that change color very often cost a lot of
filament and time there; they shine on tool changers.

| Tool | What it does | Status |
|---|---|---|
| Split3MF (`split3mf.com`) | Splits a painted 3MF into one part per color, keeps the filament colors, caps the cut and can add connector pins. Runs in the browser; the site says the file never leaves your computer. Open beta, source on GitHub | on demand, not tested. On a single-nozzle printer: print each color as its own part with no purge, then assemble. Check the result before printing; files over 10 MB may stall |

## Slicers and OrcaSlicer forks

Decision of 2026-09-23: **none of these replaces OrcaSlicer in the flow.**

| Slicer | What it is | Status and why |
|---|---|---|
| Full Spectrum | OrcaSlicer fork that blends colors by dithering; 4 filaments can look like 12 or more | radar, for the day multicolor becomes a real need. Many color changes means heavy purging on a single nozzle; test on a small part first |
| JusPrin (Obico) | OrcaSlicer fork with an AI that edits settings | dropped. Its suggestions ran heavy on infill and supports. In this workflow the assistant already does this with `analyze_part.py` and [docs/12](12-slicing-by-part.md), explaining the reason for each change |
| Prusa EasyPrint | Browser and mobile slicer | dropped for now. Slicing on a phone was not a need, and AMS printing needs a real project `.3mf` (see [docs/06](06-slicing-with-an-assistant.md)). Some brands block printing from it; not checked for Bambu |
| PreFlight | PrusaSlicer fork with advanced features | dropped. Profile migration and interface were reported as worse |

## Support

| Tool | Status |
|---|---|
| Support Fins (`printfins.com`) | in the flow as an option, not yet tested |
