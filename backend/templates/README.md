# Symbol reference library

One folder per catalog `item_id`; every image inside is a reference crop for that SKU.
`list_templates()` reads the folder names, so **the folder name is the label a detection
gets** — misfile a crop and it prices as the wrong thing, or vanishes into
`unmatched_detections` if the name is not a real SKU.

This directory is deliberately **tracked in git**. The crops are project data, not scratch:
without them every electrical and plumbing scan returns 422, so a fresh clone should come
with a working detector.

## What is here, and how confident it is

| Folder | Crop | Source | What it is on the plan |
| --- | --- | --- | --- |
| `CLR01/` | `ceiling_cross.png` | cut from `tests/fixtures/plans/05.png` | cross-circle, mid-room — ceiling lighting outlet |
| `OT01/` | `mapua_duplex_r0/90/180/270.png` | Mapúa University slide deck, "Example of Convenience Outlets", duplex receptacle | circle with two lines through it, on a wall — convenience outlet |

**The outlet crops do not come from a sample plan, and they beat the ones that did.** The
first `OT01` crops were cut from `05.png` itself, on the reasoning that a reference has to
look like the drawing it is matched against. They found 13 outlets there — 2 of them a door
jamb and a wall line — and **none of the 14 on `10.png`**, a different draughtsman's sheet.
The textbook duplex symbol, shrunk to the ~18 px these plans draw at, finds 16 of 18 on
`05.png` with nothing false, 9 of 14 on `10.png`, and no longer mislabels lights as outlets
on `08.png`. Swapped on 25 Sep 2026; `tests/test_ground_truth.py` holds the counts.

What the same deck offered and **failed**, each measured on all 11 sample electrical plans
before being turned away — do not re-add them without a new hand count:

| Symbol | Why it was rejected |
| --- | --- |
| single receptacle (one line) | 279 hits on `05.png` — a circle and a line is everywhere |
| triplex receptacle | 80–160 hits on sheets that carry almost nothing |
| special-purpose (filled, ACU) | 15–18 hits on sheets that are otherwise refused, which would price them |
| ceiling outlet, plain circle | pushes `05.png` past its hand count of 21 |
| ceiling outlet, with ticks | `08.png` 17 -> 29 against a true 19 |
| ceiling outlet, with X | 9 hits on `10.png`, a power layout with no lights at all |

**The variant is assumed, not read.** These are filed under the `01` variant as a deliberate
default, so every match prices as a 1-gang outlet. Every detection-path estimate carries a
line saying so — see `_source_assumptions()` in `app/takeoff/estimator.py`. The Mapúa legend
draws single, duplex and triplex receptacles with one, two and three lines, and every outlet
on `05.png` and `10.png` is its duplex symbol. That does **not** make them `OT02`: duplex
counts sockets, gang counts plate slots, and a duplex receptacle normally sits in a 1-gang
box. **Settled by the owner, 25 Sep 2026: the duplex symbol stays `OT01`.** Do not relabel
the crops by line count.

**Four crops for one symbol is not a mistake.** The convenience outlet is drawn rotated to
match the wall it sits on, and `cv2.matchTemplate` is not rotation-invariant, so each
orientation needs its own reference.

## What cannot go here

- **Plumbing fixture symbols.** Tried 25 Sep 2026 with the LAV (both styles), WC, UR and KS
  symbols from a sanitary legend (E.H. Sison Engineers, sheet P-01), each in 4 rotations,
  mirrored, at two sizes, on all five plumbing samples. At 0.66 they return 88-291 "water
  closets" per sheet against 1-13 real ones. Lowering the bar is no help either: on
  `Plumbingplan/04.png` the six strongest WC matches are dimension tick marks and the six
  strongest KS matches are columns, with no real toilet among them. A fixture is a large,
  curved outline, and a plan is full of curves and squares - unlike the outlet circle, it
  has no feature that is rare on a drawing. The plumbing path reads labels instead
  (`app/extract/tags.py`), and nothing routes a plumbing plan through this library.
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
