# Electrical Gemini-first live workflow test

26 October 2026, Asia/Singapore. User instruction: “test it”. One browser scan
used the configured two-model maximum on the existing internal electrical sample
`tests/fixtures/plans/Data Set/Electricalplan/IMAGE/11.png` (683 x 658). No same-model
retry, billing change, additional model discovery or extra scan followed.

## Result

| Stage | Observed result |
| --- | --- |
| Gemini 2.5 Flash | Timed out after 20.013 s; no returned model identity or usable detections |
| Gemini 2.5 Flash-Lite | HTTP 404 after 0.607 s; unavailable for this request, not proof of global retirement |
| Automatic local fallback | Review opened automatically with nine light-point proposals; no detector choice and no added model/local aggregates |
| Local location review | Nine hits visually matched the previously checked nine ceiling outlets on sheet 11 |
| Missed switches | Six visible S/S2 marks were not automatically detected; manually marked as switch assemblies and explicitly excluded, because product/function and box compatibility were not established |
| Device pricing | Explicit test choice CLR01: nine sets at P22 = **P198**; no wire, conduit, breaker, panel or inferred switch/AC allowance |
| Boxes | Nine explicitly omitted with reasons; no assumed compatible box |
| Save | New, clearly named `ACCEPTANCE GEMINI ELECTRICAL LIVE 2026-10-26` project saved successfully |
| Full-page reload | P198, partial scope, exclusions and original image retained |
| Reopen from Projects | Same P198 result; all fifteen review markers retained (nine included lights, six excluded switches) |
| CSV export | Verified partial-scope heading, circuit exclusion, six device exclusions, nine box exclusions and CLR01 quantity/price/total |

The saved amount is a deliberately limited lights-only test estimate. It is not
the building's electrical cost or a complete takeoff. CLR01 is an explicit test
product choice, not a receptacle size read from the image. Manually marked
switches are not Gemini or local detections and do not establish recognition
accuracy. Their positions were marked from the visible original; this is a
same-preparer review, not an independent benchmark.

The backend audit record preserved both unsuccessful provider attempts and the
local source. Rebuilding the reviewed partial plan with the committed catalog
reproduced P198 and only CLR01. The browser, operating as the signed-in owner,
verified saved output, exclusions and all fifteen markers. A separate direct
service-role table-read check was refused by existing database permissions;
no grants or policies were changed. No claim is made here that the verifier
directly read every immutable saved snapshot through that service role.

Evidence: `datasets/electrical-gemini-validation-2026-10-26/live-ui-test.json`.
Screenshots: `../tmp/electrical-gemini-live-test-2026-10-26/review.png` and
`results.png`. Export retained as `estimate.csv` in the same temporary folder.

## Assessment

Automatic fallback, explicit review, partial pricing, persistence, original-image
binding in the UI, reopening and export passed this live workflow test. Gemini
electrical detection did not produce usable proposals. Improved symbol coverage
and reduced manual corrections therefore remain **unverified**. Next work is to
resolve provider/model availability and request latency, then obtain and visually
score actual Gemini proposals before claiming R25 recognition acceptance.
