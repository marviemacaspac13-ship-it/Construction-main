"""Post-review diagnostic only: canonical-class dedupe at the existing OCR radius.

Reads a frozen evidence export, never production data. No threshold tuning.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.extract.ocr import DEDUPE_RADIUS


def deduplicate(observations):
    kept, removed = [], []
    for item in sorted(observations, key=lambda o: -o["score"]):
        duplicate = next((k for k in kept if k["tag"] == item["tag"]
                          and abs(k["cx"] - item["cx"]) <= DEDUPE_RADIUS
                          and abs(k["cy"] - item["cy"]) <= DEDUPE_RADIUS), None)
        if duplicate:
            removed.append(dict(id=item["id"], retained_id=duplicate["id"],
                                tag=item["tag"], dx=abs(item["cx"] - duplicate["cx"]),
                                dy=abs(item["cy"] - duplicate["cy"])))
        else:
            kept.append(item)
    return kept, removed


def run(directory):
    rows = json.loads((directory / "evidence.json").read_text())
    comparisons = []
    for row in rows:
        kept, removed = deduplicate(row["observations"])
        comparisons.append(dict(file=row["file"], pixel_sha256=row["pixel_sha256"],
                                before=row["before_counts"],
                                candidate=dict(Counter(o["tag"] for o in kept)),
                                removed=removed))
    result = dict(status="post-review offline hypothesis; not production or held-out acceptance",
                  radius_px=DEDUPE_RADIUS, policy="Existing OCR radius; group by canonical tag",
                  limitations="Nearby distinct tags can merge; requires broader location review before promotion.",
                  comparisons=comparisons)
    with (directory / "duplicate-probe.json").open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    run(parser.parse_args().directory)
