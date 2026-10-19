"""Native Qt, offline-first AOE4 build-order reader."""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re

from PyQt6.QtCore import QRectF, Qt, QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor, QDesktopServices, QFont, QIcon, QImage, QLinearGradient, QPainter,
    QPainterPath, QPixmap, QRadialGradient, QTextDocument,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMenu, QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QTextBrowser, QToolButton, QToolTip, QVBoxLayout, QWidget,
)

from .guide_data import (
    CIVILIZATIONS, GuideStore, GuideSyncError, icon_path, source_url,
)
from .guide_table import RESOURCES, build_table_rows, villager_count


# Hand-edited interface glosses.  The author's build text itself is untouched.
ICON_INFO = {
    "resource/time.webp": ("时间", "此步骤建议执行的游戏时间。"),
    "resource/repair.webp": ("建造村民", "当前分配给建造或修理的村民。"),
    "resource/resource_food.webp": ("食物", "用于训练单位和研究科技的基础资源。"),
    "resource/resource_wood.webp": ("木材", "通常用于建造建筑、生产部分单位和研究科技。"),
    "resource/resource_gold.webp": ("黄金", "常用于时代升级、研究科技及训练高级单位。"),
    "resource/resource_stone.webp": ("石料", "常用于建造城镇中心、防御建筑和升级防御。"),
    "resource/sheep.webp": ("绵羊", "可由村民采集食物；通常带回城镇中心附近屠宰。"),
    "resource/deer.webp": ("鹿", "野外食物来源，可由村民或侦察兵相关机制利用。"),
    "resource/rally.webp": ("集结点", "指定新生产单位离开建筑后的前往位置。"),
    "unit_worker/villager.webp": ("村民", "采集资源、建造建筑和修理建筑的经济单位。"),
    "unit_worker/villager-china.webp": ("村民", "采集资源、建造建筑和修理建筑的经济单位。"),
    "unit_chinese/imperial-official.webp": ("命官", "中国及相关文明的特殊经济单位，可监督建筑并收取税金。"),
    "building_economy/town-center.webp": ("城镇中心", "训练村民，并为附近单位提供防御。"),
    "building_economy/house.webp": ("房屋", "提高人口上限。"),
    "building_economy/mill.webp": ("磨坊", "食物采集点，通常也提供食物相关科技。"),
    "building_economy/lumber-camp.webp": ("伐木场", "木材采集点，通常也提供伐木科技。"),
    "building_economy/mining-camp.webp": ("采矿场", "黄金和石料采集点。"),
    "building_military/barracks.webp": ("兵营", "训练步兵的军事建筑。"),
    "building_military/archery-range.webp": ("靶场", "训练弓兵及其他远程单位的军事建筑。"),
    "building_military/stable.webp": ("马厩", "训练骑兵的军事建筑。"),
    "unit_cavalry/scout.webp": ("侦察兵", "探索地图、寻找资源和敌军动向。"),
    "unit_cavalry/horseman-1.webp": ("骑手", "机动性较高的轻骑兵。"),
    "unit_chinese/zhuge-nu-2.webp": ("诸葛弩手", "中国及相关文明的远程步兵。"),
    "technology_economy/professional-scouts.webp": ("专业侦察兵", "使侦察兵能够搬运鹿尸等猎物。"),
    "abilities/repair.webp": ("建造／修理", "命令村民建造或修理目标。"),
}

ICON_TILE_COLORS = {
    "icon-ability": ("#5c457b", "#4d366e"),
    "icon-tech": ("#469586", "#266d5b"),
    "icon-military": ("#8b5d44", "#683a22"),
    "icon-none": ("#646c79", "#4f5866"),
    "icon-default": ("#4b6382", "#1d2432"),
    "icon-landmark": ("#232e3e", "#0c0f17"),
}

PLAYSTYLE_LABELS = {
    "feudal_attack": "封建进攻",
    "fast_castle": "速城堡 直城",
    "multi_tc": "多 TC 2TC 3TC 4TC",
    "dark_age_attack": "黑暗快攻",
}


def _icon_tile(source: QImage, variant: str) -> QImage:
    """Qt's rich text cannot paint CSS radial gradients, so compose icon tiles."""
    tile = QImage(36, 36, QImage.Format.Format_ARGB32_Premultiplied)
    tile.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tile)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    light, dark = ICON_TILE_COLORS.get(variant, ICON_TILE_COLORS["icon-default"])
    gradient = QRadialGradient(18, 1, 39)
    gradient.setColorAt(0, QColor(light))
    gradient.setColorAt(1, QColor(dark))
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(0, 0, 36, 36), 4, 4)
    painter.fillPath(shape, gradient)
    painter.drawImage(QRectF(2, 2, 32, 32), source)
    painter.end()
    return tile


class _StepHtml(HTMLParser):
    """Keep only text, line breaks and local cached icons from author HTML."""

    def __init__(self, store: GuideStore, tips: dict[str, str], images: set[str],
                 variants: dict[str, str] | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.store = store
        self.tips = tips
        self.images = images
        self.variants = variants
        self.fragments: list[str] = []

    def handle_data(self, data: str) -> None:
        self.fragments.append(escape(data))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.fragments.append("<br>")
        if tag != "img":
            return
        attributes = dict(attrs)
        path = icon_path(attributes.get("src") or "")
        if path is None:
            return
        relative = path.removeprefix("/assets/pictures/")
        default_name, explanation = ICON_INFO.get(relative, ("", ""))
        metadata = self.store.icon_info(path)
        label = (default_name or metadata.get("title") or attributes.get("title")
                 or attributes.get("alt") or Path(relative).stem.replace("-", " "))
        explanation = explanation or str(metadata.get("description") or "")
        costs = metadata.get("costs") or {}
        cost_text = " · ".join(
            f"{name} {costs[key]}" for key, name in
            (("food", "食物"), ("wood", "木材"), ("gold", "黄金"),
             ("stone", "石料"), ("oliveoil", "橄榄油"), ("time", "建造／训练秒数"))
            if isinstance(costs, dict) and costs.get(key)
        )
        url = "guideicon:/" + relative
        self.tips[url] = "\n".join(part for part in (label, explanation, cost_text) if part)
        cached = self.store.cached_icon(path)
        if cached and cached.is_file():
            self.images.add(path)
            if self.variants is not None:
                classes = (attributes.get("class") or "").split()
                self.variants[path] = next(
                    (name for name in classes if name in ICON_TILE_COLORS),
                    "icon-none" if relative.startswith("resource/") else "icon-default",
                )
            self.fragments.append(
                f'<a href="{escape(url, quote=True)}">'
                f'<img src="{escape(url, quote=True)}" width="36" height="36"></a>'
            )
        else:
            self.fragments.append(f"[{escape(label)}]")


def _rich_step(text: str, store: GuideStore, tips: dict[str, str], images: set[str],
               variants: dict[str, str] | None = None) -> str:
    parser = _StepHtml(store, tips, images, variants)
    parser.feed(text)
    parser.close()
    return "".join(parser.fragments)


def _age_name(age: object) -> str:
    return {1: "黑暗时代", 2: "封建时代", 3: "城堡时代", 4: "帝王时代"}.get(age, "时代")


GUIDE_STYLE = """
QWidget { background:#1d2432; color:#e9ebee; font-family:'Microsoft YaHei UI'; font-size:12px; }
QLabel { background:transparent; }
QFrame#guideBar { background:#324156; border:0; border-radius:8px; }
QFrame#guideFilter { background:#324156; border:0; border-radius:7px; }
QFrame#guideCard { background:#324156; border:1px solid #324156; border-radius:9px; }
QFrame#guideCard:hover { background:#3d516b; border:1px solid #e7c05e; }
QFrame#guideAgeRail { background:transparent; border-left:1px solid #506077; }
QLabel#guideTitle { color:#e7c05e; font-size:19px; font-weight:700; }
QLabel#guideCardTitle { color:#e7c05e; font-weight:700; font-size:15px; }
QLabel#guideGold, QLabel#guideAgeTime { color:#e7c05e; font-weight:600; }
QLabel#guideSmall { color:#aebac9; font-size:11px; }
QPushButton, QToolButton { background:#324156; border:1px solid #506077; border-radius:6px;
    padding:7px 12px; color:#e9ebee; }
QPushButton:hover, QToolButton:hover { background:#3d516b; border-color:#e7c05e; }
QPushButton:checked { background:#e7c05e; color:#1d2432; border-color:#e7c05e; }
QPushButton#guidePrimary { background:#e7c05e; color:#1d2432; font-weight:700; border:0; }
QPushButton#guidePrimary:hover { background:#f1d381; }
QLineEdit, QComboBox { background:#29374a; color:#e9ebee; border:1px solid #52647a;
    border-radius:6px; padding:7px 10px; min-height:24px; }
QLineEdit:focus, QComboBox:focus { border-color:#e7c05e; }
QScrollArea { border:0; background:#1d2432; }
QScrollArea > QWidget > QWidget { background:#1d2432; }
QScrollBar:vertical { background:#1d2432; width:9px; }
QScrollBar::handle:vertical { background:#5d6e84; border-radius:4px; min-height:30px; }
QMenu { background:#324156; color:#e9ebee; border:1px solid #52647a; }
QMenu::item:selected { background:#3d516b; color:#e7c05e; }
QToolTip { background:#3d516b; color:#e9ebee; border:1px solid #e7c05e; }
"""


def _stamp(value: object) -> int:
    if isinstance(value, dict):
        return int(value.get("_seconds") or 0)
    return 0


def _age_times(build: dict) -> str:
    timings = build.get("ageTimings") or {}
    result = []
    for key, label in (("feudal", "Ⅱ"), ("castle", "Ⅲ"), ("imperial", "Ⅳ")):
        entry = timings.get(key) if isinstance(timings, dict) else None
        seconds = entry.get("t") if isinstance(entry, dict) else None
        if isinstance(seconds, (int, float)) and seconds > 0:
            result.append(f"{label} {int(seconds)//60}:{int(seconds)%60:02d}")
    return "   ".join(result) or "时代时间未记录"


def _flat_steps(build: dict) -> list[tuple[str, dict]]:
    result = []
    for section in build.get("steps") or []:
        if not isinstance(section, dict):
            continue
        age = section.get("age")
        heading = (f"升级至{_age_name((age or 1) + 1)}"
                   if section.get("type") == "ageUp" else _age_name(age))
        plan = str(section.get("gameplan") or "").strip()
        if plan:
            result.append((heading, {"description": plan, "time": "提示"}))
        for step in section.get("steps") or []:
            if isinstance(step, dict):
                result.append((heading, step))
    return result


class RichGuideText(QTextBrowser):
    def __init__(self, store: GuideStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.tips: dict[str, str] = {}
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setMouseTracking(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("QTextBrowser{background:#324156;color:#e9ebee;border:0;border-radius:8px;padding:14px;}")

    def render_html(self, html: str, images: set[str],
                    variants: dict[str, str] | None = None) -> None:
        document = QTextDocument(self)
        document.setDefaultFont(self.font())
        document.setDocumentMargin(0)
        for path in images:
            icon = self.store.cached_icon(path)
            if icon and icon.is_file():
                picture = QImage(str(icon))
                if not picture.isNull():
                    variant = (variants or {}).get(
                        path, "icon-none" if "/resource/" in path else "icon-default"
                    )
                    document.addResource(
                        QTextDocument.ResourceType.ImageResource,
                        QUrl("guideicon:/" + path.removeprefix("/assets/pictures/")),
                        _icon_tile(picture, variant),
                    )
        document.setHtml(html)
        self.setDocument(document)
        self.verticalScrollBar().setValue(0)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        url = self.anchorAt(event.pos())
        if url in self.tips:
            QToolTip.showText(event.globalPosition().toPoint(), self.tips[url], self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(event)


TABLE_WIDTHS = (68, 60, 56, 62, 62, 62, 62)
TABLE_ICONS = (
    ("resource/time.webp", "时间"),
    ("unit_worker/villager.webp", "村民总数"),
    ("resource/repair.webp", "建造"),
    ("resource/resource_food.webp", "食物"),
    ("resource/resource_wood.webp", "木材"),
    ("resource/resource_gold.webp", "黄金"),
    ("resource/resource_stone.webp", "石料"),
)
RESOURCE_COLORS = {
    "builders": (94, 83, 64), "food": (136, 64, 64),
    "wood": (79, 107, 58), "gold": (138, 109, 46),
    "stone": (89, 102, 122),
}
RESOURCE_LABELS = dict(zip(RESOURCES, ("建造", "食物", "木材", "黄金", "石料")))


class StepDescription(RichGuideText):
    """A non-scrolling rich-text cell with offline icon tiles and hover details."""

    def __init__(self, store: GuideStore, html: str) -> None:
        super().__init__(store)
        self.setStyleSheet("QTextBrowser{background:transparent;color:#e9ebee;border:0;padding:0;font-size:13px;}")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tips = {}
        images: set[str] = set()
        variants: dict[str, str] = {}
        rich = _rich_step(html, store, self.tips, images, variants) or "—"
        self.render_html(f'<body style="color:#e9ebee;font-size:13px;">{rich}</body>', images, variants)
        self._fit_height()

    def _fit_height(self) -> None:
        self.document().setTextWidth(max(90, self.viewport().width() - 2))
        height = max(48, int(self.document().size().height()) + 6)
        if self.height() != height:
            self.setFixedHeight(height)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit_height()

    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class ResourcePill(QWidget):
    """A resource tint plus directional gold edge, matching the source's legend."""

    def __init__(self, key: str, value: object, previous: object | None, change: str,
                 width: int) -> None:
        super().__init__()
        self.key, self.value, self.change = key, str(value or "").strip(), change
        self.setFixedSize(width, 34)
        before, now = villager_count(previous), villager_count(value)
        detail = {
            "up": f"比上一步增加 {now - before}",
            "down": f"比上一步减少 {before - now}",
            "same": "与上一步相同",
            "initial": "第一步的分配",
        }[change]
        label = RESOURCE_LABELS[key]
        self.setToolTip(f"{label}：{self.value or '—'}\n{detail}")
        self.setAccessibleName(f"{label} {self.value or '无'}，{detail}")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        value = villager_count(self.value)
        if value:
            red, green, blue = RESOURCE_COLORS[self.key]
            alpha = 31 if self.change == "same" else 115
            border_alpha = 56 if self.change == "same" else 166
            painter.setBrush(QColor(red, green, blue, alpha))
            painter.setPen(QColor(red, green, blue, border_alpha))
            painter.drawRoundedRect(self.rect().adjusted(1, 2, -1, -2), 6, 6)
        if self.change in ("up", "down"):
            painter.setPen(QColor("#e7c05e"))
            edge = 3 if self.change == "up" else self.height() - 4
            painter.drawLine(7, edge, self.width() - 8, edge)
        painter.setPen(QColor("#e9ebee" if value else "#8794a5"))
        font = QFont(self.font())
        font.setBold(bool(value))
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.value if value else "—")


class GuideStepRow(QFrame):
    def __init__(self, row: dict, store: GuideStore) -> None:
        super().__init__()
        self.in_age = bool(row["in_age"])
        self.setMinimumHeight(58)
        step, previous = row["step"], row["previous"]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(4)
        time = QLabel(str(step.get("time") or "—"))
        time.setStyleSheet("color:#e7c05e;font-weight:700;font-size:13px;")
        time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time.setFixedWidth(TABLE_WIDTHS[0])
        time.setToolTip("建议执行时间")
        layout.addWidget(time)
        villagers = QLabel(str(row["villagers"] or "—"))
        villagers.setStyleSheet("color:#aebac9;font-weight:700;font-size:13px;")
        villagers.setAlignment(Qt.AlignmentFlag.AlignCenter)
        villagers.setFixedWidth(TABLE_WIDTHS[1])
        villagers.setToolTip("五类工作分配合计的村民数")
        layout.addWidget(villagers)
        for index, key in enumerate(RESOURCES, 2):
            pill = ResourcePill(key, step.get(key), previous.get(key) if previous else None,
                                row["changes"][key], TABLE_WIDTHS[index])
            layout.addWidget(pill, alignment=Qt.AlignmentFlag.AlignVCenter)
        body = str(step.get("description") or step.get("gameplan") or "")
        self.description = StepDescription(store, body)
        layout.addWidget(self.description, 1)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#324156"))
        if self.in_age:
            shade = QLinearGradient(0, 0, self.width(), 0)
            shade.setColorAt(0, QColor(231, 192, 94, 32))
            shade.setColorAt(0.6, QColor(231, 192, 94, 5))
            shade.setColorAt(1, QColor(231, 192, 94, 0))
            painter.fillRect(self.rect(), shade)
            painter.fillRect(0, 0, 3, self.height(), QColor("#e7c05e"))
        painter.setPen(QColor("#4a596d"))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class GuideAgeRow(QFrame):
    def __init__(self, label: str, arrival: bool) -> None:
        super().__init__()
        self.arrival = arrival
        self.setFixedHeight(50)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 12, 0)
        caption = QLabel(label if arrival else "↑  " + label)
        caption.setStyleSheet("color:#e7c05e;font-weight:800;font-size:13px;")
        layout.addWidget(caption)
        layout.addStretch(1)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#324156"))
        shade = QLinearGradient(0, 0, self.width(), 0)
        shade.setColorAt(0, QColor(231, 192, 94, 77 if self.arrival else 38))
        shade.setColorAt(0.6, QColor(231, 192, 94, 31 if self.arrival else 5))
        shade.setColorAt(1, QColor(231, 192, 94, 20 if self.arrival else 0))
        painter.fillRect(self.rect(), shade)
        painter.fillRect(0, 0, 3, self.height(), QColor("#e7c05e"))
        painter.setPen(QColor("#4a596d"))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class GuideNoteRow(QFrame):
    def __init__(self, store: GuideStore, html: str, in_age: bool) -> None:
        super().__init__()
        self.in_age = in_age
        self.setMinimumHeight(58)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 5, 10, 5)
        label = QLabel("说明")
        label.setFixedWidth(sum(TABLE_WIDTHS) + 6 * 4 - 4)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet("color:#e7c05e;font-weight:700;")
        layout.addWidget(label)
        description = StepDescription(store, html)
        layout.addWidget(description, 1)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#324156"))
        if self.in_age:
            shade = QLinearGradient(0, 0, self.width(), 0)
            shade.setColorAt(0, QColor(231, 192, 94, 32))
            shade.setColorAt(1, QColor(231, 192, 94, 0))
            painter.fillRect(self.rect(), shade)
            painter.fillRect(0, 0, 3, self.height(), QColor("#e7c05e"))
        painter.setPen(QColor("#4a596d"))
        painter.drawLine(0, self.height() - 1, self.width(), self.height() - 1)


class GuideDetail(QScrollArea):
    """Native, scrollable build table with locally rendered game icons."""

    def __init__(self, store: GuideStore) -> None:
        super().__init__()
        self.store = store
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def show_build(self, build: dict) -> None:
        old = self.takeWidget()
        if old is not None:
            old.deleteLater()
        content = QWidget()
        content.setObjectName("guideTableContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        description = str(build.get("description") or "").strip()
        if description:
            intro = QLabel(description)
            intro.setTextFormat(Qt.TextFormat.PlainText)
            intro.setWordWrap(True)
            intro.setStyleSheet("background:#324156;color:#e9ebee;padding:12px;")
            layout.addWidget(intro)
        header = QFrame()
        header.setStyleSheet("QFrame{background:#324156;border-bottom:1px solid #526075;}")
        header.setFixedHeight(58)
        columns = QHBoxLayout(header)
        columns.setContentsMargins(10, 4, 10, 4)
        columns.setSpacing(4)
        for index, (width, (path, title)) in enumerate(zip(TABLE_WIDTHS, TABLE_ICONS)):
            icon = QLabel()
            icon.setFixedWidth(width)
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setToolTip(
                title + ("\n上沿金线：增加；下沿金线：减少；浅色底：不变。" if index >= 2 else "")
            )
            icon.setAccessibleName(title)
            cached = self.store.cached_icon("/assets/pictures/" + path)
            if cached:
                icon.setPixmap(QPixmap(str(cached)).scaled(
                    29, 29, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
            columns.addWidget(icon)
        caption = QLabel("步骤说明 / Description")
        caption.setStyleSheet("color:#e9ebee;font-size:13px;font-weight:700;")
        caption.setWordWrap(True)
        caption.setMinimumWidth(0)
        caption.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        columns.addWidget(caption, 1)
        layout.addWidget(header)
        for row in build_table_rows(build):
            if row["kind"] == "step":
                widget = GuideStepRow(row, self.store)
            elif row["kind"] == "note":
                widget = GuideNoteRow(self.store, row["html"], row["in_age"])
            else:
                widget = GuideAgeRow(row["label"], row["kind"] == "arrival")
            layout.addWidget(widget)
        layout.addStretch(1)
        self.setWidget(content)
        self.verticalScrollBar().setValue(0)


class CivCard(QPushButton):
    def __init__(self, code: str, name: str, flag: Path) -> None:
        super().__init__()
        self.code, self.name = code, name
        self.picture = QPixmap(str(flag))
        self.setMinimumHeight(122)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"选择文明：{name}")
        self.setToolTip(f"查看{name}的离线流程")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect().adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(area), 10, 10)
        painter.setClipPath(clip)
        painter.fillRect(area, QColor("#324156"))
        if not self.picture.isNull():
            scaled = self.picture.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            x = area.x() + (area.width() - scaled.width()) // 2
            y = area.y() + (area.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
        gradient = QLinearGradient(0, area.top(), 0, area.bottom())
        gradient.setColorAt(0, QColor(29, 36, 50, 0))
        gradient.setColorAt(0.55, QColor(29, 36, 50, 35))
        gradient.setColorAt(1, QColor(29, 36, 50, 235))
        painter.fillRect(area, gradient)
        if self.isDown():
            painter.fillRect(area, QColor(6, 17, 28, 90))
        painter.setPen(QColor("#f1d381" if self.underMouse() or self.hasFocus() else "#e7c05e"))
        font = QFont(self.font())
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(area.adjusted(11, 0, -8, -9), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, self.name)
        if self.underMouse() or self.hasFocus():
            painter.setClipping(False)
            painter.setPen(QColor("#e7c05e"))
            painter.drawRoundedRect(QRectF(area), 10, 10)


class CivBanner(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.picture = QPixmap()
        self.setFixedHeight(112)

    def set_civ(self, name: str, flag: Path | None) -> None:
        self.title = name
        self.picture = QPixmap(str(flag)) if flag and flag.is_file() else QPixmap()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(area), 8, 8)
        painter.setClipPath(clip)
        painter.fillRect(area, QColor("#324156"))
        if not self.picture.isNull():
            scaled = self.picture.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(0, (area.height() - scaled.height()) // 2, scaled)
        shade = QLinearGradient(0, 0, area.width(), 0)
        shade.setColorAt(0, QColor(29, 36, 50, 28))
        shade.setColorAt(1, QColor(29, 36, 50, 240))
        painter.fillRect(area, shade)
        painter.setPen(QColor("#e7c05e"))
        font = QFont(self.font())
        font.setPointSize(19)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(area.adjusted(18, 0, -15, 0), Qt.AlignmentFlag.AlignVCenter, self.title)


def _parse_time(value: object) -> int | None:
    match = re.search(r"(\d+):(\d{2})", str(value or ""))
    return int(match[1]) * 60 + int(match[2]) if match else None


class TimelineWidget(QFrame):
    """Age markers and time scale, independent of the site's web runtime."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("guideFilter")
        self.setFixedHeight(84)
        self.build: dict = {}

    def show_build(self, build: dict) -> None:
        self.build = build
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, right = 48, max(120, self.width() - 34)
        painter.setPen(QColor("#d5dfeb"))
        painter.drawText(12, 19, "时间轴")
        painter.setPen(QColor("#70839b"))
        painter.drawLine(left, 47, right, 47)
        times = [_parse_time(step.get("time")) for _, step in _flat_steps(self.build)]
        known = [time for time in times if time is not None]
        timings = self.build.get("ageTimings") or {}
        marks = []
        for key, label in (("feudal", "Ⅱ"), ("castle", "Ⅲ"), ("imperial", "Ⅳ")):
            entry = timings.get(key) if isinstance(timings, dict) else None
            time = entry.get("t") if isinstance(entry, dict) else None
            if isinstance(time, (int, float)) and time > 0:
                marks.append((int(time), label))
        maximum = max([360, *known, *(time for time, _ in marks)])
        maximum = ((maximum + 119) // 120) * 120
        for time in range(0, maximum + 1, 120):
            x = left + (right - left) * time // maximum
            painter.setPen(QColor("#879ab3"))
            painter.drawLine(x, 43, x, 52)
            painter.drawText(x - 13, 70, f"{time // 60}:00")
        for time, label in marks:
            x = left + (right - left) * time // maximum
            painter.setPen(QColor("#e7c05e"))
            painter.drawLine(x, 30, x, 51)
            painter.drawText(x - 16, 27, f"{label} {time // 60}:{time % 60:02d}")


class EconomyChart(QFrame):
    COLORS = (("food", "食物", "#d78c8a"), ("wood", "木材", "#9bc693"),
              ("gold", "黄金", "#f0c967"), ("stone", "石料", "#a4bbd3"))

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("guideFilter")
        self.setFixedHeight(150)
        self.points: list[tuple[int, dict[str, int]]] = []

    def show_build(self, build: dict) -> None:
        values = {key: 0 for key, _, _ in self.COLORS}
        self.points = []
        for _, step in _flat_steps(build):
            time = _parse_time(step.get("time"))
            if time is None:
                continue
            for key in values:
                match = re.search(r"\d+", str(step.get(key) or ""))
                if match:
                    values[key] = int(match[0])
            self.points.append((time, values.copy()))
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#e7ebf0"))
        painter.drawText(12, 20, "经济分配 · 村民数量")
        left, right, top, bottom = 40, max(100, self.width() - 18), 33, 112
        painter.setPen(QColor("#62748d"))
        painter.drawLine(left, bottom, right, bottom)
        painter.drawLine(left, top, left, bottom)
        if not self.points:
            painter.drawText(55, 80, "没有可绘制的经济数据")
            return
        max_time = max(60, max(time for time, _ in self.points))
        max_value = max(5, max(value for _, item in self.points for value in item.values()))
        for key, name, color in self.COLORS:
            painter.setPen(QColor(color))
            previous = None
            for time, values in self.points:
                point = (left + (right - left) * time // max_time,
                         bottom - (bottom - top) * values[key] // max_value)
                if previous:
                    painter.drawLine(previous[0], previous[1], point[0], point[1])
                previous = point
        for index, (_, name, color) in enumerate(self.COLORS):
            painter.setPen(QColor(color))
            painter.drawText(15 + index * 86, 139, f"● {name}")


class GuideFlagPane(QWidget):
    """The site's flag cover with a fade into the card surface."""

    def __init__(self, flag: Path) -> None:
        super().__init__()
        self.picture = QPixmap(str(flag))
        self.setFixedWidth(158)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = self.rect()
        painter.fillRect(area, QColor("#324156"))
        if not self.picture.isNull():
            scaled = self.picture.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                         Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap((area.width() - scaled.width()) // 2,
                               (area.height() - scaled.height()) // 2, scaled)
        fade = QLinearGradient(0, 0, area.width(), 0)
        fade.setColorAt(0, QColor(50, 65, 86, 0))
        fade.setColorAt(0.45, QColor(50, 65, 86, 30))
        fade.setColorAt(1, QColor("#324156"))
        painter.fillRect(area, fade)


class GuideCard(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, build: dict, store: GuideStore) -> None:
        super().__init__()
        self.build_id = build["id"]
        self.setObjectName("guideCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("点击阅读完整流程")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(10)
        self.flag = GuideFlagPane(store.flag(str(build.get("civ") or ""), large=True))
        layout.addWidget(self.flag)
        copy = QVBoxLayout()
        copy.setContentsMargins(0, 10, 0, 9)
        copy.setSpacing(3)
        self.full_title = str(build.get("title") or "未命名流程")
        self.title = QLabel(self.full_title)
        self.title.setObjectName("guideCardTitle")
        self.title.setToolTip(self.full_title)
        self.title.setMinimumWidth(0)
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        copy.addWidget(self.title)
        creator = str(build.get("author") or "未知作者")
        author = QLabel(f"作者  {creator}")
        author.setObjectName("guideSmall")
        author.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        copy.addWidget(author)
        curated = "精选 · " if "curated_playstyles" in build else ""
        stats = QLabel(f"{curated}{build.get('season') or '赛季未记录'}   ·   {build.get('views') or 0} 次浏览")
        stats.setObjectName("guideSmall")
        stats.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        copy.addWidget(stats)
        self.mobile_times = QLabel(_age_times(build))
        self.mobile_times.setObjectName("guideGold")
        self.mobile_times.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        copy.addWidget(self.mobile_times)
        layout.addLayout(copy, 1)
        self.age_rail = QFrame()
        self.age_rail.setObjectName("guideAgeRail")
        self.age_rail.setFixedWidth(124)
        self.age_rail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        ages = QVBoxLayout(self.age_rail)
        ages.setContentsMargins(13, 9, 0, 8)
        ages.setSpacing(1)
        timings = build.get("ageTimings") or {}
        for key, label in (("feudal", "Ⅱ"), ("castle", "Ⅲ"), ("imperial", "Ⅳ")):
            entry = timings.get(key) if isinstance(timings, dict) else None
            seconds = entry.get("t") if isinstance(entry, dict) else None
            value = f"{int(seconds) // 60}:{int(seconds) % 60:02d}" if isinstance(seconds, (int, float)) and seconds > 0 else "—"
            row = QLabel(f"{label}    {value}")
            row.setObjectName("guideAgeTime")
            ages.addWidget(row)
        layout.addWidget(self.age_rail)
        self.has_age_times = _age_times(build) != "时代时间未记录"
        self.setFixedHeight(104)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        show_rail = self.has_age_times and self.width() >= 630
        self.age_rail.setVisible(show_rail)
        self.mobile_times.setVisible(self.has_age_times and not show_rail)
        available = self.width() - self.flag.width() - (self.age_rail.width() if show_rail else 0) - 48
        self.title.setText(self.title.fontMetrics().elidedText(
            self.full_title, Qt.TextElideMode.ElideRight, max(70, available)
        ))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit(self.build_id)
        super().mouseReleaseEvent(event)


class FocusDialog(QDialog):
    def __init__(self, store: GuideStore, build: dict, floating: bool, parent: QWidget) -> None:
        flags = Qt.WindowType.Window | (Qt.WindowType.WindowStaysOnTopHint if floating else Qt.WindowType(0))
        super().__init__(parent, flags)
        self.store = store
        self.build = build
        self.steps = _flat_steps(build)
        self.index = 0
        self.elapsed = 0
        self.setWindowTitle(f"逐步播放 · {build.get('title') or '流程'}")
        self.resize(480 if floating else 800, 320 if floating else 560)
        self.setMinimumSize(360, 250)
        self.setStyleSheet(GUIDE_STYLE)
        self.setModal(False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 18)
        layout.setSpacing(10)
        top = QHBoxLayout()
        self.heading = QLabel()
        self.heading.setObjectName("guideGold")
        top.addWidget(self.heading, 1)
        self.progress = QLabel()
        top.addWidget(self.progress)
        layout.addLayout(top)
        self.bar = QFrame()
        self.bar.setFixedHeight(5)
        self.bar.setObjectName("guideProgress")
        layout.addWidget(self.bar)
        self.body = RichGuideText(store)
        layout.addWidget(self.body, 1)
        self.resources = QLabel()
        self.resources.setObjectName("guideGold")
        layout.addWidget(self.resources)
        bottom = QHBoxLayout()
        self.clock = QLabel("00:00")
        bottom.addWidget(self.clock)
        bottom.addStretch(1)
        self.previous = QPushButton("← 上一步")
        self.previous.clicked.connect(lambda: self._move(-1))
        bottom.addWidget(self.previous)
        self.sound = QToolButton()
        self.sound.setText("音效 开")
        self.sound.setCheckable(True)
        self.sound.setChecked(True)
        self.sound.toggled.connect(lambda enabled: self.sound.setText("音效 开" if enabled else "音效 关"))
        bottom.addWidget(self.sound)
        self.next = QPushButton("下一步 →")
        self.next.clicked.connect(lambda: self._move(1))
        bottom.addWidget(self.next)
        layout.addLayout(bottom)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(1000)
        self._render()

    def _tick(self) -> None:
        self.elapsed += 1
        self.clock.setText(f"{self.elapsed // 60:02d}:{self.elapsed % 60:02d}")

    def _move(self, delta: int) -> None:
        if 0 <= self.index + delta < len(self.steps):
            self.index += delta
            if delta > 0 and self.sound.isChecked():
                QApplication.beep()
            self._render()

    def _render(self) -> None:
        total = len(self.steps)
        self.previous.setEnabled(self.index > 0)
        self.next.setEnabled(self.index < total - 1)
        if not total:
            self.heading.setText("没有可播放的步骤")
            self.progress.setText("0/0")
            self.body.render_html("<p>这篇流程没有步骤。</p>", set())
            return
        heading, step = self.steps[self.index]
        self.heading.setText(f"{heading} · {step.get('time') or '—'}")
        self.progress.setText(f"{self.index + 1}/{total}")
        self.bar.setStyleSheet(
            "QFrame#guideProgress{border:0;background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 #e7c05e,stop:{(self.index + 1) / total:.3f} #e7c05e,"
            f"stop:{min(1, (self.index + 1) / total + .001):.3f} #3d516b,stop:1 #3d516b);}}"
        )
        self.body.tips = {}
        images: set[str] = set()
        body = _rich_step(str(step.get("description") or step.get("gameplan") or ""),
                          self.store, self.body.tips, images)
        self.body.render_html(f'<body style="font-size:18px;color:#f2eee5;">{body or "—"}</body>', images)
        counts = [f"{name} {step[key]}" for key, name in (("villagers", "村民"), ("food", "食物"),
                  ("wood", "木材"), ("gold", "黄金"), ("stone", "石料")) if str(step.get(key) or "").strip()]
        self.resources.setText("    ".join(counts))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Right, Qt.Key.Key_Space):
            self._move(1)
        elif event.key() == Qt.Key.Key_Left:
            self._move(-1)
        else:
            super().keyPressEvent(event)


class GuideWorker(QThread):
    progress = pyqtSignal(str)
    succeeded = pyqtSignal(int, int)
    failed = pyqtSignal(str)

    def __init__(self, store: GuideStore, operation: str, argument: str = "") -> None:
        super().__init__()
        self.store = store
        self.operation = operation
        self.argument = argument

    def run(self) -> None:
        try:
            if self.operation == "sync":
                count, missing = self.store.sync_public(self.progress.emit, self.isInterruptionRequested)
            elif self.operation == "link":
                count, missing = self.store.import_link(
                    self.argument, self.progress.emit, self.isInterruptionRequested
                )
            else:
                count, missing = self.store.import_file(
                    Path(self.argument), self.progress.emit, self.isInterruptionRequested
                )
            self.succeeded.emit(count, missing)
        except (GuideSyncError, ValueError, OSError) as exc:
            self.failed.emit(str(exc))


class GuidePage(QWidget):
    """Offline Qt counterpart of the site's public browsing and playback journey."""

    def __init__(self, folder: Path) -> None:
        super().__init__()
        self.store = GuideStore(folder, prefer_bundled=True)
        self.bundled = self.store.bundle_file.is_file()
        self.data = self.store.load()
        self.worker: GuideWorker | None = None
        self.current_id: str | None = None
        self.current_civ = ""
        self.mode = "score"
        self.focus_windows: list[FocusDialog] = []
        self.setStyleSheet(GUIDE_STYLE)
        root = QVBoxLayout(self)
        root.setContentsMargins(3, 3, 3, 3)
        root.setSpacing(7)

        bar = QFrame()
        bar.setObjectName("guideBar")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(10, 6, 10, 6)
        self.back_button = QToolButton()
        self.back_button.setText("←")
        self.back_button.setToolTip("返回上一层")
        self.back_button.clicked.connect(self._back)
        bar_layout.addWidget(self.back_button)
        self.bar_title = QLabel("文明与开局流程")
        self.bar_title.setObjectName("guideTitle")
        bar_layout.addWidget(self.bar_title, 1)
        self.all_button = QToolButton()
        self.all_button.setText("全部流程")
        self.all_button.clicked.connect(lambda: self._show_civ(""))
        bar_layout.addWidget(self.all_button)
        self.menu_button = QToolButton()
        self.menu_button.setText("资料")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu = QMenu(self.menu_button)
        self.data_actions = []
        if not self.bundled:
            self.data_actions = [
                self.menu.addAction("更新公开流程（手动）", self._sync),
                self.menu.addAction("粘贴链接导入单篇", self._import_link),
                self.menu.addAction("导入批量 JSON", self._import_file),
            ]
            self.menu.addSeparator()
        self.source_action = self.menu.addAction("在原站打开当前流程", self._open_source)
        self.source_action.setEnabled(False)
        self.menu.addAction("素材与数据来源", self._show_attribution)
        self.menu_button.setMenu(self.menu)
        bar_layout.addWidget(self.menu_button)
        root.addWidget(bar)

        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        self._make_home()
        self._make_list()
        self._make_detail()
        self.status = QLabel()
        self.status.setObjectName("guideSmall")
        self.status.setToolTip("内置版流程和图标均可离线阅读。" if self.bundled else
                               "只有手动更新或导入时才会连接 AOE4 Guides；图标随程序离线提供。")
        root.addWidget(self.status)
        self.status.hide()
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.status.hide)
        self._refresh_home()
        self._refresh_list()
        self._show_home()

    def _make_home(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        heading = QLabel("选择文明")
        heading.setObjectName("guideTitle")
        layout.addWidget(heading)
        search = QLineEdit()
        search.setPlaceholderText("搜索文明")
        search.textChanged.connect(self._layout_civs)
        self.civ_search = search
        layout.addWidget(search)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.civ_grid = QGridLayout(content)
        self.civ_grid.setContentsMargins(0, 5, 0, 5)
        self.civ_grid.setSpacing(11)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        self.civ_cards = []
        available_civs = {build.get("civ") for build in self.data["builds"]}
        for code, name in CIVILIZATIONS.items():
            if self.bundled and code not in available_civs:
                continue
            card = CivCard(code, name, self.store.flag(code, large=True))
            card.clicked.connect(lambda checked=False, selected=code: self._show_civ(selected))
            self.civ_cards.append(card)
        self.home_count = QLabel()
        self.home_count.setObjectName("guideSmall")
        layout.addWidget(self.home_count)
        self.pages.addWidget(page)

    def _make_list(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 3, 4, 2)
        layout.setSpacing(7)
        self.civ_banner = CivBanner()
        layout.addWidget(self.civ_banner)
        tabs = QHBoxLayout()
        self.mode_buttons = {}
        for text, mode in (("热门", "score"), ("经典", "scoreAllTime"), ("最新", "timeCreated")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=mode: self._set_mode(value))
            self.mode_buttons[mode] = button
            tabs.addWidget(button)
        tabs.addStretch(1)
        self.mode_buttons[self.mode].setChecked(True)
        layout.addLayout(tabs)
        filter_row = QHBoxLayout()
        self.build_search = QLineEdit()
        self.build_search.setPlaceholderText("搜索标题／作者／打法")
        self.build_search.textChanged.connect(self._refresh_list)
        filter_row.addWidget(self.build_search, 2)
        self.civ_filter = QComboBox()
        self.civ_filter.addItem("全部文明", "")
        available_civs = {build.get("civ") for build in self.data["builds"]}
        for code, name in CIVILIZATIONS.items():
            if self.bundled and code not in available_civs:
                continue
            self.civ_filter.addItem(name, code)
        self.civ_filter.currentIndexChanged.connect(self._filter_civ_changed)
        filter_row.addWidget(self.civ_filter, 1)
        self.filter_button = QToolButton()
        self.filter_button.setText("筛选")
        self.filter_button.setCheckable(True)
        self.filter_button.toggled.connect(self._toggle_filters)
        filter_row.addWidget(self.filter_button)
        layout.addLayout(filter_row)
        self.filters = QFrame()
        self.filters.setObjectName("guideFilter")
        filter_grid = QGridLayout(self.filters)
        filter_grid.setContentsMargins(8, 8, 8, 8)
        self.season = QComboBox()
        self.game_map = QComboBox()
        self.strategy = QComboBox()
        for widget, label, column in ((self.season, "赛季", 0), (self.game_map, "地图", 1),
                                      (self.strategy, "战术", 2)):
            widget.setToolTip(label)
            widget.currentIndexChanged.connect(self._refresh_list)
            filter_grid.addWidget(widget, 0, column)
        self.filters.setVisible(False)
        layout.addWidget(self.filters)
        self.list_count = QLabel()
        self.list_count.setObjectName("guideSmall")
        layout.addWidget(self.list_count)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.cards_area = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_area)
        self.cards_layout.setContentsMargins(0, 1, 0, 1)
        self.cards_layout.setSpacing(8)
        scroll.setWidget(self.cards_area)
        layout.addWidget(scroll, 1)
        self.pages.addWidget(page)

    def _make_detail(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 3, 4, 2)
        layout.setSpacing(6)
        top = QHBoxLayout()
        self.detail_title = QLabel()
        self.detail_title.setObjectName("guideTitle")
        self.detail_title.setWordWrap(True)
        top.addWidget(self.detail_title, 1)
        self.play_button = QPushButton("播放")
        self.play_button.setObjectName("guidePrimary")
        self.play_button.clicked.connect(lambda: self._play(False))
        top.addWidget(self.play_button)
        floating = QToolButton()
        floating.setText("更多")
        play_menu = QMenu(floating)
        play_menu.addAction("悬浮播放（置顶窗口）", lambda: self._play(True))
        play_menu.addAction("手机扫码查看原站", self._send_phone)
        floating.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        floating.setMenu(play_menu)
        top.addWidget(floating)
        layout.addLayout(top)
        self.detail_meta = QLabel()
        self.detail_meta.setObjectName("guideGold")
        self.detail_meta.setWordWrap(True)
        layout.addWidget(self.detail_meta)
        self.timeline = TimelineWidget()
        layout.addWidget(self.timeline)
        self.economy_toggle = QToolButton()
        self.economy_toggle.setText("经济分配")
        self.economy_toggle.setCheckable(True)
        self.economy_toggle.toggled.connect(self._toggle_economy)
        layout.addWidget(self.economy_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        self.economy = EconomyChart()
        self.economy.setVisible(False)
        layout.addWidget(self.economy)
        self.detail = GuideDetail(self.store)
        layout.addWidget(self.detail, 1)
        self.pages.addWidget(page)

    def _layout_civs(self, *_unused) -> None:
        if not hasattr(self, "civ_grid"):
            return
        while self.civ_grid.count():
            self.civ_grid.takeAt(0)
        query = self.civ_search.text().strip().casefold()
        visible = [card for card in self.civ_cards if query in card.name.casefold()]
        width = max(400, self.pages.width() - 30)
        columns = max(2, min(5, width // 180))
        for index, card in enumerate(visible):
            self.civ_grid.addWidget(card, index // columns, index % columns)
            card.show()
        for card in self.civ_cards:
            if card not in visible:
                card.hide()
        for column in range(columns):
            self.civ_grid.setColumnStretch(column, 1)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "civ_grid"):
            self._layout_civs()

    def _refresh_home(self) -> None:
        self._layout_civs()
        updated = self.data.get("synced_at")
        date = updated[:10] if isinstance(updated, str) else "尚未同步"
        label = "内置" if self.bundled else "本地已保存"
        self.home_count.setText(f"{label} {len(self.data['builds'])} 篇 · 资料日期 {date}")
        self.home_count.setToolTip("内置流程随开发者发布的新版本更新。" if self.bundled else
                                   "流程来自 AOE4 Guides；每文明公开列表最多提供 10 篇。资料仅手动更新。")

    def _show_home(self) -> None:
        self.pages.setCurrentIndex(0)
        self.bar_title.setText("文明与开局流程")
        self.back_button.setEnabled(False)
        self.source_action.setEnabled(False)

    def _show_civ(self, code: str) -> None:
        self.current_civ = code
        self.civ_filter.blockSignals(True)
        index = self.civ_filter.findData(code)
        self.civ_filter.setCurrentIndex(max(0, index))
        self.civ_filter.blockSignals(False)
        name = CIVILIZATIONS.get(code, "全部文明")
        flag = self.store.flag(code, large=True) if code else None
        self.civ_banner.set_civ(name, flag)
        self.pages.setCurrentIndex(1)
        self.bar_title.setText(name + " · 开局流程")
        self.back_button.setEnabled(True)
        self.source_action.setEnabled(False)
        self._refresh_filters()
        self._refresh_list()

    def _filter_civ_changed(self, *_unused) -> None:
        self.current_civ = self.civ_filter.currentData() or ""
        name = CIVILIZATIONS.get(self.current_civ, "全部文明")
        flag = self.store.flag(self.current_civ, large=True) if self.current_civ else None
        self.civ_banner.set_civ(name, flag)
        self.bar_title.setText(name + " · 开局流程")
        self._refresh_filters()
        self._refresh_list()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        for key, button in self.mode_buttons.items():
            button.setChecked(key == mode)
        self._refresh_list()

    def _toggle_filters(self, enabled: bool) -> None:
        self.filters.setVisible(enabled)
        self.filter_button.setText("收起筛选" if enabled else "筛选")

    def _toggle_economy(self, enabled: bool) -> None:
        self.economy.setVisible(enabled)
        self.economy_toggle.setText("收起经济分配" if enabled else "经济分配")

    def _refresh_filters(self) -> None:
        builds = [b for b in self.data["builds"] if not self.current_civ or b.get("civ") == self.current_civ]
        for combo, key, label in ((self.season, "season", "全部赛季"),
                                  (self.game_map, "map", "全部地图"),
                                  (self.strategy, "strategy", "全部战术")):
            previous = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(label, "")
            for value in sorted({str(b.get(key)) for b in builds if b.get(key)}):
                combo.addItem(value, value)
            combo.setCurrentIndex(max(0, combo.findData(previous)))
            combo.blockSignals(False)

    def _refresh_list(self, *_unused) -> None:
        if not hasattr(self, "cards_layout"):
            return
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        code = self.civ_filter.currentData() or ""
        query = self.build_search.text().strip().casefold()
        builds = []
        for build in self.data["builds"]:
            if code and build.get("civ") != code:
                continue
            labels = " ".join(PLAYSTYLE_LABELS.get(tag, "") for tag in build.get("curated_playstyles", []))
            searchable = " ".join((str(build.get("title") or ""), str(build.get("author") or ""),
                                   str(build.get("strategy") or ""), labels)).casefold()
            if query and query not in searchable:
                continue
            if any(combo.currentData() and build.get(key) != combo.currentData() for combo, key in (
                    (self.season, "season"), (self.game_map, "map"), (self.strategy, "strategy"))):
                continue
            builds.append(build)
        builds.sort(key=lambda b: float(b.get(self.mode) or 0) if self.mode != "timeCreated"
                    else _stamp(b.get("timeCreated")), reverse=True)
        for build in builds:
            card = GuideCard(build, self.store)
            card.clicked.connect(self._show_detail)
            self.cards_layout.addWidget(card)
        if not builds:
            message = ("内置资料中没有匹配的流程。" if self.bundled else
                       "本地没有匹配的流程。可在右上角“资料”中手动更新，或粘贴单篇链接导入。")
            empty = QLabel(message)
            empty.setWordWrap(True)
            empty.setObjectName("guideSmall")
            self.cards_layout.addWidget(empty)
        self.cards_layout.addStretch(1)
        # QScrollArea resizes its child to the viewport; without a minimum height,
        # Qt can overlap fixed-height cards instead of making the list scroll.
        self.cards_area.setMinimumHeight(len(builds) * 104 + max(0, len(builds) - 1) * 8 + 2)
        self.list_count.setText(f"{len(builds)} 篇流程")
        self.list_count.setToolTip("资料已随程序打包，更新请安装开发者发布的新版本。" if self.bundled else
                                   "资料保存在本机；公开 API 每文明最多提供 10 篇。")

    def _show_detail(self, build_id: str) -> None:
        build = next((b for b in self.data["builds"] if b.get("id") == build_id), None)
        if build is None:
            return
        self.current_id = build_id
        self.detail_title.setText(str(build.get("title") or "未命名流程"))
        civ = CIVILIZATIONS.get(build.get("civ"), str(build.get("civ") or ""))
        self.detail_meta.setText(
            f"{civ}   ·   作者 {build.get('author') or '未知'}   ·   {build.get('season') or '赛季未记录'}"
            f"   ·   {_age_times(build)}"
        )
        self.timeline.show_build(build)
        self.economy.show_build(build)
        self.detail.show_build(build)
        self.pages.setCurrentIndex(2)
        self.bar_title.setText("流程详情")
        self.back_button.setEnabled(True)
        self.source_action.setEnabled(True)

    def _back(self) -> None:
        if self.pages.currentIndex() == 2:
            self._show_civ(self.current_civ)
        else:
            self._show_home()

    def _play(self, floating: bool) -> None:
        build = next((b for b in self.data["builds"] if b.get("id") == self.current_id), None)
        if build is None:
            return
        dialog = FocusDialog(self.store, build, floating, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.focus_windows.append(dialog)
        dialog.destroyed.connect(lambda: self.focus_windows.remove(dialog) if dialog in self.focus_windows else None)
        dialog.show()

    def _send_phone(self) -> None:
        if not self.current_id:
            return
        import qrcode

        url = source_url(self.current_id)
        matrix = qrcode.QRCode(border=2)
        matrix.add_data(url)
        matrix.make(fit=True)
        dots = matrix.get_matrix()
        size = len(dots)
        tile = max(1, 240 // size)
        picture = QPixmap(size * tile, size * tile)
        picture.fill(QColor("#ffffff"))
        painter = QPainter(picture)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#182536"))
        for row, values in enumerate(dots):
            for column, filled in enumerate(values):
                if filled:
                    painter.drawRect(column * tile, row * tile, tile, tile)
        painter.end()
        dialog = QDialog(self)
        dialog.setWindowTitle("手机查看原站流程")
        dialog.setStyleSheet(GUIDE_STYLE)
        box = QVBoxLayout(dialog)
        note = QLabel("手机扫描二维码后，将在 AOE4 Guides 原站打开此篇流程。")
        note.setWordWrap(True)
        box.addWidget(note)
        image = QLabel()
        image.setPixmap(picture)
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(image)
        copy = QPushButton("复制流程链接")
        copy.clicked.connect(lambda: QApplication.clipboard().setText(url))
        box.addWidget(copy)
        dialog.exec()

    def _sync(self) -> None:
        self._start_worker("sync")

    def _import_link(self) -> None:
        url, accepted = QInputDialog.getText(
            self, "导入单篇流程", "粘贴 AOE4 Guides 流程页面链接："
        )
        if accepted and url.strip():
            self._start_worker("link", url.strip())

    def _import_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self, "选择站点提供的流程 JSON", "", "JSON 文件 (*.json)"
        )
        if filename:
            self._start_worker("file", filename)

    def _start_worker(self, operation: str, argument: str = "") -> None:
        if self.worker is not None:
            return
        self.worker = GuideWorker(self.store, operation, argument)
        self.worker.progress.connect(self.status.setText)
        self.worker.succeeded.connect(self._synced)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._worker_finished)
        for action in self.data_actions:
            action.setEnabled(False)
        self.status_timer.stop()
        self.status.setText("正在读取流程文字；原有本地资料保持不变…")
        self.status.show()
        self.worker.start()

    def _synced(self, count: int, _unused: int) -> None:
        self.data = self.store.load()
        self._refresh_home()
        self._refresh_filters()
        self._refresh_list()
        self.status.setText(f"已保存 {count} 篇流程到本机；下次打开不会自动联网。")
        self.status_timer.start(10000)
        if self.worker and self.worker.operation == "link":
            from .guide_data import build_id_from_url
            self._show_detail(build_id_from_url(self.worker.argument))

    def _failed(self, message: str) -> None:
        self.status.setText(message)
        self.status_timer.start(10000)
        QMessageBox.warning(self, "流程更新失败", message)

    def _worker_finished(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None
        for action in self.data_actions:
            action.setEnabled(True)

    def _open_source(self) -> None:
        if self.current_id:
            QDesktopServices.openUrl(QUrl(source_url(self.current_id)))

    def _show_attribution(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("素材与数据来源")
        dialog.setStyleSheet(GUIDE_STYLE)
        dialog.resize(440, 210)
        layout = QVBoxLayout(dialog)
        notice = QLabel(
            'Age of Empires IV © Microsoft Corporation. AOE4 Toolbox was created under '
            'Microsoft\'s <a href="https://www.xbox.com/en-US/developers/rules">Game Content Usage Rules</a> '
            'using assets from Age of Empires IV, and it is not endorsed by or affiliated with Microsoft.'
            '<br><br>游戏图片和图标目录来自 '
            '<a href="https://github.com/jensbuehl/aoe4-guides">AOE4 Guides</a>；'
            '流程文字来自该站的各位作者。此工具是免费的非官方阅读器。'
        )
        notice.setWordWrap(True)
        notice.setOpenExternalLinks(True)
        layout.addWidget(notice)
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()

    def shutdown(self) -> None:
        for dialog in list(self.focus_windows):
            dialog.close()
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
