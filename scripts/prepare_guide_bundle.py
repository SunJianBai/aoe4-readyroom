"""Build the EXE's offline guide snapshot from author-provided JSON files.

This developer command never contacts AOE4 Guides. Obtain a permitted export
before using it; the public list API is not a bulk-export interface.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aoevillager.guide_data import CIVILIZATIONS, GuideSyncError, _validate_build  # noqa: E402


DISPLAY_FIELDS = (
    "id", "title", "description", "author", "civ", "season", "map", "strategy",
    "views", "score", "scoreAllTime", "timeCreated", "ageTimings", "steps",
    "curated_playstyles",
)
DEFAULT_OUTPUT = ROOT / "assets" / "guides" / "guides.json"


def read_builds(filename: Path) -> list[dict]:
    payload = json.loads(filename.read_text(encoding="utf-8"))
    builds = payload.get("builds") if isinstance(payload, dict) else payload
    if not isinstance(builds, list):
        raise ValueError(f"{filename}: expected a build array or an object with builds")
    validated = []
    for item in builds:
        build = _validate_build(item)
        if build.get("civ") not in CIVILIZATIONS:
            raise ValueError(f"{filename}: unsupported civilization in {build['id']}")
        validated.append({field: build[field] for field in DISPLAY_FIELDS if field in build})
    return validated


def write_bundle(by_id: dict[str, dict], output: Path) -> int:
    if not by_id:
        raise ValueError("No build orders supplied; refusing to create an empty bundle")
    builds = sorted(by_id.values(), key=lambda item: (item["civ"], item["id"]))
    result = {
        "version": 1,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "builds": builds,
        "manual_ids": [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".guides-", suffix=".json", dir=output.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    counts = Counter(item["civ"] for item in builds)
    print(f"Wrote {len(builds)} unique guides to {output}")
    print("Per civilization: " + ", ".join(f"{code}={counts[code]}" for code in CIVILIZATIONS))
    return len(builds)


def prepare(inputs: list[Path], output: Path, merge: bool) -> int:
    by_id: dict[str, dict] = {}
    if merge and output.is_file():
        for build in read_builds(output):
            by_id[build["id"]] = build
    for filename in inputs:
        for build in read_builds(filename):
            by_id[build["id"]] = build
    return write_bundle(by_id, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="+", type=Path, help="permitted JSON exports to include")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--merge", action="store_true", help="preserve existing bundled IDs")
    args = parser.parse_args()
    try:
        prepare(args.input, args.output, args.merge)
    except (OSError, ValueError, json.JSONDecodeError, GuideSyncError) as exc:
        parser.exit(1, f"Guide bundle not changed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
