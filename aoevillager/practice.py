"""Native, offline AOE4 building-shortcut practice page."""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QStackedWidget, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .practice_catalog import AGE_NAMES, Building, PracticeCatalog
from .widgets import NoWheelComboBox, NoWheelSpinBox


PRACTICE_STYLE = """
QWidget#practiceRoot { background: #071321; color: #ead09b; font-family: 'Microsoft YaHei UI'; }
QFrame#practiceCard, QFrame#practiceHeader {
  background: #10263d; border: 1px solid #756549; border-radius: 5px;
}
QFrame#practiceTarget { background: #0d2033; border: 1px solid #a8844b; border-radius: 5px; }
QLabel { color: #ead09b; background: transparent; }
QLabel#practiceTitle { color: #f5dfa9; font-size: 17px; font-weight: 700; }
QLabel#practiceMuted { color: #c9b88e; font-size: 11px; }
QLabel#practiceBuilding { color: #f5dfa9; font-size: 25px; font-weight: 700; }
QLabel#practiceKey { color: #dfbd79; font-size: 16px; font-weight: 700; }
QLabel#practiceStat { color: #f5dfa9; font-size: 13px; font-weight: 700; }
QComboBox, QSpinBox, QTreeWidget {
  background: #071626; color: #f3dba6; border: 1px solid #917a50;
  border-radius: 4px; padding: 5px 8px; min-height: 28px;
}
QComboBox QAbstractItemView { background: #10243a; color: #f3dba6;
  selection-background-color: #7b643e; }
QPushButton { background: #17314a; color: #edd29a; border: 1px solid #94784d;
  border-radius: 4px; padding: 7px 12px; min-height: 28px; font-weight: 600; }
QPushButton:hover { background: #244663; border-color: #e0bc79; }
QPushButton:checked, QPushButton#practicePrimary { background: #d6b16e;
  color: #0b1b2d; border-color: #f0d99f; }
QPushButton:disabled { color: #807258; background: #102031; border-color: #48483d; }
QPushButton:focus, QComboBox:focus, QSpinBox:focus, QCheckBox:focus {
  border: 2px solid #fff0bc;
}
QCheckBox { color: #f0d7a1; spacing: 8px; padding: 5px; min-height: 35px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox:hover { background: #1a3852; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: #0b1b2b; width: 9px; }
QScrollBar::handle:vertical { background: #856d48; border-radius: 4px; min-height: 22px; }
QTreeWidget::item { min-height: 25px; }
QTreeWidget::item:selected { background: #6b5737; color: #fff2cf; }
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(9)
        header = styled_frame("practiceHeader")
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 8, 14, 8)
        title = styled_label("快捷键练习", "practiceTitle")
        row.addWidget(title)
        row.addStretch()
        row.addWidget(QLabel("文明"))
        self.civ_combo = NoWheelComboBox()
        self.civ_combo.setMinimumWidth(180)
        self.civ_combo.setAccessibleName("选择练习文明")
        self.civ_combo.addItem("请选择文明", None)
        for civ in self.catalog.civilizations:
            self.civ_combo.addItem(QIcon(str(civ.icon)), civ.name, civ.id)
        self.civ_combo.currentIndexChanged.connect(lambda _index: self._set_civilization())
        row.addWidget(self.civ_combo)
        outer.addWidget(header)

        modes = QHBoxLayout()
        modes.setSpacing(7)
        self.mode_buttons = {}
        for value, label in (("learn", "学习模式"), ("train", "训练模式"), ("wrong", "错题本")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(value == "learn")
            button.clicked.connect(lambda checked=False, mode=value: self._select_mode(mode))
            modes.addWidget(button)
            self.mode_buttons[value] = button
        outer.addLayout(modes)

        self.views = QStackedWidget()
        practice = QWidget()
        practice_layout = QVBoxLayout(practice)
        practice_layout.setContentsMargins(0, 0, 0, 0)
        practice_layout.setSpacing(9)
        controls = styled_frame("practiceCard")
        row = QHBoxLayout(controls)
        row.setContentsMargins(13, 8, 13, 8)
        self.start_button = QPushButton("开始练习")
        self.start_button.setObjectName("practicePrimary")
        self.start_button.setAccessibleName("开始或继续快捷键练习")
        self.pause_button = QPushButton("暂停")
        self.reset_button = QPushButton("重置")
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
        row.setContentsMargins(16, 10, 16, 10)
        self.target_icon = QLabel()
        self.target_icon.setFixedSize(96, 96)
        self.target_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.target_icon)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        self.target_caption = styled_label("选择文明和建筑，点击开始练习", "practiceMuted")
        self.target_name = styled_label("等待开始", "practiceBuilding")
        self.target_key = styled_label("按时代键 → 建筑键", "practiceKey")
        self.feedback = QLabel("")
        self.feedback.setAccessibleName("按键反馈")
        for label in (self.target_caption, self.target_name, self.target_key, self.feedback):
            copy.addWidget(label)
        row.addLayout(copy, 1)
        practice_layout.addWidget(target)

        stat_card = styled_frame("practiceCard")
        row = QHBoxLayout(stat_card)
        row.setContentsMargins(13, 6, 13, 6)
        self.correct_label, self.wrong_label = QLabel(), QLabel()
        self.time_label, self.progress_label = QLabel(), QLabel()
        for label in (self.correct_label, self.wrong_label, self.time_label, self.progress_label):
            label.setObjectName("practiceStat")
            row.addWidget(label)
        row.addStretch()
        practice_layout.addWidget(stat_card)

        selection = styled_frame("practiceCard")
        selection_layout = QVBoxLayout(selection)
        selection_layout.setContentsMargins(13, 10, 13, 10)
        selection_layout.setSpacing(6)
        selection_layout.addWidget(styled_label("建筑选择", "practiceTitle"))
        selection_layout.addWidget(styled_label(
            "勾选要练习的建筑；未勾选时练习当前文明的全部建筑。", "practiceMuted"
        ))
        self.building_scroll = QScrollArea()
        self.building_scroll.setWidgetResizable(True)
        self.building_content = QWidget()
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
        self._refresh_controls()
        self._refresh_stats()

    def _set_civilization(self) -> None:
        self._reset()
        civ = self.civ_combo.currentData()
        self._available = self.catalog.available(civ) if civ else ()
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
            group_layout.setContentsMargins(9, 6, 9, 6)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{age_name}  /  {age_key}"))
            row.addStretch()
            select = QPushButton("全选 / 取消")
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
        self.target_icon.setPixmap(pixmap.scaled(
            88, 88, Qt.AspectRatioMode.KeepAspectRatio,
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
