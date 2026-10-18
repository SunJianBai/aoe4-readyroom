"""One-time migration of the standalone practice page into native Qt data/assets.

Usage: python scripts/import_hotkey_catalog.py D:\\Games\\AOE4\\aoe4-hotkeys-single.html
The HTML is an input to this migration only; it is not used by the application.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "practice"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DATA_PREFIX = "https://data.aoe4world.com/images/"
GITHUB_PREFIX = "https://raw.githubusercontent.com/aoe4world/data/main/images/"


def object_entries(source: str, variable: str) -> dict[str, str]:
    match = re.search(rf"const {variable} = \{{(.*?)\n\}};", source, re.S)
    if match is None:
        raise ValueError(f"Missing JavaScript data object: {variable}")
    return dict(re.findall(r"'([^']+)':\s*'([^']+)'", match.group(1)))


def fetch_png(url: str, target: Path) -> None:
    if target.is_file() and target.read_bytes().startswith(PNG_SIGNATURE):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "AOE4Toolbox/1.0"})
            with urlopen(request, timeout=35) as response:
                data = response.read()
            if not data.startswith(PNG_SIGNATURE):
                raise ValueError(f"Not a PNG: {url}")
            target.write_bytes(data)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def main(source_path: Path) -> None:
    source = source_path.read_text(encoding="utf-8-sig")
    names = object_entries(source, "keyMappings")
    images = object_entries(source, "buildingImages")
    civ_matches = re.findall(
        r'<button class="civ-btn" data-civ="([^"]+)"[^>]*>\s*'
        r'<img src="([^"]+)" alt="([^"]+)"', source
    )
    item_matches = re.findall(
        r'<div class="building-checkbox([^"]*)">\s*'
        r'<input type="checkbox" id="build-([^"]+)" value="([^"]+)"', source
    )
    if len(civ_matches) < 20 or len(item_matches) < 65:
        raise ValueError("The source page did not yield the expected civilizations/buildings")

    civilizations = []
    for civ_id, icon_url, display_name in civ_matches:
        icon = f"civs/{civ_id}.png"
        fetch_png(icon_url, OUTPUT / icon)
        civilizations.append({"id": civ_id, "name": display_name, "icon": icon})

    buildings = []
    for classes, item_id, shortcut in item_matches:
        civ = classes.strip().split()[-1] if "civ-specific" in classes else None
        image_url = images.get(item_id) or images.get(shortcut)
        if shortcut not in names or not image_url:
            raise ValueError(f"Missing mapping for {item_id} / {shortcut}")
        if not image_url.startswith(DATA_PREFIX):
            raise ValueError(f"Unexpected building image host: {image_url}")
        relative = image_url.removeprefix(DATA_PREFIX)
        if len(Path(relative).parts) != 2 or not relative.endswith(".png"):
            raise ValueError(f"Unexpected building asset path: {relative}")
        fetch_png(GITHUB_PREFIX + relative, OUTPUT / relative)
        buildings.append({
            "id": item_id,
            "key": shortcut,
            "name": names[shortcut],
            "civ": civ,
            "icon": relative.replace("\\", "/"),
        })

    catalog = {"civilizations": civilizations, "buildings": buildings}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Imported {len(civilizations)} civilizations and {len(buildings)} buildings into {OUTPUT}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_hotkey_catalog.py <source.html>")
    main(Path(sys.argv[1]))
