# Plumbing fixture detection: Gemini trial and current direction

> Implementation update, 22 October: the user authorized reviewed Gemini plumbing
> proposals with ordered model fallbacks and the original reader last. The local
> implementation and setup are described in [the setup guide](PLUMBING_VISION_SETUP.md).
> The trial provenance below remains historical evidence. A subsequent
> [live cafeteria acceptance](PLUMBING_VISION_LIVE_ACCEPTANCE_2026-10-22.md)
> verified Gemini 3.8 Flash, reviewed counts and real save/reopen on one drawing.

Recorded 17 October 2026. This supersedes the immediate detector recommendation
in the 16 October assisted-template handoff, while preserving its findings.

## Current decision

Gemini is the strongest candidate demonstrated in this conversation for the
user's immediate constraints: no custom training, no new annotation dataset,
and no local GPU inference requirement. Continue toward a limited API prototype
with visual review before estimating, subject to further verification. This is
not a claim that Gemini is universally the best detector or production-ready.

The user asked to record this decision. No Gemini API integration, deployment,
new model installation, or training was performed by this documentation update.
Production plumbing recognition remains the existing OCR/tag pipeline.

## Evidence and provenance

The user supplied two complete JSON responses after being given an image-reading
prompt for WC and LAV fixture bodies. The assistant mapped the returned boxes
onto the corresponding local images and visually inspected the overlays.

| Drawing | Image size | Returned WC | Returned LAV | Visual review |
| --- | --- | ---: | ---: | --- |
| Cafeteria water layout, `Plumbingplan/IMAGE/01.png` | 1356 x 650 | 2 | 2 | All four locations match visible bodies; kitchen sinks and legend excluded |
| Public restroom, `Plumbingplan/IMAGE/02.png` | 397 x 828 | 11 | 12 | All 23 locations match visible bodies; urinals and floor drains excluded |
| Total | Two previously examined sheets | 13 | 14 | 27 returned locations; no apparent WC/LAV misses or false detections |

These are qualitative location/completeness checks by the same assistant, not
independent ground truth or a scored IoU benchmark. Some toilet boxes omit the
rectangular tank. Correct fixture location does not establish precise full-body
segmentation. Do not report 100% general accuracy from these observations.

The recommended model in chat was `gemini-3.8-flash`, based on Google's documentation
available during the session. The pasted responses contain no model metadata:
the model actually used, settings, exact submitted prompt, and number of attempts
were not independently verified. Treat these as user-supplied Gemini trial outputs,
not reproducible API benchmark runs. `uncertainty: null` and `limitations: []`
are model output, not evidence that the result has no uncertainty or limitations.

Both images were already exposed in prior detection work. They are development
examples, not untouched held-out acceptance data. Other plumbing classes, pipe
routes, lengths, diameters, fittings, and estimating accuracy were not tested.

## Preserved artifacts

The [trial evidence directory](datasets/gemini-fixture-trial-2026-10-17/) contains:

- `user_supplied_responses.json`: both complete pasted responses, including
  normalized boxes in `[ymin, xmin, ymax, xmax]` order on a 0-1000 scale.
- `cafeteria-review.png` and `restroom-review.png`: source-image overlays, with
  WC in red and LAV in blue. The restroom overlay is displayed at twice native size.

Original images remain at
`tests/fixtures/plans/Data Set/Plumbingplan/IMAGE/01.png` and `02.png`.
No commit, push, external backup, or independent validation is claimed.

## SAM 3 comparison: bounded negative result

Meta's signed-in SAM 3 playground was tested on the cafeteria sheet. Text searches
`toilet`, `toilet symbols in a plumbing drawing`, and `washbasin` produced no
usable visible fixture masks. An enlarged bathroom crop from the same image also
produced no usable fixture masks for `toilet` and `washbasin`.

A session-reset error interrupted the full-sheet washbasin attempt; after one
reload, the search reached review without usable masks. This limits the strength
of the comparison. Visual-exemplar discovery was not tested, and the second
plumbing sheet was not tested in SAM 3 because its upload required separate approval.
This does not establish that all SAM 3 approaches fail. No paid fal inference ran.

## Next verification before production use

1. Record the actual model ID, prompt, settings, image hash and dimensions, raw
   response, and request outcome for each API run.
2. Check repeatability on these two sheets and performance on additional drawing
   styles. Review locations and omissions, not totals alone.
3. Measure actual latency, token usage/cost and account-specific free-tier limits.
   Free-tier availability is not unlimited capacity or a production SLA.
4. Validate response structure, supported classes, finite ordered box coordinates,
   bounds and duplicate/conflicting observations. Derive counts from validated
   instances rather than trusting a separate model count field.
5. Let users review, reject, relabel and add instances before confirming counts.
   Replace corresponding WC/LAV source counts; never add visual counts to OCR
   totals. Preserve unrelated tags and existing deterministic estimating rules.
6. Keep credentials server-side, preserve authentication/ownership, and handle
   provider failures without replacing prior results with an apparent real zero.
   Reuse supported correction and save contracts after inspecting current code.

Training, broad model experiments and production threshold changes remain paused.
The prototype is a recommended next step, not work completed or authorized merely
by documenting it.

## Technical references checked during the conversation

- [Gemini image understanding and bounding boxes](https://ai.google.dev/gemini-api/docs/image-understanding)
- [Gemini pricing and free-tier availability](https://ai.google.dev/gemini-api/docs/pricing)
- [Meta SAM 3](https://github.com/facebookresearch/sam3)

Recheck model availability, pricing and provider data-use terms before integration.
