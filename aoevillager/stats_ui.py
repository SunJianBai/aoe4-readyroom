"""Native Qt civilization statistics page backed by AoE4 World's public API."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (
    QAbstractTableModel, QModelIndex, QRect, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal,
)
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QFontMetrics, QIcon, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QStyle, QStyledItemDelegate, QTabWidget, QTableView, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from .guide_data import CIVILIZATIONS
from .stats_data import (
    RATINGS, RANK_LEVELS, WORLD_TO_CODE, StatsError, StatsFilter, StatsStore,
    fetch_snapshot, is_fresh, overall_excluding_mirrors, source_url,
)


STATS_STYLE = """
QWidget#statsRoot { background:#1d2432; color:#e9ebee; }
QFrame#statsPanel { background:#324156; border:1px solid #52627a; border-radius:8px; }
QFrame#statsDetail { background:#253950; border:1px solid #8f794e; border-radius:7px; }
QLabel#statsMuted { color:#bfcbda; font-size:10px; }
QLabel#statsValue { color:#f5dfa9; font-size:11px; font-weight:700; }
QComboBox { background:#233449; color:#f4e3bd; border:1px solid #8a7758;
  border-radius:5px; min-height:23px; padding:2px 6px; }
QComboBox QAbstractItemView { background:#26394d; color:#f4e3bd;
  selection-background-color:#826a45; }
QPushButton#statsAction { background:#3b5169; color:#f5e2b0;
  border:1px solid #a08859; border-radius:5px; min-height:23px; padding:2px 8px; }
QPushButton#statsAction:hover { background:#4b6480; border-color:#e7c05e; }
QPushButton#statsAction:disabled { color:#8793a2; border-color:#536072; }
QPushButton#statsMiniAction { background:#3b5169; color:#f5e2b0;
  border:1px solid #a08859; border-radius:4px; min-height:20px;
  padding:1px 6px; font-size:10px; }
QPushButton#statsMiniAction:hover { background:#4b6480; border-color:#e7c05e; }
QPushButton#statsMiniAction:disabled { color:#8793a2; border-color:#536072; }
QTabWidget::pane { border:1px solid #4b5d75; border-radius:5px; background:#202d3e; }
QTabBar::tab { background:#324156; color:#dbe2e9; padding:4px 10px;
  border:1px solid #4b5d75; min-width:72px; }
QTabBar::tab:selected { background:#d8b667; color:#14243a; font-weight:700; }
QTableView, QTableWidget { background:#101b2a; alternate-background-color:#1c2b3d;
  color:#e7e9ec; gridline-color:#28374a; border:0; selection-background-color:#38546b; }
QHeaderView::section { background:#26384e; color:#f2d187; border:1px solid #435670;
  padding:2px; font-weight:600; }
QTableCornerButton::section { background:#26384e; border:1px solid #435670; }
QToolTip { background:#173047; color:#f5dfa9; border:1px solid #c5a466; }
"""


def _name(slug: str) -> str:
    code = WORLD_TO_CODE.get(slug)
    return CIVILIZATIONS.get(code, slug.replace("_", " ").title())


def _percent(value: object) -> str:
    return f"{float(value):.1f}%" if isinstance(value, (int, float)) else "—"


class _NumberItem(QTableWidgetItem):
    def __init__(self, text: str, number: float) -> None:
        super().__init__(text)
        self.setData(Qt.ItemDataRole.UserRole, number)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        return float(self.data(Qt.ItemDataRole.UserRole) or 0) < float(
            other.data(Qt.ItemDataRole.UserRole) or 0
        )


class MatchupModel(QAbstractTableModel):
    """One 23x24 model instead of a QWidget for every heatmap cell."""

    def __init__(self, flags: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.flags = flags
        self.slugs: list[str] = []
        self.cells: dict[tuple[str, str], dict] = {}
        self.totals: dict[str, tuple[float, int]] = {}
        self._icons: dict[str, QIcon] = {}

    def set_snapshot(self, snapshot: dict | None) -> None:
        self.beginResetModel()
        self.slugs = []
        self.cells = {}
        self.totals = {}
        if snapshot:
            self.cells = {
                (row["civilization"], row["other_civilization"]): row
                for row in snapshot["matchups"]
            }
            for row in snapshot["civilizations"]:
                slug = row["civilization"]
                total = overall_excluding_mirrors(snapshot["matchups"], slug)
                self.totals[slug] = total or (float(row["win_rate"]), int(row["games_count"]))
                self.slugs.append(slug)
            self.slugs.sort(key=lambda slug: (-self.totals[slug][0],
                                             -self.totals[slug][1], _name(slug)))
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.slugs)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.slugs) + 1

    def row_slug(self, row: int) -> str:
        return self.slugs[row]

    def opponent_slug(self, column: int) -> str:
        return self.slugs[column - 1] if column else ""

    def cell(self, index: QModelIndex) -> tuple[float, int, bool] | None:
        if not index.isValid() or not 0 <= index.row() < len(self.slugs):
            return None
        civ = self.slugs[index.row()]
        if index.column() == 0:
            rate, games = self.totals[civ]
            return rate, games, False
        opponent = self.slugs[index.column() - 1]
        item = self.cells.get((civ, opponent))
        if not item:
            return None
        return float(item["win_rate"]), int(item["games_count"]), civ == opponent

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        value = self.cell(index)
        if value is None:
            return None
        rate, games, mirror = value
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{rate:.1f}%\n{games:,}"
        if role == Qt.ItemDataRole.ToolTipRole:
            civ = self.slugs[index.row()]
            opponent = self.opponent_slug(index.column())
            title = f"{_name(civ)}总体（不含镜像）" if not opponent else f"{_name(civ)} 对 {_name(opponent)}"
            warning = "\n样本较少，请谨慎解读" if games < 100 and not mirror else ""
            return f"{title}\n胜率 {rate:.1f}% · {games:,} 场{warning}"
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        return None

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal:
            if section == 0:
                if role == Qt.ItemDataRole.DisplayRole:
                    return "总体"
                if role == Qt.ItemDataRole.ToolTipRole:
                    return "总体胜率（不含镜像对局）"
                return None
            slug = self.slugs[section - 1] if section <= len(self.slugs) else ""
        else:
            slug = self.slugs[section] if section < len(self.slugs) else ""
        if not slug:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return ""
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ToolTipRole:
            return _name(slug)
        if role == Qt.ItemDataRole.DecorationRole:
            code = WORLD_TO_CODE.get(slug)
            if code:
                if code not in self._icons:
                    self._icons[code] = QIcon(str(self.flags / f"{code.lower()}-small.webp"))
                return self._icons[code].pixmap(QSize(32, 22))
        return None


class FlagHeader(QHeaderView):
    """Center flag-only headings while keeping full names in header tooltips."""

    def paintSection(self, painter: QPainter, rect: QRect, logical_index: int) -> None:  # noqa: N802
        flag = self.model().headerData(
            logical_index, self.orientation(), Qt.ItemDataRole.DecorationRole
        )
        painter.save()
        painter.fillRect(rect, QColor("#26384e"))
        painter.setPen(QColor("#435670"))
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        if flag is not None and not flag.isNull():
            available = rect.size() - QSize(4, 3)
            scaled = flag.scaled(available, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(
                rect.left() + (rect.width() - scaled.width()) // 2,
                rect.top() + (rect.height() - scaled.height()) // 2,
                scaled,
            )
        elif self.orientation() == Qt.Orientation.Horizontal and logical_index == 0:
            font = QFont(painter.font())
            font.setBold(True)
            font.setPixelSize(min(12, max(8, rect.width() // 3)))
            painter.setFont(font)
            painter.setPen(QColor("#f2d187"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "总体")
        painter.restore()


class MatchupTableView(QTableView):
    """Fit the entire matrix by default; Ctrl+wheel opts into scrollable zoom."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.zoom_factor = 1.0
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self.fit_grid)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def schedule_fit(self) -> None:
        self._fit_timer.start(0)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.schedule_fit()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.schedule_fit()

    def wheelEvent(self, event) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta:
                self.set_zoom(self.zoom_factor * (1.15 if delta > 0 else 1 / 1.15))
            event.accept()
            return
        super().wheelEvent(event)

    def set_zoom(self, value: float) -> None:
        self.zoom_factor = 1.0 if value <= 1.03 else min(3.0, value)
        policy = (Qt.ScrollBarPolicy.ScrollBarAlwaysOff if self.zoom_factor == 1.0
                  else Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)
        if self.zoom_factor == 1.0:
            self.horizontalScrollBar().setValue(0)
            self.verticalScrollBar().setValue(0)
        self.schedule_fit()

    def fit_grid(self) -> None:
        model = self.model()
        if model is None or not model.rowCount():
            return
        columns, rows = model.columnCount(), model.rowCount()
        self.verticalHeader().setFixedWidth(max(24, min(42, self.width() // 30)))
        self.horizontalHeader().setFixedHeight(max(20, min(30, self.height() // 25)))
        # Qt can finalize header geometry a few pixels after a resize event.
        # Keep a small safety margin so the last row/column never gets clipped.
        width = max(1, self.viewport().width() - 8)
        height = max(1, self.viewport().height() - 8)
        if self.zoom_factor == 1.0:
            cell_width, extra_columns = divmod(width, columns)
            cell_height, extra_rows = divmod(height, rows)
            for column in range(columns):
                self.setColumnWidth(column, cell_width + (column < extra_columns))
            for row in range(rows):
                self.setRowHeight(row, cell_height + (row < extra_rows))
        else:
            cell_width = max(18, round(width / columns * self.zoom_factor))
            cell_height = max(12, round(height / rows * self.zoom_factor))
            for column in range(columns):
                self.setColumnWidth(column, cell_width)
            for row in range(rows):
                self.setRowHeight(row, cell_height)


class MatchupDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        cell = index.model().cell(index)
        if cell is None:
            painter.fillRect(option.rect, QColor("#182537"))
            return
        rate, games, mirror = cell
        low_sample = games < 100
        if mirror:
            background, foreground, secondary = "#222b39", "#9ba6b3", "#778392"
        elif rate >= 50:
            background, foreground, secondary = "#153d30", "#5be1a0", "#99bbab"
        else:
            background, foreground, secondary = "#462b32", "#ff8a83", "#b99a9e"
        painter.save()
        rect = option.rect.adjusted(1, 1, -1, -1)
        painter.fillRect(rect, QColor(background))
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(QColor("#e7c05e"))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
        if low_sample and not mirror:
            foreground, secondary = "#d9c6a9", "#a79783"
        show_games = rect.height() >= 16 and rect.width() >= 28
        rate_text = f"{rate:.1f}%"
        games_text = f"{games:,}"
        font = QFont(option.font)
        font.setBold(True)
        top_height = max(1, round(rect.height() * 0.56)) if show_games else rect.height()
        font.setPixelSize(max(6, min(15, top_height - 1, rect.width() // 4)))
        while font.pixelSize() > 5 and QFontMetrics(font).horizontalAdvance(rate_text) > rect.width() - 2:
            font.setPixelSize(font.pixelSize() - 1)
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        painter.drawText(QRect(rect.left(), rect.top(), rect.width(), top_height),
                         Qt.AlignmentFlag.AlignCenter, rate_text)
        if show_games:
            font.setBold(False)
            font.setPixelSize(max(5, min(11, rect.height() - top_height - 1,
                                         rect.width() // 5)))
            while font.pixelSize() > 5 and QFontMetrics(font).horizontalAdvance(games_text) > rect.width() - 2:
                font.setPixelSize(font.pixelSize() - 1)
            painter.setFont(font)
            painter.setPen(QColor(secondary))
            painter.drawText(QRect(rect.left(), rect.top() + top_height,
                                   rect.width(), rect.height() - top_height),
                             Qt.AlignmentFlag.AlignCenter, games_text)
        painter.restore()


class StatsWorker(QThread):
    result_ready = pyqtSignal(object, object, str)

    def __init__(self, store: StatsStore, filters: StatsFilter, parent: QWidget) -> None:
        super().__init__(parent)
        self.store, self.filters = store, filters

    def run(self) -> None:
        try:
            snapshot = fetch_snapshot(self.filters)
            self.store.save(self.filters, snapshot)
            self.result_ready.emit(self.filters, snapshot, "")
        except (StatsError, OSError, ValueError) as exc:
            self.result_ready.emit(self.filters, None, str(exc))


class StatsPage(QWidget):
    guide_requested = pyqtSignal(str)

    def __init__(self, cache_folder: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("statsRoot")
        self.setStyleSheet(STATS_STYLE)
        self.store = StatsStore(cache_folder)
        self.flags = (Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
                      / "assets" / "guides" / "flags")
        self.snapshot: dict | None = None
        self.current_filter = StatsFilter()
        self.worker: StatsWorker | None = None
        self.queued = False
        self.selected_civ = ""
        self.selected_opponent = ""
        self.initialized = False
        self._build_ui()
        self.debounce = QTimer(self)
        self.debounce.setSingleShot(True)
        self.debounce.setInterval(350)
        self.debounce.timeout.connect(self._load_or_fetch)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 3, 4, 3)
        root.setSpacing(5)

        controls = QFrame()
        controls.setObjectName("statsPanel")
        filter_row = QHBoxLayout(controls)
        filter_row.setContentsMargins(8, 4, 8, 4)
        filter_row.setSpacing(5)
        self.patch_combo = self._combo([("当前补丁范围", ""), ("全部补丁", "any")])
        self.rank_combo = self._combo(RANK_LEVELS)
        self.rating_combo = self._combo(RATINGS)
        for label, combo in (("补丁", self.patch_combo), ("段位", self.rank_combo),
                             ("分数", self.rating_combo)):
            filter_row.addWidget(QLabel(label))
            filter_row.addWidget(combo, 1)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setObjectName("statsAction")
        self.refresh_button.setToolTip("重新获取当前筛选条件的公开统计")
        self.refresh_button.clicked.connect(lambda: self._load_or_fetch(force=True))
        filter_row.addWidget(self.refresh_button)
        self.patch_combo.currentIndexChanged.connect(self._filter_changed)
        self.rank_combo.currentIndexChanged.connect(self._rank_changed)
        self.rating_combo.currentIndexChanged.connect(self._rating_changed)
        root.addWidget(controls)

        self.tabs = QTabWidget()
        self.matrix_model = MatchupModel(self.flags, self)
        self.matrix = MatchupTableView()
        self.matrix.setModel(self.matrix_model)
        self.matrix.setHorizontalHeader(FlagHeader(Qt.Orientation.Horizontal, self.matrix))
        self.matrix.setVerticalHeader(FlagHeader(Qt.Orientation.Vertical, self.matrix))
        self.matrix.setItemDelegate(MatchupDelegate(self.matrix))
        self.matrix.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.matrix.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.matrix.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.matrix.verticalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        self.matrix.verticalHeader().setMinimumSectionSize(1)
        self.matrix.horizontalHeader().setMinimumSectionSize(1)
        self.matrix.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.matrix.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.matrix.setWordWrap(False)
        self.matrix.clicked.connect(self._matrix_clicked)
        self.tabs.addTab(self.matrix, "对阵热力图")

        self.overview = QTableWidget(0, 5)
        self.overview.setHorizontalHeaderLabels(("文明", "胜率", "选择率", "场次", "对局中位时长"))
        self.overview.horizontalHeaderItem(1).setToolTip("总体胜率（不含镜像），按此列从高到低排序")
        self.overview.horizontalHeaderItem(3).setToolTip("不含镜像的对阵场次")
        self.overview.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.overview.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.overview.setIconSize(QSize(30, 20))
        self.overview.verticalHeader().setDefaultSectionSize(30)
        self.overview.verticalHeader().setVisible(False)
        self.overview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.overview.setColumnWidth(0, 64)
        self.overview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.overview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.overview.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.overview.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.overview.cellClicked.connect(self._overview_clicked)
        self.tabs.addTab(self.overview, "文明总览")

        focused = QWidget()
        focused_layout = QVBoxLayout(focused)
        focused_row = QHBoxLayout()
        focused_row.addWidget(QLabel("我方文明"))
        self.civ_combo = self._combo([])
        self.civ_combo.currentIndexChanged.connect(self._focused_changed)
        focused_row.addWidget(self.civ_combo, 1)
        focused_layout.addLayout(focused_row)
        self.focused_table = QTableWidget(0, 3)
        self.focused_table.setHorizontalHeaderLabels(("对手文明", "我方胜率", "场次"))
        self.focused_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.focused_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.focused_table.setIconSize(QSize(30, 20))
        self.focused_table.verticalHeader().setDefaultSectionSize(30)
        self.focused_table.verticalHeader().setVisible(False)
        self.focused_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.focused_table.setColumnWidth(0, 88)
        self.focused_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.focused_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.focused_table.cellClicked.connect(self._focused_clicked)
        focused_layout.addWidget(self.focused_table, 1)
        self.tabs.addTab(focused, "单文明对阵")
        root.addWidget(self.tabs, 1)

        detail = QFrame()
        detail.setObjectName("statsDetail")
        detail_row = QHBoxLayout(detail)
        detail_row.setContentsMargins(8, 2, 8, 2)
        detail_row.setSpacing(5)
        self.detail_text = QLabel("点击国旗或对阵格查看统计")
        self.detail_text.setObjectName("statsValue")
        self.detail_text.setWordWrap(False)
        self.detail_text.setMinimumWidth(0)
        detail_row.addWidget(self.detail_text, 1)
        self.guides_button = QPushButton("开局流程")
        self.guides_button.setObjectName("statsMiniAction")
        self.guides_button.setToolTip("查看当前文明的开局流程")
        self.guides_button.setEnabled(False)
        self.guides_button.clicked.connect(self._open_guides)
        detail_row.addWidget(self.guides_button)
        source_button = QPushButton("原站详情")
        source_button.setObjectName("statsMiniAction")
        source_button.setToolTip("在 AOE4 World 查看当前对阵")
        source_button.clicked.connect(self._open_source)
        detail_row.addWidget(source_button)
        root.addWidget(detail)
        self.status = QLabel("数据来源：AOE4 World · 首次打开将读取公开统计。")
        self.status.setObjectName("statsMuted")
        self.status.setWordWrap(False)
        self.status.setFixedHeight(16)
        self.status.setToolTip(self.status.text())
        root.addWidget(self.status)

    def _set_status(self, message: str) -> None:
        self.status.setText(message)
        self.status.setToolTip(message)

    def _set_detail(self, message: str, full_message: str | None = None) -> None:
        self.detail_text.setText(message)
        self.detail_text.setToolTip(full_message or message)

    @staticmethod
    def _combo(items) -> QComboBox:
        combo = QComboBox()
        for label, value in items:
            combo.addItem(label, value)
        return combo

    def activate(self) -> None:
        if not self.initialized:
            self.initialized = True
            QTimer.singleShot(0, self._load_or_fetch)

    def _filters(self) -> StatsFilter:
        return StatsFilter(str(self.patch_combo.currentData() or ""),
                           str(self.rank_combo.currentData() or ""),
                           str(self.rating_combo.currentData() or ""))

    def _filter_changed(self) -> None:
        self.debounce.start()

    def _rank_changed(self) -> None:
        if self.rank_combo.currentData() and self.rating_combo.currentIndex() != 0:
            self.rating_combo.blockSignals(True)
            self.rating_combo.setCurrentIndex(0)
            self.rating_combo.blockSignals(False)
        self._filter_changed()

    def _rating_changed(self) -> None:
        if self.rating_combo.currentData() and self.rank_combo.currentIndex() != 0:
            self.rank_combo.blockSignals(True)
            self.rank_combo.setCurrentIndex(0)
            self.rank_combo.blockSignals(False)
        self._filter_changed()

    def _load_or_fetch(self, force: bool = False) -> None:
        filters = self._filters()
        self.current_filter = filters
        try:
            cached = self.store.load(filters)
        except StatsError as exc:
            cached = None
            self._set_status(str(exc))
        if cached:
            self._display(cached, stale=not is_fresh(cached))
        else:
            self._display(None)
        if cached and is_fresh(cached) and not force:
            return
        if self.worker and self.worker.isRunning():
            self.queued = True
            return
        self._start_worker(filters)

    def _start_worker(self, filters: StatsFilter) -> None:
        self._set_status("正在读取 AOE4 World 公开统计；旧缓存会保留到新数据完整返回…")
        self.refresh_button.setEnabled(False)
        self.worker = StatsWorker(self.store, filters, self)
        self.worker.result_ready.connect(self._result_ready)
        self.worker.finished.connect(self._worker_finished)
        self.worker.start()

    def _result_ready(self, filters: StatsFilter, snapshot: dict | None, error: str) -> None:
        if filters != self._filters():
            return
        if snapshot:
            self._display(snapshot)
        else:
            if self.snapshot:
                fetched = datetime.fromisoformat(self.snapshot["fetched_at"]).astimezone().strftime("%Y-%m-%d %H:%M")
                self._set_status(
                    f"刷新失败：{error}。仍显示 {fetched} 抓取的本地缓存，数据可能已过时。"
                )
            else:
                self._set_status(f"刷新失败：{error}。当前筛选无本地缓存。")

    def _worker_finished(self) -> None:
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        self.refresh_button.setEnabled(True)
        if self.queued:
            self.queued = False
            self._load_or_fetch()

    def _patch_options(self, patch_value: str) -> None:
        current = self.patch_combo.currentData()
        known = {self.patch_combo.itemData(i) for i in range(self.patch_combo.count())}
        patches = [item.strip() for item in patch_value.split(",") if item.strip().isdecimal()]
        self.patch_combo.blockSignals(True)
        for patch in patches:
            if patch not in known:
                self.patch_combo.addItem(f"补丁 {patch}", patch)
                known.add(patch)
        selected = self.patch_combo.findData(current)
        if selected >= 0:
            self.patch_combo.setCurrentIndex(selected)
        self.patch_combo.blockSignals(False)

    def _display(self, snapshot: dict | None, stale: bool = False) -> None:
        self.snapshot = snapshot
        self.matrix_model.set_snapshot(snapshot)
        self.matrix.schedule_fit()
        self.overview.setRowCount(0)
        self.focused_table.setRowCount(0)
        if not snapshot:
            self.civ_combo.blockSignals(True)
            self.civ_combo.clear()
            self.civ_combo.blockSignals(False)
            self.selected_civ = ""
            self.selected_opponent = ""
            self._set_detail("当前筛选暂无本地数据，正在等待统计接口。")
            self.guides_button.setEnabled(False)
            return
        self._patch_options(snapshot.get("patch", ""))
        self._fill_overview(snapshot)
        previous = self.civ_combo.currentData()
        self.civ_combo.blockSignals(True)
        self.civ_combo.clear()
        for slug in self.matrix_model.slugs:
            self.civ_combo.addItem(_name(slug), slug)
        chosen = self.civ_combo.findData(previous or self.selected_civ)
        self.civ_combo.setCurrentIndex(max(0, chosen))
        self.civ_combo.blockSignals(False)
        self._fill_focused()
        self._show_selection()
        fetched = datetime.fromisoformat(snapshot["fetched_at"]).astimezone().strftime("%Y-%m-%d %H:%M")
        marker = " · 离线历史缓存" if stale else ""
        self._set_status(
            f"来源 AOE4 World · 排位单挑 · 补丁 {snapshot.get('patch') or '未标明'}"
            f" · 本机抓取 {fetched}{marker} · 低于 100 场的格子已弱化显示"
        )

    def _fill_overview(self, snapshot: dict) -> None:
        by_slug = {row["civilization"]: row for row in snapshot["civilizations"]}
        self.overview.setRowCount(len(self.matrix_model.slugs))
        for position, slug in enumerate(self.matrix_model.slugs):
            row = by_slug[slug]
            name = QTableWidgetItem("")
            name.setData(Qt.ItemDataRole.UserRole, slug)
            name.setToolTip(_name(slug))
            name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code = WORLD_TO_CODE.get(slug)
            if code:
                name.setIcon(QIcon(str(self.flags / f"{code.lower()}-small.webp")))
            self.overview.setItem(position, 0, name)
            rate, games = self.matrix_model.totals[slug]
            pick = float(row.get("pick_rate") or 0)
            duration = round(float(row.get("duration_median") or 0) / 60, 1)
            for column, item in enumerate((
                _NumberItem(f"{rate:.1f}%", rate),
                _NumberItem(f"{pick:.1f}%", pick),
                _NumberItem(f"{games:,}", games),
                _NumberItem(f"{duration:.1f} 分钟", duration),
            ), start=1):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.overview.setItem(position, column, item)

    def _fill_focused(self) -> None:
        slug = self.civ_combo.currentData()
        if not slug or not self.snapshot:
            return
        rows = [self.matrix_model.cells[(slug, other)] for other in self.matrix_model.slugs
                if other != slug and (slug, other) in self.matrix_model.cells]
        rows.sort(key=lambda row: row["win_rate"], reverse=True)
        self.focused_table.setRowCount(len(rows))
        for position, row in enumerate(rows):
            opponent = row["other_civilization"]
            name = QTableWidgetItem("")
            name.setData(Qt.ItemDataRole.UserRole, opponent)
            name.setToolTip(_name(opponent))
            name.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            code = WORLD_TO_CODE.get(opponent)
            if code:
                name.setIcon(QIcon(str(self.flags / f"{code.lower()}-small.webp")))
            self.focused_table.setItem(position, 0, name)
            rate = float(row["win_rate"])
            games = int(row["games_count"])
            rate_item = _NumberItem(f"{rate:.1f}%", rate)
            games_item = _NumberItem(f"{games:,}", games)
            for column, item in ((1, rate_item), (2, games_item)):
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.focused_table.setItem(position, column, item)

    def _matrix_clicked(self, index: QModelIndex) -> None:
        self.selected_civ = self.matrix_model.row_slug(index.row())
        self.selected_opponent = self.matrix_model.opponent_slug(index.column())
        self._show_selection()

    def _overview_clicked(self, row: int, _column: int) -> None:
        item = self.overview.item(row, 0)
        if item:
            self.selected_civ = item.data(Qt.ItemDataRole.UserRole)
            self.selected_opponent = ""
            self._show_selection()

    def _focused_changed(self) -> None:
        self.selected_civ = str(self.civ_combo.currentData() or "")
        self.selected_opponent = ""
        self._fill_focused()
        self._show_selection()

    def _focused_clicked(self, row: int, _column: int) -> None:
        item = self.focused_table.item(row, 0)
        if item:
            self.selected_civ = str(self.civ_combo.currentData() or "")
            self.selected_opponent = item.data(Qt.ItemDataRole.UserRole)
            self._show_selection()

    def _show_selection(self) -> None:
        slug = self.selected_civ
        if slug not in self.matrix_model.totals and self.matrix_model.slugs:
            slug = self.matrix_model.slugs[0]
            self.selected_civ = slug
            self.selected_opponent = ""
        if self.selected_opponent and (slug, self.selected_opponent) not in self.matrix_model.cells:
            self.selected_opponent = ""
        self.guides_button.setEnabled(bool(WORLD_TO_CODE.get(slug)))
        if not slug or not self.snapshot:
            self._set_detail("点击国旗或对阵格查看统计")
            return
        if self.selected_opponent:
            row = self.matrix_model.cells.get((slug, self.selected_opponent))
            if row:
                games = int(row["games_count"])
                note = " · 样本较少" if games < 100 else ""
                self._set_detail(
                    f"{_name(slug)} vs {_name(self.selected_opponent)} · "
                    f"{_percent(row['win_rate'])} · {games:,} 场{note}",
                    f"{_name(slug)} 对 {_name(self.selected_opponent)}："
                    f"我方胜率 {_percent(row['win_rate'])}，共 {games:,} 场{note}"
                )
                return
        rate, games = self.matrix_model.totals[slug]
        self._set_detail(
            f"{_name(slug)} · 总体 {_percent(rate)} · {games:,} 场",
            f"{_name(slug)} 总体胜率（不含镜像） {_percent(rate)} · {games:,} 场",
        )

    def _open_guides(self) -> None:
        code = WORLD_TO_CODE.get(self.selected_civ)
        if code:
            self.guide_requested.emit(code)

    def _open_source(self) -> None:
        QDesktopServices.openUrl(QUrl(source_url(
            self._filters(), self.selected_civ, self.selected_opponent
        )))

    def shutdown(self) -> None:
        self.debounce.stop()
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.worker.wait()
