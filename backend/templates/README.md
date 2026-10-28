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
| `CLR01/` | `legend_pendant_fixture.png` | "Lighting Symbols" chart supplied by the owner, 27 Sep 2026 — *Pendant Fixture Light* | circle with four short ticks OUTSIDE it — how `08.png` draws every light |
| `CLR01/` | `legend_surface_ceiling.png` | same chart — *Surface Ceiling Light* | circle with four diagonal ticks — how `11.png` draws its lights |
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
| ceiling outlet, plain circle | exceeded the then-recorded 21-light count on `05.png`; that count was superseded by a 23-light visual recount on 13 Oct, so this variant needs a fresh location-level audit before reconsideration |
| ceiling outlet, with ticks | `08.png` 17 -> 29 against a true 19 |
| ceiling outlet, with X | 9 hits on `10.png`, a power layout with no lights at all |

### The lighting chart (27 Sep 2026)

The catalog prices no light fixture, only the **ceiling receptacle** behind each light
point, so every light symbol is filed under `CLR01` whatever the fixture. All 20 symbols
were cropped, turned into line art (black strokes kept, yellow fill dropped, since plans
draw them hollow), shrunk to 20 px, and matched **one at a time** on all 12 sample
electrical sheets with the ring check on. Every hit at a location nothing else found was
checked against the drawing.

**Adopted:**

| Symbol | Result |
| --- | --- |
| Pendant Fixture Light | `08.png` 7 → **19 of 19**, every hit checked; `05.png` +1, a plain circle on the dining lighting circuit |
| Surface Ceiling Light | 9 light symbols on `11.png`, each checked by eye; nothing on any other sheet. A 13 Oct whole-sheet visual count found 9/9 light points, but the plan remains refused under `MIN_DEVICES = 10` and this single-sheet review does not establish generalization. |

The "ceiling outlet, with ticks" rejected in the table above (`08.png` 17 → 29) was the
same idea before the ring check existed; its extra hits were line crossings, which the
check now removes.

**Rejected** — do not re-add without a new hand count:

| Symbol | Why |
| --- | --- |
| External Light | 500–950 hits per sheet |
| Fluorescent Strip, LED strip (dashed) | 100–760 hits per sheet: a pair of lines or a dash row is everywhere |
| Recessed Downlighter (plain circle) | grid bubble "C" on `10.png` and `11.png`, patterned floor on `06.jpg` |
| Recessed Ceiling Light | 9 hits on `11.png`, as Surface Ceiling has, plus 1 unchecked on `08.png` — which is already 19 of 19. Not checked hit by hit; one tick-circle crop is enough until a sheet shows it adds something |
| Light Point Pendant (diamond) | subset of what Pendant Fixture finds |
| Light Point Pendant (crossed circle) | only lights the existing crop already finds |
| Floor Light | one hit, a hatched box beside a motor symbol |
| Surface Wall, Recessed Wall | land on convenience outlets on `10.png` — a double count |
| Ceiling Light (X), Outdoor Light, Exit Light, Wall Light, LED Light (square), Luminaire, Light Point Batten, Step Light | **no hit on any sample sheet.** No sheet draws them, so they cannot be shown to work here; adding them untested is how false hits get in |

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

- **Door and window symbols.** Tried 25 Sep 2026 with a door leaf (one half of the
  EdrawMax "double door" - the sheet has no plain single swing) and its window symbol, in 8
  orientations at three sizes, on all four floor plans. At 0.66 the window returns 119-239
  hits per sheet against about 9-11 real windows; the door finds 5 real doors on `01.png` (of
  about 9, plus one kitchen counter) but 1 of 6 on `04.jpg` and nothing on `03.png`, and one
  step lower it returns hundreds. The door hits that were real were catching the hinge
  corner, not the swing. Even perfect counts would barely move a price: the assumed 1 door
  and 1 window per room already lands within 1% on `04.jpg`, the one plan with known counts,
  and gives 10 / 10 on `01.png` against about 9 / 11 drawn.
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

On 11 October 2026, the supplied electrical appendix contributed one tested CLR01
crop, `6a3a970d9f0c4b3c88b6e5e29c51ddaa.png`. It recovers the lower-left living-area
light on `05.png` (17 detected of 23 on the 13 Oct recount, previously 16 detected), preserves 19/19 on `08.png` and zero
false lights on `10.png`, and leaves the other electrical sheets unchanged except
the identical `02.png` copy. Wider size/orientation variants and the supplied
plumbing fixture crops were rejected after false-positive checks. Source crops,
API receipt and evaluation are in [the reference report](../reference_candidates/2026-10-11/README.md).

Either drop a file into `<ITEM_ID>/`, or use the Symbol Library screen, which posts to
`/api/templates`. Crop tightly around the symbol with no surrounding wires or text.
