# Print queue

The order of the rows **is** the priority: the first row is the next part to slice and print. Move
a row instead of keeping a number column.

## File naming, applied at download time

Downloaded STL and 3MF files usually arrive with unreadable names (hashes, giant titles, other
languages). Rename **before** moving the file anywhere, and keep the original name only as a note.

```
owner-part-material-color.3mf        all lowercase, hyphens instead of spaces
me-desk-hook-pla-black.3mf           your own part
acme-shelf-pla-white.3mf             a client's part
```

## Status

`Downloaded` -> `Sliced` -> `Printing` -> `Printed` -> `Delivered`

A row only goes backwards (to `Sliced` or `Downloaded`) if the print fails. When you mark
`Printed`, also add the part to `filament-log.md`.

| Owner | Part | File | Status | Material | Notes |
|---|---|---|---|---|---|
| `<me>` | `<part>` | `<file>` | Downloaded | `<PLA black>` | `<original name, source>` |

## Before slicing any downloaded file

- [ ] Open the object list (or top view) and look for **duplicated overlapping objects**. This is a
      known bug in Bambu Studio and its forks: a project can carry a duplicate object placed almost
      exactly on top of the original, and files downloaded from model sites sometimes arrive already
      broken.
- [ ] Unzip a `.3mf` (`unzip -l file.3mf`): only `3D/3dmodel.model` means pure mesh (configure
      everything by hand); a `Metadata/` folder means a full slicer project with a profile
      (check the printer and filament match yours).
