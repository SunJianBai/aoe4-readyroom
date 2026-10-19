"""Check the shipped EXE contains the offline practice and guide assets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parents[1]


def main(exe_path: Path) -> int:
    guide_bundle_path = ROOT / "assets" / "guides" / "guides.json"
    guide_bundle = json.loads(guide_bundle_path.read_text(encoding="utf-8"))
    if len(guide_bundle.get("builds", [])) < 258:
        print("Offline guide snapshot is missing or incomplete")
        return 1
    catalog = json.loads(
        (ROOT / "assets" / "practice" / "catalog.json").read_text(encoding="utf-8")
    )
    required = {
        "assets/aoevillager.png",
        "assets/practice/catalog.json",
        "assets/guides/guides.json",
    }
    required.update(
        "assets/practice/" + item["icon"]
        for group in ("civilizations", "buildings") for item in catalog[group]
    )
    required.update(
        "assets/guides/" + str(path.relative_to(ROOT / "assets" / "guides")).replace("\\", "/")
        for path in (ROOT / "assets" / "guides").rglob("*") if path.is_file()
    )
    names = {name.replace("\\", "/") for name in CArchiveReader(str(exe_path)).toc}
    missing = sorted(required - names)
    unexpected = sorted(
        name for name in names
        if name.lower().endswith("icuuc.dll") or "qtwebengine" in name.lower()
    )
    if missing:
        print(f"Missing {len(missing)} offline assets: {', '.join(missing[:5])}")
    if unexpected:
        print(f"Unexpected bundled DLLs: {', '.join(unexpected[:5])}")
    if missing or unexpected:
        return 1
    print(f"Offline bundle verified: {len(required)} required resources")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_bundle.py <AOE4Toolbox.exe>")
    raise SystemExit(main(Path(sys.argv[1])))
