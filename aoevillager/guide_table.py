"""Presentation-ready build-order rows and resource changes.

The source build and its author-written descriptions are never modified.
"""

from __future__ import annotations

from html import unescape
import re


RESOURCES = ("builders", "food", "wood", "gold", "stone")
AGE_NAMES = {1: "黑暗时代", 2: "封建时代", 3: "城堡时代", 4: "帝王时代"}


def villager_count(value: object) -> int:
    """Read common author notations such as ``5+2``, ``~5`` and ``<br>``."""
    text = unescape(re.sub(r"<[^>]*>", "", str(value or ""))).replace("≈", "~")
    total = 0
    for part in text.split("+"):
        match = re.match(r"\s*~?\s*(\d+)", part)
        if match:
            total += int(match.group(1))
    return total


def resource_change(current: object, previous: object | None) -> str:
    if previous is None:
        return "initial"
    now, before = villager_count(current), villager_count(previous)
    return "up" if now > before else "down" if now < before else "same"


def build_table_rows(build: dict) -> list[dict]:
    """Flatten age sections while retaining the previous real step for deltas."""
    rows: list[dict] = []
    previous: dict | None = None
    for section in build.get("steps") or []:
        if not isinstance(section, dict):
            continue
        advancing = section.get("type") == "ageUp"
        target = AGE_NAMES.get((section.get("age") or 1) + 1, "下一时代")
        if advancing:
            rows.append({"kind": "advance", "label": f"升级至{target}"})
        for step in section.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if step.get("type") in ("note", "gameplan"):
                note = str(step.get("gameplan") or step.get("description") or "").strip()
                if note:
                    rows.append({"kind": "note", "html": note, "in_age": advancing})
                continue
            changes = {
                key: resource_change(step.get(key), previous.get(key) if previous is not None else None)
                for key in RESOURCES
            }
            rows.append({
                "kind": "step", "step": step, "changes": changes, "in_age": advancing,
                "villagers": sum(villager_count(step.get(key)) for key in RESOURCES),
                "previous": previous,
            })
            previous = step
        note = str(section.get("gameplan") or "").strip()
        if note:
            rows.append({"kind": "note", "html": note, "in_age": advancing})
        if advancing:
            rows.append({"kind": "arrival", "label": f"已进入{target}"})
    return rows
