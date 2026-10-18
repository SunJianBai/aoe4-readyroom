"""Check the shipped EXE contains every native practice asset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


ROOT = Path(__file__).resolve().parents[1]


def main(exe_path: Path) -> int:
    catalog = json.loads(
        (ROOT / "assets" / "practice" / "catalog.json").read_text(encoding="utf-8")
    )
    required = {"assets/aoevillager.png", "assets/practice/catalog.json"}
    required.update(
        "assets/practice/" + item["icon"]
        for group in ("civilizations", "buildings") for item in catalog[group]
    )
    names = {name.replace("\\", "/") for name in CArchiveReader(str(exe_path)).toc}
    missing = sorted(required - names)
    unexpected = sorted(
        name for name in names
        if name.lower().endswith("icuuc.dll") or "qtwebengine" in name.lower()
    )
    if missing:
        print(f"Missing {len(missing)} practice assets: {', '.join(missing[:5])}")
    if unexpected:
        print(f"Unexpected bundled DLLs: {', '.join(unexpected[:5])}")
    if missing or unexpected:
        return 1
    print(f"Offline practice bundle verified: {len(required) - 2} image files and catalog")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify_bundle.py <AOE4Toolbox.exe>")
    raise SystemExit(main(Path(sys.argv[1])))
