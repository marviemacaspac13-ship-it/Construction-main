# Symbol reference library

One folder per catalog `item_id`; every image inside is a reference crop for that SKU.
`list_templates()` reads the folder names, so **the folder name is the label a detection
gets** — misfile a crop and it prices as the wrong thing, or vanishes into
`unmatched_detections` if the name is not a real SKU.

This directory is deliberately **tracked in git**. The crops are project data, not scratch:
without them every electrical and plumbing scan returns 422, so a fresh clone should come
with a working detector.

## What is here, and how confident it is

Cut from `tests/fixtures/plans/05.png` itself — a reference has to look like the drawing it
will be matched against, and multi-scale matching forgives size but not style.

| Folder | Crop | What it is on the plan |
| --- | --- | --- |
| `CLR01/` | `ceiling_cross.png` | cross-circle, mid-room — ceiling lighting outlet |
| `OT01/` | `wall_outlet_h.png`, `wall_outlet_v.png` | circle with one line, on a wall — convenience outlet |

**The variant is assumed, not read.** The drawing puts the same circle on a 1-gang and a
3-gang outlet, and the same ring on every size of ceiling receptacle, so nothing on the page
says whether a match is `OT01`, `OT02` or `OT03`. These were filed under the `01` variant as
a deliberate default. Every detection-path estimate carries a line saying so — see
`_source_assumptions()` in `app/takeoff/estimator.py`.

**Two crops for one symbol is not a mistake.** The convenience outlet is drawn rotated to
match the wall it sits on, and `cv2.matchTemplate` is not rotation-invariant, so each
orientation needs its own reference. Four would probably be better than two.

## What cannot go here

- **Switches.** On `05.png` they are lettered `S`, `S2`, `S3`, `S3w` — text, not a glyph.
  There is nothing to crop, so they need tag counting rather than template matching.
- **`UTB01` and `JCB01`.** Both *do* have standard symbols — a plain square and a square
  with a diagonal cross — but `05.png` does not draw them, and the rules derive one utility
  box per wiring device and one junction box per ceiling outlet. A template would double-count
  **on a plan like this one**. If a drawing ever does show them, the derivation is the thing
  that has to give way, not the template.
- **Anything without a `UnitSpec`** in `app/takeoff/units.py`. `from_detections.py` filters
  those labels out, so the crop would be matched and then silently dropped.

## Adding one

Either drop a file into `<ITEM_ID>/`, or use the Symbol Library screen, which posts to
`/api/templates`. Crop tightly around the symbol with no surrounding wires or text.
