"""Native, offline AOE4 building-shortcut practice page."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .guide_data import CIVILIZATIONS
from .guide_ui import CivCard
from .practice_catalog import AGE_NAMES, Building, PracticeCatalog
from .widgets import NoWheelComboBox, NoWheelSpinBox


PRACTICE_STYLE = """
QWidget#practiceRoot, QWidget#practiceWorkspace, QWidget#civPicker, QWidget#civGridContent { background: #1d2432; color: #edf1f4; font-family: 'Microsoft YaHei UI'; }
QWidget#practiceBuildingContent { background: #324156; }
QFrame#practiceCard, QFrame#practiceHeader, QFrame#civHero {
  background: #324156; border: 1px solid #50627a; border-radius: 8px;
}
QFrame#practiceHeader, QFrame#civHero {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #354960,stop:1 #26374b);
  border-color: #9a7d4a;
}
QFrame#practiceTarget { background: #273b51; border: 1px solid #ba9453; border-radius: 8px; }
QLabel { color: #edf1f4; background: transparent; }
QLabel#practiceTitle { color: #f6d987; font-size: 16px; font-weight: 700; }
QLabel#practiceSectionTitle { color: #f6d987; font-size: 15px; font-weight: 700; }
QLabel#pickerTitle { color: #f6d987; font-size: 25px; font-weight: 700; }
QLabel#practiceMuted { color: #c5d0dd; font-size: 12px; }
QLabel#practiceBuilding { color: #fff0c1; font-size: 21px; font-weight: 700; }
QLabel#practiceKey { color: #e8c36e; font-size: 14px; font-weight: 700; }
QLabel#practiceStat { color: #f2d28e; background: #273b51; border: 1px solid #516078;
  border-radius: 5px; padding: 3px 8px; font-size: 12px; font-weight: 700; }
QLineEdit, QComboBox, QSpinBox, QTreeWidget {
  background: #202f42; color: #f5e5bf; border: 1px solid #7f755c;
  border-radius: 6px; padding: 7px 10px; min-height: 30px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTreeWidget:focus { border: 2px solid #f5d995; }
QComboBox QAbstractItemView { background: #26394d; color: #f5e5bf; selection-background-color: #50637c; }
QPushButton { background: #3b5169; color: #f5e2b0; border: 1px solid #8c7853;
  border-radius: 6px; padding: 7px 14px; min-height: 30px; font-weight: 600; }
QPushButton:hover { background: #4b6480; border-color: #e8c36e; }
QPushButton:pressed { background: #2e4056; }
QPushButton:checked { background: #e0bd72; color: #17283b; border-color: #f4da9a; }
QPushButton#practicePrimary { background: #e0bd72; color: #17283b; border-color: #f4da9a; }
QPushButton#practicePrimary:hover { background: #f2d68f; }
QPushButton#practiceMode, QPushButton#practicePrimary, QPushButton#practiceAction,
QPushButton#practiceCivSwitch { padding: 4px 11px; min-height: 28px; }
QPushButton#practiceAgeAction { padding: 3px 9px; min-height: 24px; }
QPushButton#civCard { padding: 0; min-height: 132px; max-height: 132px;
  border: none; background: transparent; }
QPushButton:disabled { color: #8591a0; background: #2c3948; border-color: #4d5661; }
QPushButton:focus, QToolButton:focus, QCheckBox:focus { border: 2px solid #fff0bc; }
QCheckBox { color: #edf1f4; spacing: 8px; padding: 5px; min-height: 35px; }
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 3px; }
QCheckBox::indicator:unchecked { background: #f0f2f5; border: 1px solid #aab7c4; }
QCheckBox::indicator:checked { background: #e0bd72; border: 3px solid #f6e5b7; }
QCheckBox:hover { background: #3a516b; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #263445; width: 9px; }
QScrollBar::handle:vertical { background: #a1885b; border-radius: 4px; min-height: 22px; }
QTreeWidget::item { min-height: 29px; }
QTreeWidget::item:selected { background: #586d88; color: #fff2cf; }
"""


def styled_frame(name: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName(name)
    return frame


def styled_label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


class HotkeyPracticePage(QWidget):
    def __init__(self, asset_dir: Path) -> None:
        super().__init__()
        self._asset_dir = asset_dir
        self.catalog = PracticeCatalog(asset_dir)
        self.setObjectName("practiceRoot")
        self.setAccessibleName("帝国时代 4 快捷键练习")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet(PRACTICE_STYLE)
        self._mode = "learn"
        self._state = "idle"
        self._available: tuple[Building, ...] = ()
        self._checks: dict[str, QCheckBox] = {}
        self._target: Building | None = None
        self._first_key = self._revealed = False
        self._consecutive_errors = 0
        self._correct = self._wrong = self._elapsed = self._progress = self._total = 0
        self._sessions: list[dict] = []
        self._active_session: dict | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._build()
        QApplication.instance().installEventFilter(self)
        self._set_civilization()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.page_stack = QStackedWidget()
        root.addWidget(self.page_stack)
        self._build_civilization_picker()

        workspace = QWidget()
        workspace.setObjectName("practiceWorkspace")
        outer = QVBoxLayout(workspace)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(7)
        header = styled_frame("practiceHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(13, 6, 13, 6)
        row.addWidget(styled_label("建筑快捷键练习", "practiceTitle"))
        row.addStretch()
        self.civ_combo = NoWheelComboBox(workspace)
        self.civ_combo.setAccessibleName("选择练习文明")
        self.civ_combo.addItem("请选择文明", None)
        for civ in self.catalog.civilizations:
            self.civ_combo.addItem(QIcon(str(civ.icon)), civ.name, civ.id)
        self.civ_combo.currentIndexChanged.connect(lambda _index: self._set_civilization())
        self.civ_combo.hide()
        self.civ_button = QPushButton("更换文明")
        self.civ_button.setObjectName("practiceCivSwitch")
        self.civ_button.setAccessibleName("返回文明选择页面")
        self.civ_button.clicked.connect(self._show_civilization_picker)
        row.addWidget(self.civ_button)
        outer.addWidget(header)

        modes = QHBoxLayout()
        modes.setSpacing(7)
        self.mode_buttons = {}
        for value, label in (("learn", "学习模式"), ("train", "训练模式"), ("wrong", "错题本")):
            button = QPushButton(label)
            button.setObjectName("practiceMode")
            button.setCheckable(True)
            button.setChecked(value == "learn")
            button.clicked.connect(lambda checked=False, mode=value: self._select_mode(mode))
            modes.addWidget(button)
            self.mode_buttons[value] = button
        mode_card = styled_frame("practiceCard")
        mode_card.setLayout(modes)
        modes.setContentsMargins(6, 4, 6, 4)
        outer.addWidget(mode_card)

        self.views = QStackedWidget()
        practice = QWidget()
        practice_layout = QVBoxLayout(practice)
        practice_layout.setContentsMargins(0, 0, 0, 0)
        practice_layout.setSpacing(6)
        controls = styled_frame("practiceCard")
        row = QHBoxLayout(controls)
        row.setContentsMargins(9, 4, 9, 4)
        self.start_button = QPushButton("开始练习")
        self.start_button.setObjectName("practicePrimary")
        self.start_button.setAccessibleName("开始或继续快捷键练习")
        self.pause_button = QPushButton("暂停")
        self.reset_button = QPushButton("重置")
        self.pause_button.setObjectName("practiceAction")
        self.reset_button.setObjectName("practiceAction")
        self.start_button.clicked.connect(self._start)
        self.pause_button.clicked.connect(self.pause)
        self.reset_button.clicked.connect(self._reset)
        for button in (self.start_button, self.pause_button, self.reset_button):
            row.addWidget(button)
        row.addStretch()
        row.addWidget(QLabel("练习次数"))
        self.count_spin = NoWheelSpinBox()
        self.count_spin.setRange(1, 100)
        self.count_spin.setValue(10)
        self.count_spin.setAccessibleName("练习次数")
        self.count_spin.setFixedWidth(80)
        row.addWidget(self.count_spin)
        practice_layout.addWidget(controls)

        target = styled_frame("practiceTarget")
        row = QHBoxLayout(target)
        row.setContentsMargins(12, 6, 12, 6)
        row.setSpacing(12)
        self.target_icon = QLabel()
        self.target_icon.setFixedSize(70, 70)
        self.target_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.target_icon)
        self.target_icon.hide()
        copy = QVBoxLayout()
        copy.setSpacing(2)
        self.target_caption = styled_label("选择文明和建筑，点击开始练习", "practiceMuted")
        self.target_name = styled_label("等待开始", "practiceBuilding")
        self.target_key = styled_label("按时代键 → 建筑键", "practiceKey")
        self.feedback = QLabel("")
        self.feedback.setAccessibleName("按键反馈")
        self.feedback.setWordWrap(True)
        for label in (self.target_caption, self.target_name):
            copy.addWidget(label)
        row.addLayout(copy, 2)
        status = QVBoxLayout()
        status.setSpacing(2)
        status.addWidget(self.target_key)
        status.addWidget(self.feedback)
        row.addLayout(status, 3)
        practice_layout.addWidget(target)

        stat_card = styled_frame("practiceCard")
        row = QHBoxLayout(stat_card)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(8)
        self.correct_label, self.wrong_label = QLabel(), QLabel()
        self.time_label, self.progress_label = QLabel(), QLabel()
        for label in (self.correct_label, self.wrong_label, self.time_label, self.progress_label):
            label.setObjectName("practiceStat")
            row.addWidget(label)
        row.addStretch()
        practice_layout.addWidget(stat_card)

        selection = styled_frame("practiceCard")
        selection_layout = QVBoxLayout(selection)
        selection_layout.setContentsMargins(10, 7, 10, 8)
        selection_layout.setSpacing(5)
        selection_heading = QHBoxLayout()
        selection_heading.setSpacing(12)
        selection_heading.addWidget(styled_label("建筑选择", "practiceSectionTitle"))
        selection_heading.addStretch()
        selection_heading.addWidget(styled_label(
            "勾选要练习的建筑；未勾选时练习当前文明的全部建筑。", "practiceMuted"
        ))
        selection_layout.addLayout(selection_heading)
        self.building_scroll = QScrollArea()
        self.building_scroll.setWidgetResizable(True)
        self.building_scroll.viewport().setStyleSheet("background: #324156;")
        self.building_content = QWidget()
        self.building_content.setObjectName("practiceBuildingContent")
        self.building_layout = QVBoxLayout(self.building_content)
        self.building_layout.setContentsMargins(0, 0, 5, 0)
        self.building_scroll.setWidget(self.building_content)
        selection_layout.addWidget(self.building_scroll, 1)
        practice_layout.addWidget(selection, 1)
        self.views.addWidget(practice)

        wrong = styled_frame("practiceCard")
        wrong_layout = QVBoxLayout(wrong)
        wrong_layout.setContentsMargins(13, 10, 13, 10)
        row = QHBoxLayout()
        row.addWidget(styled_label("错题本 · 本次运行", "practiceTitle"))
        row.addStretch()
        self.clear_session_button = QPushButton("清空选中会话")
        self.clear_all_button = QPushButton("清空全部")
        self.clear_session_button.clicked.connect(self._clear_selected_session)
        self.clear_all_button.clicked.connect(self._clear_all_sessions)
        row.addWidget(self.clear_session_button)
        row.addWidget(self.clear_all_button)
        wrong_layout.addLayout(row)
        self.wrong_tree = QTreeWidget()
        self.wrong_tree.setHeaderLabels(["建筑 / 会话", "快捷键", "错误次数"])
        self.wrong_tree.setAccessibleName("训练错题记录")
        wrong_layout.addWidget(self.wrong_tree, 1)
        self.views.addWidget(wrong)
        outer.addWidget(self.views, 1)
        self.page_stack.addWidget(workspace)
        self._refresh_controls()
        self._refresh_stats()

    def _build_civilization_picker(self) -> None:
        picker = QWidget()
        picker.setObjectName("civPicker")
        layout = QVBoxLayout(picker)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        hero = styled_frame("civHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 17, 22, 17)
        hero_layout.setSpacing(5)
        hero_layout.addWidget(styled_label("快捷键练习  /  文明选择", "practiceMuted"))
        hero_layout.addWidget(styled_label("选择你的文明", "pickerTitle"))
        hero_layout.addWidget(styled_label(
            "选择后练习该文明的建筑快捷键；可随时返回更换。", "practiceMuted"
        ))
        layout.addWidget(hero)

        tools = QHBoxLayout()
        tools.setSpacing(12)
        self.civ_count = styled_label("", "practiceMuted")
        tools.addWidget(self.civ_count)
        tools.addStretch()
        self.civ_search = QLineEdit()
        self.civ_search.setPlaceholderText("搜索文明")
        self.civ_search.setAccessibleName("搜索练习文明")
        self.civ_search.setClearButtonEnabled(True)
        self.civ_search.setMinimumWidth(170)
        self.civ_search.setMaximumWidth(260)
        self.civ_search.textChanged.connect(self._filter_civilizations)
        tools.addWidget(self.civ_search)
        layout.addLayout(tools)

        self.civ_scroll = QScrollArea()
        self.civ_scroll.setWidgetResizable(True)
        self.civ_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.civ_grid_content = QWidget()
        self.civ_grid_content.setObjectName("civGridContent")
        self.civ_scroll.viewport().setStyleSheet("background: #1d2432;")
        self.civ_grid = QGridLayout(self.civ_grid_content)
        self.civ_grid.setContentsMargins(0, 0, 8, 4)
        self.civ_grid.setHorizontalSpacing(12)
        self.civ_grid.setVerticalSpacing(12)
        guide_codes = {name: code for code, name in CIVILIZATIONS.items()}
        self.civ_cards: list[tuple[str, CivCard]] = []
        for civ in self.catalog.civilizations:
            code = guide_codes.get(civ.name, "")
            flag = self._asset_dir.parent / "guides" / "flags" / f"{code.lower()}-large.webp"
            card = CivCard(code, civ.name, flag if flag.is_file() else civ.icon)
            card.setObjectName("civCard")
            card.setToolTip(f"练习{civ.name}的 {len(self.catalog.available(civ.id))} 个建筑快捷键")
            card.setAccessibleName(f"选择{civ.name}，进入快捷键练习")
            card.setMinimumWidth(148)
            card.setFixedHeight(132)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.clicked.connect(lambda checked=False, civ_id=civ.id: self._choose_civilization(civ_id))
            self.civ_cards.append((civ.id, card))
        self.civ_empty = styled_label("没有找到匹配的文明，请换个关键词。", "practiceMuted")
        self.civ_scroll.setWidget(self.civ_grid_content)
        layout.addWidget(self.civ_scroll, 1)
        self.page_stack.addWidget(picker)
        self._filter_civilizations("")

    def _filter_civilizations(self, query: str) -> None:
        query = query.strip().casefold()
        while self.civ_grid.count():
            self.civ_grid.takeAt(0)
        visible = [(civ_id, card) for civ_id, card in self.civ_cards
                   if query in card.name.casefold()]
        columns = max(2, min(5, (max(self.width(), 560) - 20) // 170))
        for index, (_, card) in enumerate(visible):
            self.civ_grid.addWidget(card, index // columns, index % columns)
            card.show()
        visible_ids = {civ_id for civ_id, _ in visible}
        for civ_id, card in self.civ_cards:
            if civ_id not in visible_ids:
                card.hide()
        self.civ_empty.setVisible(not visible)
        if not visible:
            self.civ_grid.addWidget(self.civ_empty, 0, 0, 1, columns)
        self.civ_grid.setRowStretch((len(visible) + columns - 1) // columns, 1)
        self.civ_count.setText(f"已收录 {len(visible)} / {len(self.civ_cards)} 个文明")

    def _choose_civilization(self, civ_id: str) -> None:
        index = self.civ_combo.findData(civ_id)
        if index < 0:
            return
        self.civ_combo.setCurrentIndex(index)
        self.page_stack.setCurrentIndex(1)
        self.activate()

    def _show_civilization_picker(self) -> None:
        self.pause()
        self.civ_search.clear()
        self.page_stack.setCurrentIndex(0)
        self.civ_search.setFocus(Qt.FocusReason.OtherFocusReason)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "civ_grid"):
            self._filter_civilizations(self.civ_search.text())

    def _set_civilization(self) -> None:
        self._reset()
        civ = self.civ_combo.currentData()
        self._available = self.catalog.available(civ) if civ else ()
        if civ:
            name = self.civ_combo.currentText()
            self.civ_button.setText(f"{name}  ·  更换文明")
        self._rebuild_buildings()
        self._refresh_controls()

    def _rebuild_buildings(self) -> None:
        while self.building_layout.count():
            item = self.building_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._checks.clear()
        for age_key, age_name in AGE_NAMES.items():
            buildings = [building for building in self._available if building.age_key == age_key]
            if not buildings:
                continue
            group = styled_frame("practiceCard")
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(8, 4, 8, 4)
            group_layout.setSpacing(3)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{age_name}  /  {age_key}"))
            row.addStretch()
            select = QPushButton("全选 / 取消")
            select.setObjectName("practiceAgeAction")
            select.setAccessibleName(f"{age_name}建筑全选或取消")
            select.clicked.connect(lambda checked=False, age=age_key: self._toggle_age(age))
            row.addWidget(select)
            group_layout.addLayout(row)
            grid = QGridLayout()
            grid.setHorizontalSpacing(7)
            grid.setVerticalSpacing(2)
            for index, building in enumerate(buildings):
                box = QCheckBox(f"{building.name}  {building.age_key}→{building.action_key}")
                box.setAccessibleName(
                    f"练习 {building.name}，快捷键 {building.age_key} 然后 {building.action_key}"
                )
                icon = QIcon(str(building.icon))
                if not icon.isNull():
                    box.setIcon(icon)
                    box.setIconSize(QSize(30, 30))
                self._checks[building.id] = box
                grid.addWidget(box, index // 3, index % 3)
            group_layout.addLayout(grid)
            self.building_layout.addWidget(group)
        self.building_layout.addStretch()

    def _toggle_age(self, age: str) -> None:
        boxes = [self._checks[item.id] for item in self._available if item.age_key == age]
        checked = not all(box.isChecked() for box in boxes)
        for box in boxes:
            box.setChecked(checked)

    def _select_mode(self, mode: str) -> None:
        if mode != self._mode and self._state != "idle":
            self._reset()
        self._mode = mode
        for value, button in self.mode_buttons.items():
            button.setChecked(value == mode)
        self.views.setCurrentIndex(1 if mode == "wrong" else 0)
        if mode == "wrong":
            self._refresh_wrong_book()
        else:
            self.activate()

    def _start(self) -> None:
        if not self._available:
            return
        if self._state == "paused" and self._target is not None:
            self._state = "running"
            self._timer.start()
            self._refresh_controls()
            self.activate()
            return
        self._correct = self._wrong = self._elapsed = self._progress = 0
        self._total = self.count_spin.value()
        self._state = "running"
        if self._mode == "train":
            self._active_session = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "errors": {}
            }
            self._sessions.append(self._active_session)
        else:
            self._active_session = None
        self._next_target()
        self._timer.start()
        self._refresh_controls()
        self._refresh_stats()
        self.activate()

    def pause(self) -> None:
        if self._state == "running":
            self._state = "paused"
            self._timer.stop()
            self.feedback.setText("已暂停；点击继续可接着练习。")
            self._refresh_controls()

    def activate(self) -> None:
        self.setFocus(Qt.FocusReason.OtherFocusReason)

    def _reset(self) -> None:
        self._timer.stop()
        self._state = "idle"
        self._target = None
        self._active_session = None
        self._first_key = self._revealed = False
        self._correct = self._wrong = self._elapsed = self._progress = self._total = 0
        if hasattr(self, "target_name"):
            self.target_icon.clear()
            self.target_icon.hide()
            self.target_name.setText("等待开始")
            self.target_key.setText("按时代键 → 建筑键")
            self.target_caption.setText("选择文明和建筑，点击开始练习")
            self.feedback.clear()
            self._refresh_controls()
            self._refresh_stats()

    def _next_target(self) -> None:
        selected = [item for item in self._available if self._checks[item.id].isChecked()]
        self._target = random.choice(selected or self._available)
        self._first_key = self._revealed = False
        self._consecutive_errors = 0
        pixmap = QPixmap(str(self._target.icon))
        self.target_icon.show()
        self.target_icon.setPixmap(pixmap.scaled(
            64, 64, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ) if not pixmap.isNull() else QPixmap())
        self.target_name.setText(self._target.name)
        self.target_caption.setText(AGE_NAMES[self._target.age_key] + "建筑")
        self.target_key.setText(
            f"{self._target.age_key} → {self._target.action_key}"
            if self._mode == "learn" else "按时代键，再按建筑键"
        )
        errors = sum(session["errors"].get(self._target.id, 0) for session in self._sessions)
        self.feedback.setText("⚠ 易错点" if errors > 2 else "⚠ 注意" if errors else "")

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if (event.type() == QEvent.Type.KeyPress and self.isVisible()
                and self._mode != "wrong" and self._state == "running"):
            key = event.key()
            if (not event.isAutoRepeat()
                    and event.modifiers() == Qt.KeyboardModifier.NoModifier
                    and Qt.Key.Key_A <= key <= Qt.Key.Key_Z):
                self._handle_key(chr(int(key)))
                return True
        return super().eventFilter(watched, event)

    def _handle_key(self, pressed: str) -> None:
        target = self._target
        if target is None:
            return
        if self._revealed:
            if pressed in (target.age_key, target.action_key):
                self._advance()
            return
        expected = target.action_key if self._first_key else target.age_key
        if pressed == expected:
            if not self._first_key:
                self._first_key = True
                self.feedback.setText("时代键正确，继续按建筑键")
            else:
                self._correct += 1
                for session in self._sessions:
                    if target.id in session["errors"]:
                        session["errors"][target.id] -= 1
                        if session["errors"][target.id] <= 0:
                            del session["errors"][target.id]
                self._advance()
            self._refresh_stats()
            return
        self._wrong += 1
        self._consecutive_errors += 1
        if self._active_session is not None:
            errors = self._active_session["errors"]
            errors[target.id] = errors.get(target.id, 0) + 1
        if self._consecutive_errors >= 3:
            self._revealed = True
            self.target_key.setText(f"正确按键：{target.age_key} → {target.action_key}")
            self.feedback.setText("连续错 3 次；按正确的时代键或建筑键跳到下一题")
        else:
            self._first_key = False
            self.feedback.setText(f"按键不对，请从时代键重试（{self._consecutive_errors}/3）")
        self._refresh_stats()

    def _advance(self) -> None:
        self._progress += 1
        self._refresh_stats()
        if self._progress >= self._total:
            self._state = "finished"
            self._timer.stop()
            self.feedback.setText(f"练习完成：正确 {self._correct} 次，错误 {self._wrong} 次")
            self._refresh_controls()
        else:
            self._next_target()

    def _tick(self) -> None:
        self._elapsed += 1
        self._refresh_stats()

    def _refresh_stats(self) -> None:
        self.correct_label.setText(f"正确  {self._correct}")
        self.wrong_label.setText(f"错误  {self._wrong}")
        self.time_label.setText(f"用时  {self._elapsed} 秒")
        self.progress_label.setText(f"进度  {self._progress}/{self._total}")

    def _refresh_controls(self) -> None:
        self.start_button.setText("继续练习" if self._state == "paused" else "开始练习")
        self.start_button.setEnabled(self._state != "running" and bool(self.civ_combo.currentData()))
        self.pause_button.setEnabled(self._state == "running")
        self.reset_button.setEnabled(self._state != "idle")
        self.count_spin.setEnabled(self._state in ("idle", "finished"))
        if hasattr(self, "building_scroll"):
            self.building_scroll.setEnabled(self._state in ("idle", "finished"))

    def _refresh_wrong_book(self) -> None:
        self.wrong_tree.clear()
        for session in reversed(self._sessions):
            if not session["errors"]:
                continue
            parent = QTreeWidgetItem([f"训练会话 · {session['timestamp']}", "", ""])
            parent.setData(0, Qt.ItemDataRole.UserRole, session)
            self.wrong_tree.addTopLevelItem(parent)
            for item_id, count in session["errors"].items():
                building = next((item for item in self.catalog.buildings if item.id == item_id), None)
                if building is not None:
                    QTreeWidgetItem(parent, [
                        building.name, f"{building.age_key} → {building.action_key}", str(count)
                    ])
            parent.setExpanded(True)
        self.clear_session_button.setEnabled(self.wrong_tree.topLevelItemCount() > 0)
        self.clear_all_button.setEnabled(bool(self._sessions))

    def _clear_selected_session(self) -> None:
        selected = self.wrong_tree.currentItem()
        while selected is not None and selected.parent() is not None:
            selected = selected.parent()
        if selected is not None:
            session = selected.data(0, Qt.ItemDataRole.UserRole)
            if session in self._sessions:
                self._sessions.remove(session)
        self._refresh_wrong_book()

    def _clear_all_sessions(self) -> None:
        self._sessions.clear()
        self._refresh_wrong_book()
