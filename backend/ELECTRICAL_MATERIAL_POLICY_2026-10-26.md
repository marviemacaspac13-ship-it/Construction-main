# Electrical product and material policy — 26 October 2026

Subsequent user decision: implement a separate, explicitly partial devices-and-boxes
estimate. [Implemented scope and acceptance](ELECTRICAL_PARTIAL_WORKFLOW_2026-10-26.md)
supersede the requirement for circuit inputs **only for that partial mode**.
SW01–03 require explicit one-way/gang/product confirmation; ACO01 is an explicitly
selected generic device only. Each priced box requires explicit compatibility
confirmation. No switch-leg, wire-size, conduit, breaker or panel inference was
enabled. GS, three-way and four-way mappings remain unresolved. The earlier
full-circuit policy below remains a future specification, not implemented support.

This is the implementation specification produced by the approved mapping/rule
decision checkpoint. It does not activate additional priced classes, alter the
catalog, change existing estimates or claim client/electrical-design approval.
The [review contract](ELECTRICAL_REVIEW_CONTRACT.md) still blocks switches and AC
outlets until the new calculation inputs and rules are implemented and verified.

## What the references establish

[Schneider Electric Philippines](https://www.se.com/ph/en/faqs/FAQ000266657/)
identifies gang count, operating voltage, ampere rating, mounting and switch
function as distinct selection specifications. Its [gang explanation](https://www.se.com/ae/en/faqs/FA381487/)
also distinguishes the number of switches on a plate from multi-location switching.
These sources establish terminology, not a mapping to TRACE's private item IDs.

[Meiji's two-gang three-way product](https://meijielectric.ph/product/mcs-0222/)
provides a concrete manufacturer example that gang count and switching function
are independent. Its brand, price and ratings are not imported into TRACE's catalog.

[Xiaomi's Philippine model-specific guidance](https://www.mi.com/ph/support/faq/details/KA-536271/)
discusses a dedicated circuit when a particular AC model shares an overloaded
circuit. It does not establish a generic wire length, gauge or breaker for every
AC symbol. No current PEC edition or compliance certification is inferred from
these sources or the supplied symbol appendix.

## Product decisions for implementation

1. **Use SW01–03 as costing candidates for explicitly specified one-way sets.**
   Their captured catalog names state one-way function and one/two/three gangs,
   and their purchase unit is per set. Require confirmed function, gang count and
   explicit product selection. Do not map bare S/S2/S3 labels automatically across
   drawing conventions. These are generic estimating categories, not a certified
   choice of manufacturer, voltage rating, current rating or installation method.
2. **Keep GS01–03 distinct and withheld from automatic mapping.** Their generic
   names do not establish what makes them different from SW. An external maker's
   product cannot resolve these project-specific IDs. Do not count GS and SW for
   the same assembly or pick the cheaper row as a semantic substitute.
3. **Keep three-way/four-way products unresolved.** The captured catalog contains
   no explicitly corresponding product. A reviewed S3w observation must not become
   SW03. Do not invent a new catalog row, price or product specification.
4. **Treat ACO01 as an explicit AC-outlet costing candidate, not an AC circuit.**
   Its generic name does not establish the connected load, installation connection,
   cable size, conductor count, protection, rating or actual route. No ordinary
   outlet allowance or automatic fixed aircon wire size can complete that circuit.
5. **Preserve existing OT/CLR choices and defaults.** The duplex-to-OT01 choice
   remains the owner's documented default; it is not a read gang count. Existing
   explicit OT02/03 and CLR02/03 choices remain separate from raw symbol semantics.

These decisions define a support boundary rather than silently resolving missing
evidence. GS, multi-way and unspecified AC records remain usable review evidence,
but cannot produce a supposedly complete priced result by disappearing or taking
another device's price. Explicit exclusions continue to require retained reasons.

## Separate the three quantities

### Device purchase sets

Count each included physical assembly once. For example, a confirmed two-gang
one-way assembly selected as SW02 produces **one SW02 set**, not two SW01 sets
and not two SW02 sets. Its two switching mechanisms are a separate attribute.
Two physically separate SW01 assemblies produce two purchased sets.

### Mounting locations and boxes

Each physical mounting location contributes once to the box requirement, regardless
of how many mechanisms share its assembly. A box drawn independently must be linked
to that location rather than added again to an assumed box there. Ceiling junction
locations remain separate from switch/outlet mounting locations.

Do not claim that generic UTB01 necessarily fits every multi-gang set: its catalog
entry lacks dimensions/type information. New reviewed switch support must retain
an explicit compatible-box selection/basis, or an unresolved box requirement.
The latter blocks a complete estimate unless explicitly excluded from its scope.
Neither a product listing nor the term 'gang' establishes the full box arrangement.

### Circuit materials

For the first new switch/AC implementation, use **complete explicit circuit inputs**
instead of inventing new count allowances. The reviewer supplies the applicable
route segments, conductors by selected catalog wire, terminal/slack quantities,
conduit selection, assembly coverage and relevant device/protection specifications.
Lengths and conductor counts must be explicit, not defaulted from the new device
class. A drawn switch-control arc is not a measured cable route.

For an explicitly specified route segment, retain the existing arithmetic:

- Wire metres per specified conductor group = `(route metres + supplied free-wire
  allowance for its terminations) × conductor count × (1 + wire waste)`.
- Conduit metres = `route metres × (1 + conduit waste)`, counted once per unique
  physical conduit segment, not once per conductor group or per endpoint device.
- Merge identical purchase SKUs only after physical route and assembly accounting.
  Keep different conductor groups/specifications auditable before merging.

The formula is quantity arithmetic, not electrical sizing. A service name such as
`aircon` must not select a wire gauge automatically in the new reviewed mode.
Protection/disconnect selections and requirements must be supplied/verified;
their mere catalog availability does not authorize inference from an AC count.

All included assemblies must be covered by the explicit circuit basis, or have
an explicitly acknowledged exclusion. Missing routes, wiring methods, counts,
box compatibility or protection scope remain unresolved. Do not convert unknowns
to zero or publish an unexplained device-only total as a complete electrical estimate.

## Avoid overlap with the existing estimating path

Existing count-derived outlet/lighting allowances are preserved for legacy scans
in this checkpoint. They do not authorize new switch-leg allowances. In particular,
the current lighting parameter describes a ceiling run; its implementation does
not independently establish the actual switch-to-light cable network.

In the new explicit mode, turn off **all** count-derived wire/conduit for its scope
and account for the complete route network once, including any switch legs.
Do not combine a partial measured network with complete per-device allowances.
No hybrid partial-coverage policy is approved by this specification. Missing
coverage must block completion rather than silently suppressing some circuits.

The current `Run` structure has implicit conductor defaults, service-selected
wire gauges and no per-assembly coverage or shared-segment identity. Therefore
passing a nonempty `plan.runs` is not sufficient evidence of this new complete
explicit basis. A dedicated validated circuit record and grouping rules are
needed before relaxing the review contract's switch/AC guard. Do not quietly
change the existing Run semantics or replay older snapshots with new defaults.

## Worked implementation fixtures

The [machine-readable policy](datasets/electrical-review-audit-2026-10-26/material-policy.json)
records the catalog hash, mapping candidates, withheld classes and these checks:

| Input | Expected quantity | Pricing/quantity scope |
| --- | --- | --- |
| One confirmed two-gang one-way assembly | One SW02 set, two mechanisms, one mounting location | Device-only example: PHP 169 at captured price; not a complete estimate |
| Two separate one-gang one-way assemblies | Two SW01 sets, two mechanisms, two mounting locations | Device-only example: PHP 264 at captured prices; not equivalent to the first arrangement |
| S3w without an exact product | One unresolved observed device | Not SW03 and not a zero device |
| Supplied 10 m route, three conductors, two 0.30 m terminal allowances, 10% waste | 34.98 m conductor, 11.00 m conduit | Synthetic arithmetic only; not a proposed circuit design |

Catalog names/units, example prices and arithmetic were checked locally. No
manufacturer web prices were substituted for captured project prices. No new
application code, estimating constants, model requests, database writes or UI
changes were made in this decision checkpoint. The earlier 690-test backend run
is historical verification of the existing contract, not proof these future
circuit rules have been implemented.

## Next checkpoint

Implement the dedicated explicit circuit/box records, assembly coverage and
separate purchase/box/conductor calculations with exact tests. Only then allow
eligible one-way switch/AC records through that complete route-based workflow.
GS and missing multi-way products remain withheld until their product definitions
are actually available. R25 is not complete until proposer/review integration
and drawing-level recognition plus save/reopen acceptance also pass.
