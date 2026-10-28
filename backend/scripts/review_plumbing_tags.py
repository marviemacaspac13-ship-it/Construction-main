"""Offline stage-1 evidence capture; never changes production counts or settings.

Run from the repository root with backend/.venv/Scripts/python.exe.
The input is the existing plumbing-expanded dataset manifest. Images with equal
decoded pixels share one OCR run; drawing-family membership is retained separately.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter
from unittest.mock import patch

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import main
from app.extract.tags import count_tags, read_tiled, tally
from app.takeoff.constants import FIXTURE_TAG_PATTERNS


def pixel_hash(image):
    """Group identical decoded content even if file encodings differ."""
    digest = hashlib.sha256(str(image.shape).encode())
    digest.update(image.tobytes())
    return digest.hexdigest()


def capture(raw, image):
    start = perf_counter()
    boxes = read_tiled(image)
    counts = count_tags(boxes, FIXTURE_TAG_PATTERNS, image.shape)
    before = dict(tally(counts))
    observations = [
        dict(id=f"tag-{i + 1:03}", tag=tag, **asdict(box), review="unreviewed")
        for i, (tag, box) in enumerate(
            (tag, box) for tag, found in counts.items() for box in found.boxes
        )
    ]
    # Exercise the actual route, including refusals, against the SAME OCR read.
    # This is a count-preservation check, not two independent accuracy runs.
    with patch.object(main, "read_tiled", return_value=boxes):
        try:
            plan, _ = main._read_plumbing(raw, "Plumbing Plan")
            status, detail = "accepted", None
            after = plan.fixture_tags
            evidence = Counter(o.tag for o in plan.fixture_tag_observations)
            assert dict(evidence) == before, "Production observations diverge from counts"
        except main.HTTPException as exc:
            if exc.status_code != 422:
                raise
            status, detail = "refused", exc.detail
            # Refused reads have no saved PlanSchema; preserve research evidence only.
            after = dict(Counter(o["tag"] for o in observations))
    assert before == after, "Evidence capture changed a count"
    return dict(before_counts=before, after_counts=after, status=status, detail=detail,
                observations=observations, ocr_boxes=[asdict(b) for b in boxes],
                runtime_seconds=round(perf_counter() - start, 3))


def overlay(image, observations, output):
    canvas = image.copy()
    for item in observations:
        point = (round(item["cx"]), round(item["cy"]))
        cv2.circle(canvas, point, 9, (0, 100, 255), 2)
        cv2.putText(canvas, item["id"].replace("tag-", ""),
                    (point[0] + 10, point[1] - 6), cv2.FONT_HERSHEY_SIMPLEX,
                    0.42, (0, 60, 210), 1, cv2.LINE_AA)
    if not cv2.imwrite(str(output), canvas):
        raise OSError(f"Cannot write {output}")


def run(dataset, output, names):
    data = json.loads(dataset.read_text(encoding="utf-8"))
    items = [i for i in data["images"] if not names or i["file"] in names]
    missing = set(names) - {i["file"] for i in items}
    if missing or not items:
        raise ValueError(f"No matching views or unknown names: {sorted(missing)}")
    # Refuse overwrites: preserve both frozen reads and any subsequent review.
    output.mkdir(parents=True, exist_ok=False)
    (output / "overlays").mkdir()
    results, cache = [], {}
    for item in items:
        source = ROOT / "datasets" / item["source"]
        raw = source.read_bytes()
        file_hash = hashlib.sha256(raw).hexdigest()
        if file_hash != item["sha256"]:
            raise ValueError(f"Source changed: {source}")
        image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"Cannot decode {source}")
        digest = pixel_hash(image)
        duplicate = digest in cache
        if not duplicate:
            cache[digest] = capture(raw, image)
            overlay(image, cache[digest]["observations"], output / "overlays" / f"{digest}.png")
        result = dict(file=item["file"], source=item["source"], family=item["family"],
                      sha256=file_hash, pixel_sha256=digest, duplicate_content=duplicate,
                      width=image.shape[1], height=image.shape[0],
                      fixture_reference_counts={
                          "water_closet": sum(o["class_id"] == 0 for o in item["objects"]),
                          "lavatory": sum(o["class_id"] == 1 for o in item["objects"])},
                      fixture_reference_status=item.get("review", data.get("annotation_status")),
                      **cache[digest])
        results.append(result)
        (output / "evidence.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        print(f"{item['file']}: {result['status']} {result['before_counts']}", flush=True)
    protocol = dict(stage=1, production_changed=False,
                    comparison="Count-only baseline versus location evidence from the same OCR read",
                    deduplication="Decoded-pixel SHA256; related nonidentical views stay in the same family",
                    unique_content=len(cache), families=sorted({r["family"] for r in results}),
                    dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
                    code_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                                 for p in ("app/main.py", "app/extract/tags.py", "app/extract/ocr.py",
                                           "app/takeoff/constants.py", "scripts/review_plumbing_tags.py")},
                    limitations="Previously exposed development drawings. Fixture boxes are not tag truth. "
                    "No tag precision/recall until complete tag annotations and observation review exist.")
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2) + "\n", encoding="utf-8")
    review = [dict(pixel_sha256=digest, coverage="pending", reviewer=None,
                   observations=[dict(id=o["id"], outcome="unreviewed", note="")
                                 for o in result["observations"]],
                   missed_tags=[], notes="Mark actual printed tags, separately from untagged fixtures.")
              for digest, result in cache.items()]
    (output / "review.json").write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    lines = ["# Stage 1: plumbing tag evidence", "",
             "Before and after use the same OCR read. Counts and production behavior are unchanged.",
             "Fixture reference totals describe drawn objects, not necessarily printed tags; differences are not tag recall.", "",
             "| View | WC before / after | LAV before / after | Drawn WC / LAV reference | Route |",
             "| --- | --- | --- | --- | --- |"]
    for r in results:
        b, a, t = r["before_counts"], r["after_counts"], r["fixture_reference_counts"]
        lines.append(f"| {r['file']} | {b.get('water_closet', 0)} / {a.get('water_closet', 0)} | "
                     f"{b.get('lavatory', 0)} / {a.get('lavatory', 0)} | "
                     f"{t['water_closet']} / {t['lavatory']} | {r['status']} |")
    lines += ["", f"{len(results)} views, {len(cache)} distinct pixel hashes, "
              f"{len(protocol['families'])} recorded drawing families.", "",
              "Orange numbered circles locate OCR observations, not fixture bounding boxes. "
              "Review status and missed-tag coordinates belong in review.json. "
              "This export alone does not complete the visual coverage audit."]
    (output / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "datasets/plumbing-expanded/dataset.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--files", nargs="*", default=[])
    args = parser.parse_args()
    run(args.dataset, args.output, args.files)
