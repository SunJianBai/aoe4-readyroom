"""Render the editable SVG into a PNG and a multi-resolution Windows ICO."""

from __future__ import annotations

import struct
from pathlib import Path

from PyQt6.QtCore import QBuffer, QIODevice
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer


ASSETS = Path(__file__).resolve().parent / "assets"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"无法渲染 {size}px 图标")
    return bytes(buffer.data())


def main() -> None:
    renderer = QSvgRenderer(str(ASSETS / "aoevillager.svg"))
    if not renderer.isValid():
        raise RuntimeError("图标 SVG 无效")
    images = [(size, render_png(renderer, size)) for size in SIZES]
    (ASSETS / "aoevillager.png").write_bytes(images[-1][1])

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries = bytearray()
    payload = bytearray()
    for size, png in images:
        width = 0 if size == 256 else size
        entries.extend(struct.pack("<BBBBHHII", width, width, 0, 0, 1, 32, len(png), offset))
        payload.extend(png)
        offset += len(png)
    (ASSETS / "aoevillager.ico").write_bytes(header + entries + payload)


if __name__ == "__main__":
    main()
