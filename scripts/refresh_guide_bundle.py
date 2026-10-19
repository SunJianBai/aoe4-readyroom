"""Developer-only, one-time refresh of selected offline AOE4 Guides entries.

The manifest lists individual public guides chosen on the website. This does
not enumerate the site's corpus, and it is never executed by the desktop app.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aoevillager.guide_data import (  # noqa: E402
    API_ROOT, SOURCE_ROOT, GuideSyncError, GuideStore, _get_json, _validate_build,
    image_paths,
)
from scripts.prepare_guide_bundle import (  # noqa: E402
    DEFAULT_OUTPUT, DISPLAY_FIELDS, read_builds, write_bundle,
)

DEFAULT_MANIFEST = ROOT / "assets" / "guides" / "curated_ids.json"


def download_missing_icons(builds: list[dict], store: GuideStore) -> tuple[int, list[str]]:
    downloaded = 0
    failed: list[str] = []
    for path in sorted(image_paths(builds)):
        filename = store.cached_icon(path)
        if filename is None or filename.is_file():
            continue
        request = Request(SOURCE_ROOT + path, headers={"User-Agent": "AOE4Toolbox/1.0 (offline bundle)"})
        try:
            with urlopen(request, timeout=25) as response:
                if response.headers.get("Content-Type", "").split(";", 1)[0] != "image/webp":
                    raise ValueError("not a WebP image")
                content = response.read(2_000_001)
                if len(content) > 2_000_000 or not content.startswith(b"RIFF") or content[8:12] != b"WEBP":
                    raise ValueError("invalid WebP image")
            filename.parent.mkdir(parents=True, exist_ok=True)
            filename.write_bytes(content)
            downloaded += 1
            time.sleep(0.2)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            failed.append(f"{path}: {exc}")
    return downloaded, failed


def refresh(base: Path, manifest_file: Path, output: Path) -> int:
    if not base.is_file():
        raise ValueError(f"Base guide file is missing: {base}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    entries = manifest.get("guides") if isinstance(manifest, dict) else None
    if not isinstance(entries, list) or not entries:
        raise ValueError("Curated manifest needs a nonempty guides array")
    by_id = {build["id"]: build for build in read_builds(base)}
    fetched = 0
    for entry in entries:
        guide_id = entry["id"]
        if guide_id in by_id:
            build = by_id[guide_id]
        else:
            build = _validate_build(_get_json(f"{API_ROOT}/builds/{guide_id}"))
            if build["id"] != guide_id:
                raise GuideSyncError(f"Guide ID mismatch: {guide_id}")
            fetched += 1
            print(f"Fetched {fetched}: {entry['civ']} {build['title']}")
            time.sleep(0.65)
        if build.get("civ") != entry["civ"] or not build.get("steps"):
            raise ValueError(f"Invalid civilization or empty steps: {guide_id}")
        projected = {field: build[field] for field in DISPLAY_FIELDS if field in build}
        projected["curated_playstyles"] = entry.get("playstyles", [])
        by_id[guide_id] = projected
    store = GuideStore(output.parent)
    downloaded, missing = download_missing_icons(list(by_id.values()), store)
    print(f"Downloaded {downloaded} missing WebP icons; {len(missing)} remain unavailable")
    for problem in missing[:15]:
        print(f"  {problem}")
    if missing:
        raise ValueError("Missing icons remain; bundle was not replaced")
    return write_bundle(by_id, output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=DEFAULT_OUTPUT,
                        help="existing local guide cache or previous bundle")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        refresh(args.base, args.manifest, args.output)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, GuideSyncError) as exc:
        parser.exit(1, f"Guide bundle not replaced: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
