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

Last reviewed: 2026-09-26. Sources: The Next Layer, "new 3D printing tools" (YouTube `K3Fmc98ug2I`) for the first batch, and
"12 new 3D printing apps" (YouTube `3ZcTKYUpr7M`, sponsored by Snapmaker) for the second.

## Filament data

| Tool | What it does | Status |
|---|---|---|
| **3D Filament Profiles** (`3dfilamentprofiles.com`) | Database of about 26,000 filaments: exact color as hex, brand print settings, drying, **empty spool weight**, HueForge TD, similar colors across brands. Also spool inventory and 3MF-based consumption, which need an account | **in the flow** since 2026-09-23, read-only, no login |
| Spoolio (`spoolio.net`) | Hosted web app with an account (not a spreadsheet or local files; data lives on their server). Adds spools by reading the label with the phone camera, assigns spools to printer slots, tracks moisture exposure and low stock. Free up to 50 spools and 2 printers; automatic per-print deduction (a post-processing script in the slicer) and charts are Pro. Full JSON export | radar, test the free tier only. If your own filament log already deducts per print, keep it as the source of truth; Spoolio adds camera entry, moisture and charts |
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

## Calibration

| Tool | What it does | Status |
|---|---|---|
| CN3D Docs (`docs.cn3d.eu/en`) | Interactive calibration guide: illustrated steps, calculators (extruder steps, PID, temperature tower, flow, pressure advance) and saved results per printer and filament. A visual take on the Ellis guide. Free | radar. For a new filament or brand when the printer's automatic calibration is not enough. Parts of it target Klipper and Marlin; on a Bambu printer, use what OrcaSlicer calibrates |

## Previewing files on a Mac

| Tool | What it does | Status |
|---|---|---|
| **threemf** (`github.com/guanchzhou/threemf`) | Quick Look for 3MF, STL and G-code: press Space in Finder, then "Show 3D" to orbit, pan and zoom; G-code shows the toolpath layer by layer. Finder thumbnails too | **in the flow** since 2026-09-26, `brew install --cask guanchzhou/tap/threemf` |
| ThumbHost3mf | Finder thumbnail from the image already embedded in a 3MF or G-code, static, with a "3MF" label | dropped: tested side by side, threemf does more. Do not install both; they claim the same file types |
| STEP Quick Look plugin (John Boyles) | Press Space on a STEP file | radar; reported to fail at times and to render the model in white |

## Remixing a downloaded model

| Tool | What it does | Status |
|---|---|---|
| Mesh to STEP (Native Research, `mesh2step.nativemedica.it`) | Turns STL, OBJ or 3MF into a STEP solid that CAD treats as real geometry; a mode that recognizes planes and cylinders (holes become true circles) and repairs damaged meshes | radar. For remixing in CAD a part whose author only published an STL. **The file is uploaded to their server** (deleted after an hour, per the site): not for client or private models. Open source at `github.com/tommasobbianchi/mesh2step` |

## Managing several printers

| Tool | What it does | Status |
|---|---|---|
| Watchtower (YGK3D) | Local, cloud-free dashboard for Bambu, Klipper, PrusaLink and OctoPrint. A "virtual printer" queue: the slicer sends a job and it picks a printer of that type with the right filament loaded. Filament inventory, failure detection, smart plugs, phone notifications. Runs on a Mac or a Raspberry Pi. Lifetime license from US$ 59, farm US$ 719; Kickstarter not yet open (Sep 2026) | radar. Pays off with several printers; with one, [the monitor](07-monitor-and-alerts.md) already sends alerts |

## Accessories for a Bambu P2-series printer (hardware)

From The Next Layer's product round-ups (`rIVenFlVESk`, Oct 2025; `LwP_1jZ9xu0`, Feb 2026). Nothing bought. P2-series compatibility is
listed only where the video states it.

| Item | What it is | Status |
|---|---|---|
| Fetus build plate for the P2S | No-heat adhesion plate named for the P2S; US$ 18.90 pre-order (Feb 2026) | radar |
| E3D Obsidian and Diamondback | Hardened nozzle (Obsidian, for H2, X1, P1) and a Diamondback hotend announced for the H2 and **P2** series, about £ 100 | radar; matters only for abrasive (carbon or glass fiber) filaments |
| BTT Panda Station | Rolling cabinet for Bambu printers with a waste drawer (Panda Den); US$ 299 plus US$ 159 | radar; P2S fit not confirmed |
| Dryers: Sunlu S4 Pro, Sovol SH03 (US$ 119) | Filament dryers up to 85 °C | radar; plain PLA rarely needs drying |

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
| PaintPort (Perspective3D, `perspektive3d.github.io/paintport`) | Re-maps a painted 3MF (MakerWorld, Bambu Studio, OrcaSlicer) to the spools you actually have loaded: tell it which color sits in each slot and it assigns the rest; missing colors can become ColorMix blends. Outputs for Bambu Studio, OrcaSlicer or PrusaSlicer. Runs in the browser, the file never leaves your computer; free, source on GitHub | radar. For a downloaded painted model whose colors do not match your AMS order, without unloading and reloading filament. Pick the printer first: switching it in the dropdown afterwards loses the mapping |
| Split3MF (`split3mf.com`) | Splits a painted 3MF into one part per color, keeps the filament colors, caps the cut and can add connector pins. Runs in the browser; the site says the file never leaves your computer. Open beta, source on GitHub | on demand, not tested. On a single-nozzle printer: print each color as its own part with no purge, then assemble. Check the result before printing; files over 10 MB may stall |

## Slicers and OrcaSlicer forks

Decision of 2026-09-23: **none of these replaces OrcaSlicer in the flow.**

| Slicer | What it is | Status and why |
|---|---|---|
| Full Spectrum | OrcaSlicer fork that blends colors by dithering; 4 filaments can look like 12 or more | radar, for the day multicolor becomes a real need. Many color changes means heavy purging on a single nozzle; test on a small part first |
| JusPrin (Obico) | OrcaSlicer fork with an AI that edits settings | dropped. Its suggestions ran heavy on infill and supports. In this workflow the assistant already does this with `analyze_part.py` and [docs/12](12-slicing-by-part.md), explaining the reason for each change |
| Prusa EasyPrint | Browser and mobile slicer | dropped for now. Slicing on a phone was not a need, and AMS printing needs a real project `.3mf` (see [docs/06](06-slicing-with-an-assistant.md)). Some brands block printing from it; not checked for Bambu |
| OrcaSlicer Image Map | OrcaSlicer fork that projects images and 2D or 3D gradients onto a part, even onto the prime tower; a multicolor method with one tool change per layer | radar. A separate fork, and the flow does not swap OrcaSlicer for forks; wait for it to reach mainline. One change per layer purges far less than dithering, so it is the most promising option for multicolor on a single nozzle |
| PrusaSlicer 3.0 | Community preview: rebuilt interface, favorites for common settings, a third-party plugin marketplace, several printer types and nozzle sizes in one project | radar. Still an unstable alpha with few third-party printers. Revisit at the stable release, mainly for the plugin marketplace |
| PreFlight | PrusaSlicer fork with advanced features | dropped. Profile migration and interface were reported as worse |

## Support

| Tool | Status |
|---|---|
| Support Fins (`printfins.com`) | in the flow as an option, not yet tested |
