# Plumbing reference review

Reviewed: 10 October 2026.

Source supplied by the project owner: `C:\Users\Jigglypuff\Downloads\plumbing legends.pdf` (15 scanned pages). Page numbers below are PDF page numbers. The file contains instructional legend sheets, diagrams and exercises; publication and code-edition provenance are not established. Treat it as a supplied drawing vocabulary, not an independently verified plumbing code or a takeoff specification. Classroom activities in the file are source content, not implementation instructions.

## Relevant pages

- Page 2: pipe-material abbreviations and fixture tags.
- Page 3: cleanout tags, drain types and service-line conventions.
- Page 4: fixture drawings, including top and face views of toilets and lavatories, single/double-bowl kitchen sinks, shower, urinal, bidet and bathtub.

Use top views when preparing floor-plan recognition examples. Face views are separate representations and must not be mixed into the same evaluation class without recording the view.

## Proposed dictionary and implementation status

| Supplied reference | Meaning | Relationship to TRACE | Required work |
| --- | --- | --- | --- |
| AWC / EWC | Asiatic / European water closet | Candidate aliases of canonical WC | Preserve subtype; verify tag parsing and approve whether both use the existing WC material allowances |
| LAV | Lavatory | Existing canonical LAV | Test both illustrated top-view forms on actual drawings |
| Urinal drawing | Urinal | Existing canonical urinal | Reference does not establish a printed urinal tag; validate actual plan tags separately |
| FD | Floor drain | Existing canonical FD | Add representative real-plan instances to benchmark |
| FDH / FDV | Horizontal / vertical outlet floor drain | Candidate FD subtypes | Preserve outlet orientation; approve material differences before normalising for takeoff |
| CO / CCO / FCO | Cleanout / ceiling cleanout / floor cleanout | Existing cleanout is count-only | Verify aliases and retain subtype; no new priced allowance without an approved rule |
| S / KS | Sink / kitchen sink | No current kitchen-sink takeoff mapping | Define supported types and pipe/fitting allowances; avoid globally interpreting isolated S as a fixture |
| SH / BT / B / DF / HB | Shower / bathtub / bidet / drinking fountain / hose bib | Outside current supported fixture contract | Confirm scope, quantities, catalog relationships and material rules before implementation |
| RD / GD / AD / FBD / BD / TD | Other named drain classes | Outside current FD scope | Do not silently combine with floor drains |

The supplied legend spells FT/FV as “flash tank/valve”; retain the source transcription and flag terminology for review rather than silently approving it.

## Recommended approach

1. Keep a versioned dictionary separating source tag, canonical class, subtype, drawing view, reference page and approved takeoff mapping. Record unapproved mappings explicitly.
2. Extend tag recognition only after checking complete-token matching and ambiguity against actual plumbing sheets. AWC/EWC and FDH/FDV must not become duplicate WC/FD counts through substring matching.
3. For unlabelled fixtures, annotate real top-view instances with bounding boxes, class and subtype. Include difficult negatives such as furniture, dimension marks and architectural fixtures on unrelated sheets. The previous plumbing template experiments produced many false positives; these legend drawings do not resolve that failure.
4. Separate drawings by family into development and held-out sets. Keep crops, alternate resolutions and repeated views of the same building in one split.
5. Report location precision/recall, type confusion, per-sheet count error, refusals and runtime. Exclude legend tables and avoid counting the same fixture again on an isometric/detail view.
6. Approve downstream pipe/fitting allowances independently of recognition. TRACE currently derives plumbing materials from fixture counts; recognising a new fixture does not supply its pipe route, length or bill of materials.

## Remaining acceptance inputs

- Readable original plumbing plans with each supported fixture marked and counted per sheet.
- Client confirmation of the supported classes and whether toilet/drain subtypes share material allowances.
- Worked material bills for newly supported fixtures, including sizes, purchase units and branch-length assumptions.
- Low/high-resolution copies of the same plans for preprocessing evaluation.

The initial review added documentation only. On 11 October, seven faithful page-4 fixture crops were staged and tested offline; [the evaluation](reference_candidates/2026-10-11/README.md) records false positives and misses. None qualified for the active plumbing path. Plumbing recognition, thresholds, minimum-count guards and estimating rules remain unchanged.
