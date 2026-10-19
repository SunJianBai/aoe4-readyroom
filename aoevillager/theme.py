"""Shared AOE4-inspired navy-and-gold presentation for the Qt interface."""

NAVY = "#1d2432"
PANEL = "#324156"
GOLD = "#e6c47d"
GOLD_BRIGHT = "#f5dfa9"
GOLD_MUTED = "#bea774"

TOOLBOX_STYLE = """
QMainWindow, QWidget#toolboxRoot { background: #1d2432; color: #e9ebee; font-family: 'Microsoft YaHei UI'; }
QFrame#shellHeader {
  background: #324156; border: none; border-radius: 8px;
}
QFrame#practiceHeader {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #193853,stop:1 #0b1e31);
  border: 1px solid #9b7d4b; border-radius: 5px;
}
QFrame#guidePanel {
  background: #10243a; border: 1px solid #766547; border-radius: 5px;
}
QLabel#guideTitle { color: #f5dfa9; font-size: 18px; font-weight: 700; }
QLabel#guideMuted { color: #c9b183; font-size: 11px; }
QListWidget { background: #0b1b2b; color: #eee0bf; border: 1px solid #665b45;
  border-radius: 4px; outline: none; }
QListWidget::item { padding: 9px 7px; border-bottom: 1px solid #293d50; }
QListWidget::item:selected { background: #244463; color: #fff0c3; }
QListWidget::item:hover { background: #19374f; }
QLabel#shellTitle { color: #e7c05e; font-size: 20px; font-weight: 700; }
QLabel#practiceTitle { color: #f5dfa9; font-size: 16px; font-weight: 700; }
QLabel#shellMuted { color: #bbc7d5; font-size: 11px; }
QFrame#toolSidebar, QFrame#toolTopNav {
  background: #324156; border: none; border-radius: 8px;
}
QPushButton#toolNav {
  background: transparent; color: #e9ebee; border: none;
  border-radius: 6px; padding: 10px 8px; min-height: 30px; font-weight: 600;
}
QPushButton#toolNav:hover { background: #3d516b; color: #e7c05e; }
QPushButton#toolNav:checked { background: #3d516b; color: #e7c05e; }
QPushButton#toolNav:focus { border: 1px solid #e7c05e; }
QFrame#toolTopNav QPushButton#toolNav { padding: 6px 8px; min-height: 24px; }
QFrame#webFrame { background: #071321; border: 1px solid #766547; border-radius: 4px; }
"""

MAIN_STYLE = """
QMainWindow, QWidget#root { background-color: #1d2432; color: #edf1f4; font-family: 'Microsoft YaHei UI'; }
QLabel { color: #edf1f4; background: transparent; }
QLabel#eyebrow { color: #c8a767; font-size: 10px; font-weight: 700; }
QLabel#title { color: #f6d987; font-size: 20px; font-weight: 700; }
QLabel#sectionTitle { color: #f1d89e; font-size: 15px; font-weight: 700; }
QLabel#subtle { color: #c5d0dd; font-size: 11px; }
QLabel#metricValue { color: #f5dfa9; font-size: 31px; font-weight: 700; }
QLabel#stepNumber { color: #d9bd7e; font-size: 11px; font-weight: 700; }
QLabel#crest { color: #f5dfa9; font-family: Georgia; font-size: 20px; font-weight: 700; }
QFrame#hero {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #354960, stop:1 #26374b);
  border: 1px solid #9a7d4a; border-radius: 8px;
}
QFrame#crestFrame { background: #273b51; border: 1px solid #d5b36e; border-radius: 6px; }
QFrame#card, QFrame#footerCard, QFrame#metricCard, QFrame#timingCard {
  background: #324156; border: 1px solid #50627a; border-radius: 8px;
}
QFrame#metricCard { background: #3b5169; border-color: #a9844f; }
QFrame#timingCard { border-color: #8a7148; }
QFrame#stepRow { background: #273b51; border: 1px solid #64718a; border-radius: 6px; }
QFrame#goldRule { background: #9d7b43; border: none; min-height: 1px; max-height: 1px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #202f42; color: #f5e5bf; selection-background-color: #9b793e;
  selection-color: #17283b; border: 1px solid #7f755c; border-radius: 6px;
  padding: 7px 10px; min-height: 29px; font-size: 12px;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: #c5a466; }
QLineEdit#stepInput { padding: 5px 8px; min-height: 24px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 2px solid #f5d995; }
QComboBox { padding-right: 26px; }
QComboBox::drop-down { border-left: 1px solid #8b754e; width: 23px; }
QComboBox QAbstractItemView {
  background: #26394d; color: #f5e5bf; border: 1px solid #a9844f;
  selection-background-color: #8b6d3c; selection-color: #fff4d3;
  outline: none; padding: 4px;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
  background: #2c3948; color: #8591a0; border-color: #4d5661;
}
QPushButton {
  background: #3b5169; color: #f5e2b0; border: 1px solid #8c7853;
  border-radius: 6px; padding: 8px 15px; min-height: 29px; font-weight: 600;
}
QPushButton:hover { background: #4b6480; border-color: #e0bc79; color: #fff0bf; }
QPushButton:pressed { background: #2e4056; }
QPushButton:focus { border: 2px solid #f5d995; }
QPushButton:disabled { color: #8591a0; background: #2c3948; border-color: #4d5661; }
QPushButton#rowAction, QPushButton#addStep { padding: 5px 11px; min-height: 25px; }
QPushButton#primary {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0d28e, stop:1 #bd9452);
  color: #102035; border: 1px solid #f6dfa6; font-size: 14px; font-weight: 700;
}
QPushButton#primary:hover { background: #f7dfa4; color: #17283b; }
QPushButton#stop { background: #723d38; color: #ffe4bc; border: 1px solid #dbac80; font-size: 14px; font-weight: 700; }
QPushButton#stop:hover { background: #8d4b43; }
QTabBar { background: #324156; border: 1px solid #50627a; border-radius: 6px; }
QTabBar::tab {
  background: #3b5169; color: #e9ebee; border: none; border-bottom: 3px solid #64718a;
  padding: 9px 20px; min-width: 100px; font-weight: 600;
}
QTabBar::tab:hover { background: #4b6480; color: #f5dfa9; }
QTabBar::tab:selected { background: #e0bd72; color: #17283b; border-bottom: 3px solid #f4da9a; }
QTabBar::tab:focus { border-bottom: 3px solid #fff1bd; }
QScrollArea { background: transparent; border: none; }
QWidget#scrollContent { background: #1d2432; border: none; }
QScrollBar:vertical { background: #263445; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #a1885b; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #173047; color: #f5dfa9; border: 1px solid #c5a466; }
"""

DIALOG_STYLE = """
QDialog { background: #1d2432; color: #edf1f4; font-family: 'Microsoft YaHei UI'; }
QLabel, QCheckBox { color: #edf1f4; background: transparent; }
QLabel#dialogTitle { color: #f5dfa9; font-size: 21px; font-weight: 700; }
QLabel#dialogHint { color: #c5d0dd; font-size: 11px; }
QFrame#dialogCard { background: #324156; border: 1px solid #50627a; border-radius: 8px; }
QSpinBox { background: #202f42; color: #f5e5bf; border: 1px solid #7f755c;
  border-radius: 6px; padding: 6px 8px; min-height: 28px; }
QSpinBox:focus { border: 2px solid #f5d995; }
QPushButton { background: #3b5169; color: #f5e2b0; border: 1px solid #8c7853;
  border-radius: 6px; padding: 7px 13px; min-height: 29px; }
QPushButton:hover { background: #4b6480; border-color: #e0bc79; }
QPushButton:focus { border: 2px solid #f5d995; }
QPushButton#dialogPrimary { background: #d9b472; color: #102035; font-weight: 700; }
QPushButton#dialogPrimary:hover { background: #f1d493; }
QSlider::groove:horizontal { height: 4px; background: #5c5b4a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #d5b16c; border-radius: 2px; }
QSlider::handle:horizontal { background: #f3d99f; border: 1px solid #8f7146;
  width: 13px; margin: -5px 0; border-radius: 7px; }
QCheckBox::indicator { width: 17px; height: 17px; }
"""
