from __future__ import annotations

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTabBar, QVBoxLayout, QWidget,
)

from .cycle import CycleEngine
from .hotkeys import GlobalHotkeyManager
from .keyedit import KeyStepEdit
from .overlay import OverlaySettingsDialog, StatusOverlay
from .settings import CUSTOM_NATION, NATION_PRESETS, SettingsStore
from .theme import GOLD_MUTED, MAIN_STYLE
from .widgets import NoWheelComboBox, NoWheelDoubleSpinBox, NoWheelSpinBox


class TrainingPage(QWidget):
    def __init__(self, store: SettingsStore) -> None:
        super().__init__()
        self.store = store
        self.hotkeys = GlobalHotkeyManager(store.values.toggle_hotkey)
        self.engine = CycleEngine(suspend_hotkey=lambda state: self.hotkeys.set_suspended(state, "cycle"))
        self.overlay = StatusOverlay(store.values.toggle_hotkey)
        self.overlay.resize(store.values.overlay_width, store.values.overlay_height)
        if store.values.overlay_x is not None and store.values.overlay_y is not None:
            from PyQt6.QtCore import QPoint
            self.overlay.set_saved_position(QPoint(store.values.overlay_x, store.values.overlay_y))
        self.overlay.setWindowOpacity(store.values.overlay_opacity / 100.0)
        self.overlay.position_changed.connect(store.set_overlay_position)
        self.overlay.size_changed.connect(store.set_overlay_size)
        self.overlay_dialog = OverlaySettingsDialog(self.overlay, store, self._set_overlay_visible, self)
        self._custom_rows: list[tuple[QWidget, KeyStepEdit]] = []
        self._rounds = 0
        self._tool_active = True

        self.setObjectName("root")
        self.setAccessibleName("自动训练村民工具")
        self.setMinimumWidth(640)
        self.setStyleSheet(MAIN_STYLE)
        self._build()
        self._connect()
        self._update_summary()
        self._update_state(False)
        if store.values.overlay_visible:
            self.overlay.show()
        self.hotkeys.start()

    def _build(self) -> None:
        page = QVBoxLayout(self)
        page.setContentsMargins(18, 14, 18, 14)
        page.setSpacing(9)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(14, 8, 14, 8)
        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(2)
        title = QLabel("自动训练村民工具")
        title.setObjectName("title")
        hero_copy.addWidget(title)
        intro = QLabel("简单模式按人数计算周期；自定义模式可编辑按键顺序和循环时间。")
        intro.setObjectName("subtle")
        intro.setWordWrap(True)
        hero_copy.addWidget(intro)
        hero_row.addLayout(hero_copy, 1)
        page.addWidget(hero)

        self.tabs = QTabBar()
        self.tabs.addTab("简单模式")
        self.tabs.addTab("自定义模式")
        self.tabs.setExpanding(True)
        self.tabs.setAccessibleName("运行模式")
        page.addWidget(self.tabs)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._simple_page())
        self.stack.addWidget(self._custom_page())
        page.addWidget(self.stack, 1)

        footer = QFrame()
        footer.setObjectName("footerCard")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(13, 8, 13, 8)
        footer_layout.setSpacing(5)
        status_row = QHBoxLayout()
        status_row.setSpacing(9)
        self.status = QLabel("● 未运行")
        self.status.setAccessibleName("当前运行状态")
        status_row.addWidget(self.status)
        self.round_count = QLabel("已完成 0 轮")
        self.round_count.setObjectName("subtle")
        status_row.addWidget(self.round_count)
        status_row.addStretch()
        status_row.addWidget(QLabel("全局开关"))
        self.hotkey_edit = QLineEdit(self.store.values.toggle_hotkey)
        self.hotkey_edit.setMaximumWidth(125)
        self.hotkey_edit.setAccessibleName("全局开关快捷键")
        self.hotkey_edit.setToolTip("例如 F6 或 Ctrl+Shift+F6；输入后点击应用")
        self.hotkey_edit.installEventFilter(self)
        status_row.addWidget(self.hotkey_edit)
        self.hotkey_apply = QPushButton("应用")
        self.hotkey_apply.setAccessibleName("应用全局开关快捷键")
        status_row.addWidget(self.hotkey_apply)
        footer_layout.addLayout(status_row)
        actions = QHBoxLayout()
        actions.setSpacing(9)
        self.toggle_button = QPushButton("开始自动训练")
        self.toggle_button.setObjectName("primary")
        self.toggle_button.setAccessibleName("开始或停止自动训练")
        actions.addWidget(self.toggle_button, 1)
        self.overlay_button = QPushButton("设置 · 悬浮窗")
        self.overlay_button.setAccessibleName("打开悬浮窗设置")
        actions.addWidget(self.overlay_button)
        footer_layout.addLayout(actions)
        page.addWidget(footer)

        index = 0 if self.store.values.mode == "simple" else 1
        self.tabs.setCurrentIndex(index)
        self.stack.setCurrentIndex(index)

    def _simple_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        self.simple_grid = QGridLayout()
        self.simple_grid.setHorizontalSpacing(10)
        self.simple_grid.setVerticalSpacing(9)
        self.simple_grid.setColumnStretch(0, 1)
        self.simple_grid.setColumnStretch(1, 1)
        self._simple_wide = False

        key_card = QFrame()
        key_card.setObjectName("card")
        key_layout = QVBoxLayout(key_card)
        key_layout.setContentsMargins(14, 12, 14, 12)
        key_layout.setSpacing(8)
        key_heading = QLabel("01  /  快捷指令")
        key_heading.setObjectName("sectionTitle")
        key_layout.addWidget(key_heading)
        self.tc_edit = KeyStepEdit()
        self.tc_edit.setText(self.store.values.tc_key)
        self.tc_edit.setAccessibleName("选中 TC 的快捷键")
        key_layout.addLayout(self._simple_field_row("选中 TC", self._key_row(self.tc_edit)))
        self.train_edit = KeyStepEdit()
        self.train_edit.setText(self.store.values.train_key)
        self.train_edit.setAccessibleName("训练村民的快捷键")
        key_layout.addLayout(self._simple_field_row("训练村民", self._key_row(self.train_edit)))

        timing_card = QFrame()
        timing_card.setObjectName("card")
        timing_layout = QVBoxLayout(timing_card)
        timing_layout.setContentsMargins(14, 12, 14, 12)
        timing_layout.setSpacing(8)
        timing_heading = QLabel("02  /  训练周期")
        timing_heading.setObjectName("sectionTitle")
        timing_layout.addWidget(timing_heading)
        self.nation_combo = NoWheelComboBox()
        for nation, (label, seconds) in NATION_PRESETS.items():
            self.nation_combo.addItem(f"{label} · {seconds:g} 秒", nation)
        self.nation_combo.addItem("自定义", CUSTOM_NATION)
        self.nation_combo.setCurrentIndex(self.nation_combo.findData(self.store.values.simple_nation))
        self.nation_combo.setAccessibleName("国家与训练时间预设")
        self.nation_combo.setToolTip("选择预设会自动填入单个村民训练时间；手动修改时间后变为自定义")
        self.nation_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        timing_layout.addLayout(self._simple_field_row("国家预设", self.nation_combo))
        self.time_spin = NoWheelDoubleSpinBox()
        self.time_spin.setRange(0.1, 3600.0)
        self.time_spin.setDecimals(1)
        self.time_spin.setSingleStep(1.0)
        self.time_spin.setSuffix(" 秒")
        self.time_spin.setValue(self.store.values.train_time_s)
        self.time_spin.setAccessibleName("单个村民训练时间 t，单位秒")
        self.time_spin.setKeyboardTracking(False)
        self.time_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        timing_layout.addLayout(self._simple_field_row("训练时间 t", self.time_spin))
        self.count_spin = NoWheelSpinBox()
        self.count_spin.setRange(1, 100)
        self.count_spin.setValue(self.store.values.villagers_per_round)
        self.count_spin.setSuffix(" 个")
        self.count_spin.setAccessibleName("每轮训练村民个数 n")
        self.count_spin.setKeyboardTracking(False)
        self.count_spin.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        timing_layout.addLayout(self._simple_field_row("每轮数量 n", self.count_spin))
        self.simple_grid.addWidget(key_card, 0, 0)
        self.simple_grid.addWidget(timing_card, 0, 1)

        metric = QFrame()
        metric.setObjectName("metricCard")
        self.simple_metric = metric
        metric_row = QHBoxLayout(metric)
        metric_row.setContentsMargins(16, 10, 16, 10)
        metric_copy = QVBoxLayout()
        metric_copy.setSpacing(2)
        metric_title = QLabel("下一轮启动间隔")
        metric_title.setObjectName("eyebrow")
        metric_copy.addWidget(metric_title)
        self.simple_formula = QLabel()
        self.simple_formula.setObjectName("subtle")
        metric_copy.addWidget(self.simple_formula)
        metric_note = QLabel("从本轮第一次训练按键算起")
        metric_note.setObjectName("subtle")
        metric_copy.addWidget(metric_note)
        metric_row.addLayout(metric_copy, 1)
        self.simple_summary = QLabel()
        self.simple_summary.setObjectName("metricValue")
        self.simple_summary.setAccessibleName("计算得出的每轮循环间隔")
        metric_row.addWidget(self.simple_summary)
        self.simple_grid.addWidget(metric, 1, 0, 1, 2)
        layout.addLayout(self.simple_grid)
        layout.addStretch(1)
        for edit in (self.tc_edit, self.train_edit):
            edit.editingFinished.connect(self._save_simple)
            edit.focus_changed.connect(lambda focused: self.hotkeys.set_suspended(focused, "key-editor"))
            edit.recording_error.connect(self._show_error)
        self.nation_combo.currentIndexChanged.connect(self._on_nation_changed)
        self.time_spin.valueChanged.connect(self._on_train_time_changed)
        self.count_spin.valueChanged.connect(self._save_simple)
        return page

    @staticmethod
    def _simple_field_row(label: str, field: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(7)
        caption = QLabel(label)
        caption.setFixedWidth(80)
        row.addWidget(caption)
        row.addWidget(field, 1)
        return row

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if not hasattr(self, "simple_metric"):
            return
        wide = event.size().width() >= 1030
        if wide == self._simple_wide:
            return
        self._simple_wide = wide
        self.simple_grid.removeWidget(self.simple_metric)
        if wide:
            self.simple_grid.addWidget(self.simple_metric, 0, 2)
            self.simple_grid.setColumnStretch(2, 1)
        else:
            self.simple_grid.addWidget(self.simple_metric, 1, 0, 1, 2)
            self.simple_grid.setColumnStretch(2, 0)

    def _custom_page(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        header_row = QHBoxLayout()
        header_copy = QVBoxLayout()
        header_copy.setSpacing(2)
        header = QLabel("自由编排按键序列")
        header.setObjectName("sectionTitle")
        header_copy.addWidget(header)
        description = QLabel("每一步可输入单键或 2–3 键组合；运行时依照列表顺序发送。")
        description.setObjectName("subtle")
        description.setWordWrap(True)
        header_copy.addWidget(description)
        header_row.addLayout(header_copy, 1)
        self.add_step_button = QPushButton("＋ 添加步骤")
        self.add_step_button.setObjectName("addStep")
        self.add_step_button.setAccessibleName("添加自定义按键步骤")
        header_row.addWidget(self.add_step_button)
        outer.addLayout(header_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(170)
        container = QWidget()
        container.setObjectName("scrollContent")
        self.rows_layout = QVBoxLayout(container)
        self.rows_layout.setContentsMargins(0, 0, 7, 0)
        self.rows_layout.setSpacing(5)
        self.rows_layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll, 1)

        timing = QFrame()
        timing.setObjectName("timingCard")
        timing_layout = QHBoxLayout(timing)
        timing_layout.setContentsMargins(14, 9, 14, 9)
        timing_layout.setSpacing(16)
        timing_copy = QVBoxLayout()
        timing_copy.setSpacing(2)
        timing_title = QLabel("循环节拍  /  TIMING")
        timing_title.setObjectName("sectionTitle")
        timing_copy.addWidget(timing_title)
        note = QLabel("下一轮从第 2 步按下时开始计时")
        note.setObjectName("subtle")
        timing_copy.addWidget(note)
        timing_layout.addLayout(timing_copy, 1)

        gap_column = QVBoxLayout()
        gap_column.setSpacing(2)
        gap_column.addWidget(QLabel("步骤间隔"))
        self.gap_spin = NoWheelSpinBox()
        self.gap_spin.setRange(0, 1000)
        self.gap_spin.setSuffix(" ms")
        self.gap_spin.setValue(self.store.values.custom_gap_ms)
        self.gap_spin.setKeyboardTracking(False)
        self.gap_spin.setAccessibleName("相邻按键步骤间隔，单位毫秒")
        self.gap_spin.setFixedWidth(130)
        gap_column.addWidget(self.gap_spin)
        timing_layout.addLayout(gap_column)

        period_column = QVBoxLayout()
        period_column.setSpacing(2)
        period_column.addWidget(QLabel("循环时间"))
        self.period_spin = NoWheelDoubleSpinBox()
        self.period_spin.setRange(0.1, 3600.0)
        self.period_spin.setDecimals(1)
        self.period_spin.setSuffix(" 秒")
        self.period_spin.setValue(self.store.values.custom_period_s)
        self.period_spin.setKeyboardTracking(False)
        self.period_spin.setAccessibleName("每轮间隔，单位秒")
        self.period_spin.setFixedWidth(130)
        period_column.addWidget(self.period_spin)
        timing_layout.addLayout(period_column)
        outer.addWidget(timing)
        for key in self.store.values.custom_keys:
            self._add_custom_row(key)
        self.add_step_button.clicked.connect(lambda: self._add_custom_row("Q"))
        self.gap_spin.valueChanged.connect(self._save_custom_timing)
        self.period_spin.valueChanged.connect(self._save_custom_timing)
        return page

    def _key_row(self, edit: KeyStepEdit) -> QWidget:
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(edit, 1)
        record = QPushButton("录制")
        record.setToolTip("点击后同时按住目标按键，松开后完成")
        record.clicked.connect(edit.begin_recording)
        row.addWidget(record)
        return wrapper

    def _add_custom_row(self, key: str) -> None:
        wrapper = QFrame()
        wrapper.setObjectName("stepRow")
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(9, 5, 9, 5)
        row.setSpacing(7)
        number = QLabel()
        number.setObjectName("stepNumber")
        number.setMinimumWidth(54)
        row.addWidget(number)
        edit = KeyStepEdit()
        edit.setObjectName("stepInput")
        edit.setText(key)
        row.addWidget(edit, 1)
        record = QPushButton("录制")
        record.setObjectName("rowAction")
        record.clicked.connect(edit.begin_recording)
        row.addWidget(record)
        remove = QPushButton("删除")
        remove.setObjectName("rowAction")
        remove.setToolTip("移除此按键步骤")
        remove.setAccessibleName("删除当前按键步骤")
        remove.clicked.connect(lambda: self._remove_custom_row(wrapper))
        row.addWidget(remove)
        self.rows_layout.insertWidget(self.rows_layout.count() - 1, wrapper)
        self._custom_rows.append((wrapper, edit))
        edit.editingFinished.connect(self._save_custom_keys)
        edit.focus_changed.connect(lambda focused: self.hotkeys.set_suspended(focused, "key-editor"))
        edit.recording_error.connect(self._show_error)
        self._renumber_rows()
        self._save_custom_keys()

    def _remove_custom_row(self, wrapper: QWidget) -> None:
        if len(self._custom_rows) == 1:
            self._show_error("自定义模式至少保留一个步骤")
            return
        self._custom_rows = [(w, e) for w, e in self._custom_rows if w is not wrapper]
        self.rows_layout.removeWidget(wrapper)
        wrapper.deleteLater()
        self._renumber_rows()
        self._save_custom_keys()

    def _renumber_rows(self) -> None:
        for index, (wrapper, edit) in enumerate(self._custom_rows, 1):
            label = wrapper.layout().itemAt(0).widget()
            label.setText(f"步骤 {index}")
            edit.setAccessibleName(f"自定义步骤 {index} 的按键")

    def _connect(self) -> None:
        self.tabs.currentChanged.connect(self._change_mode)
        self.toggle_button.clicked.connect(self._toggle)
        self.overlay_button.clicked.connect(self._open_overlay_settings)
        self.hotkey_apply.clicked.connect(self._apply_hotkey)
        self.hotkey_edit.returnPressed.connect(self._apply_hotkey)
        self.hotkeys.triggered.connect(self._toggle)
        self.hotkeys.error.connect(self._show_error)
        self.engine.state_changed.connect(self._update_state)
        self.engine.round_completed.connect(self._completed_round)
        self.engine.error.connect(self._show_error)

    def _save_simple(self) -> bool:
        try:
            self.store.set_simple(
                self.tc_edit.text(), self.train_edit.text(),
                self.time_spin.value(), self.count_spin.value(), self.nation_combo.currentData(),
            )
        except ValueError as exc:
            self._show_error(str(exc))
            self.tc_edit.setText(self.store.values.tc_key)
            self.train_edit.setText(self.store.values.train_key)
            return False
        self._update_summary()
        return True

    def _on_nation_changed(self) -> None:
        nation = self.nation_combo.currentData()
        if nation in NATION_PRESETS:
            was_blocked = self.time_spin.blockSignals(True)
            try:
                self.time_spin.setValue(NATION_PRESETS[nation][1])
            finally:
                self.time_spin.blockSignals(was_blocked)
        self._save_simple()

    def _on_train_time_changed(self) -> None:
        nation = self.nation_combo.currentData()
        if nation in NATION_PRESETS and self.time_spin.value() != NATION_PRESETS[nation][1]:
            was_blocked = self.nation_combo.blockSignals(True)
            try:
                self.nation_combo.setCurrentIndex(self.nation_combo.findData(CUSTOM_NATION))
            finally:
                self.nation_combo.blockSignals(was_blocked)
        self._save_simple()

    def _save_custom_keys(self) -> bool:
        if not self._custom_rows:
            return False
        try:
            self.store.set_custom_keys([edit.text() for _, edit in self._custom_rows])
        except ValueError as exc:
            self._show_error(str(exc))
            return False
        return True

    def _save_custom_timing(self) -> None:
        self.store.set_custom_timing(self.gap_spin.value(), self.period_spin.value())

    def _update_summary(self) -> None:
        seconds = self.time_spin.value() * self.count_spin.value()
        self.simple_summary.setText(f"{seconds:g} 秒")
        self.simple_formula.setText(f"{self.time_spin.value():g} 秒 × {self.count_spin.value()} 个村民")

    def _change_mode(self, index: int) -> None:
        if self.engine.is_running:
            self.engine.stop()
        self.stack.setCurrentIndex(index)
        self.store.set_mode("simple" if index == 0 else "custom")
        self._rounds = 0
        self.round_count.setText("已完成 0 轮")
        self.overlay.set_status(False, self.store.values.mode, self.store.values.toggle_hotkey)

    def _toggle(self) -> None:
        if not self._tool_active:
            return
        if self.engine.is_running:
            self.engine.stop()
            return
        if self.store.values.mode == "simple":
            if not self._save_simple():
                return
            values = self.store.values
            keys = values.simple_steps
            gap_ms, period_s, anchor = 2, values.simple_period_s, 2
        else:
            if not self._save_custom_keys():
                return
            self._save_custom_timing()
            values = self.store.values
            keys = values.custom_keys
            gap_ms, period_s, anchor = values.custom_gap_ms, values.custom_period_s, min(1, len(keys) - 1)
        try:
            self.engine.configure(keys, gap_ms, period_s, anchor_step_index=anchor)
            self._rounds = 0
            self.round_count.setText("已完成 0 轮")
            self.engine.start()
        except (ValueError, RuntimeError) as exc:
            self._show_error(str(exc))

    def _update_state(self, running: bool) -> None:
        self.status.setText("● 正在运行" if running else "● 未运行")
        self.status.setStyleSheet(f"color: {'#a8e1ba' if running else GOLD_MUTED}; font-weight: 700")
        self.toggle_button.setText("停止自动训练" if running else "开始自动训练")
        self.toggle_button.setObjectName("stop" if running else "primary")
        self.toggle_button.style().unpolish(self.toggle_button)
        self.toggle_button.style().polish(self.toggle_button)
        self.stack.setEnabled(not running)
        self.overlay.set_status(running, self.store.values.mode, self.store.values.toggle_hotkey)

    def _completed_round(self) -> None:
        self._rounds += 1
        self.round_count.setText(f"已完成 {self._rounds} 轮")

    def _apply_hotkey(self) -> None:
        hotkey = self.hotkey_edit.text().strip().upper()
        try:
            self.hotkeys.set_shortcut(hotkey)
            self.store.set_hotkey(hotkey)
        except ValueError as exc:
            self._show_error(str(exc))
            self.hotkey_edit.setText(self.store.values.toggle_hotkey)
        self.overlay.set_status(self.engine.is_running, self.store.values.mode, self.store.values.toggle_hotkey)

    def _open_overlay_settings(self) -> None:
        self.overlay_dialog.sync_from_overlay()
        self.overlay_dialog.show()
        self.overlay_dialog.raise_()
        self.overlay_dialog.activateWindow()

    def _set_overlay_visible(self, visible: bool) -> None:
        self.store.set_overlay_visible(visible)
        if visible and self._tool_active:
            self.overlay.show()
            if self.overlay_dialog.isVisible():
                self.overlay.set_editable(True)
        else:
            self.overlay.hide()

    def set_tool_active(self, active: bool) -> None:
        if active == self._tool_active:
            return
        if not active and self.engine.is_running:
            raise RuntimeError("自动训练尚未停止，不能切换工具")
        self._tool_active = active
        self.hotkeys.set_suspended(not active, "other-tool")
        if active:
            if self.store.values.overlay_visible:
                self.overlay.show()
        else:
            self.overlay_dialog.close()
            self.overlay.hide()

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "AOEvillager", message)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.hotkey_edit:
            if event.type() == QEvent.Type.FocusIn:
                self.hotkeys.set_suspended(True, "hotkey-editor")
            elif event.type() == QEvent.Type.FocusOut:
                self.hotkeys.set_suspended(False, "hotkey-editor")
        return super().eventFilter(watched, event)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.overlay_dialog.close()
        self.engine.shutdown()
        self.hotkeys.stop()
        self.overlay.close()
        super().closeEvent(event)
