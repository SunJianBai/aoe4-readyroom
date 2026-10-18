"""Shared AOE4-inspired navy-and-gold presentation for the Qt interface."""

NAVY = "#071321"
PANEL = "#10243a"
GOLD = "#e6c47d"
GOLD_BRIGHT = "#f5dfa9"
GOLD_MUTED = "#bea774"

TOOLBOX_STYLE = """
QMainWindow, QWidget#toolboxRoot { background: #071321; color: #e8cd94; font-family: 'Microsoft YaHei UI'; }
QFrame#shellHeader, QFrame#practiceHeader {
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #193853,stop:1 #0b1e31);
  border: 1px solid #9b7d4b; border-radius: 5px;
}
QLabel#shellTitle { color: #f5dfa9; font-size: 20px; font-weight: 700; }
QLabel#practiceTitle { color: #f5dfa9; font-size: 16px; font-weight: 700; }
QLabel#shellMuted { color: #c2ae83; font-size: 11px; }
QFrame#toolSidebar, QFrame#toolTopNav {
  background: #0e2237; border: 1px solid #514d3d; border-radius: 5px;
}
QPushButton#toolNav {
  background: #10283f; color: #e8ce94; border: 1px solid #5d5947;
  border-radius: 4px; padding: 10px 8px; min-height: 30px; font-weight: 600;
}
QPushButton#toolNav:hover { background: #1c3b58; border-color: #c9a66c; }
QPushButton#toolNav:checked { background: #d6b16e; color: #0b1b2d; border-color: #f0d99f; }
QPushButton#toolNav:focus { border: 2px solid #fff0bc; }
QFrame#toolTopNav QPushButton#toolNav { padding: 6px 8px; min-height: 24px; }
QFrame#webFrame { background: #071321; border: 1px solid #766547; border-radius: 4px; }
"""

MAIN_STYLE = """
QMainWindow, QWidget#root { background-color: #071321; color: #e6c47d; font-family: 'Microsoft YaHei UI'; }
QLabel { color: #e8cd94; background: transparent; }
QLabel#eyebrow { color: #c8a767; font-size: 10px; font-weight: 700; }
QLabel#title { color: #f5dfa9; font-size: 22px; font-weight: 700; }
QLabel#sectionTitle { color: #f1d89e; font-size: 15px; font-weight: 700; }
QLabel#subtle { color: #c2ae83; font-size: 11px; }
QLabel#metricValue { color: #f5dfa9; font-size: 31px; font-weight: 700; }
QLabel#stepNumber { color: #d9bd7e; font-size: 11px; font-weight: 700; }
QLabel#crest { color: #f5dfa9; font-family: Georgia; font-size: 20px; font-weight: 700; }
QFrame#hero {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #193853, stop:0.52 #10263d, stop:1 #0a1a2b);
  border: 1px solid #a8844b; border-radius: 5px;
}
QFrame#crestFrame { background: #10243a; border: 1px solid #d5b36e; border-radius: 3px; }
QFrame#card, QFrame#footerCard, QFrame#metricCard, QFrame#timingCard {
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #122a42, stop:1 #0b1c2e);
  border: 1px solid #5b563f; border-radius: 5px;
}
QFrame#metricCard { border-color: #a9844f; }
QFrame#timingCard { border-color: #8a7148; }
QFrame#stepRow { background: #102239; border: 1px solid #47536a; border-radius: 4px; }
QFrame#goldRule { background: #9d7b43; border: none; min-height: 1px; max-height: 1px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
  background: #071626; color: #f3dba6; selection-background-color: #9b793e;
  selection-color: #071321; border: 1px solid #8b754e; border-radius: 4px;
  padding: 7px 10px; min-height: 29px; font-size: 12px;
}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover { border-color: #c5a466; }
QLineEdit#stepInput { padding: 5px 8px; min-height: 24px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border: 2px solid #f5d995; }
QComboBox { padding-right: 26px; }
QComboBox::drop-down { border-left: 1px solid #8b754e; width: 23px; }
QComboBox QAbstractItemView {
  background: #10243a; color: #f3dba6; border: 1px solid #a9844f;
  selection-background-color: #8b6d3c; selection-color: #fff4d3;
  outline: none; padding: 4px;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {
  background: #0b1724; color: #806f53; border-color: #3a4050;
}
QPushButton {
  background: #132b43; color: #edd29a; border: 1px solid #94784d;
  border-radius: 4px; padding: 8px 15px; min-height: 29px; font-weight: 600;
}
QPushButton:hover { background: #1d3b58; border-color: #e0bc79; color: #fff0bf; }
QPushButton:pressed { background: #0b1c2f; }
QPushButton:focus { border: 2px solid #f5d995; }
QPushButton:disabled { color: #806f53; background: #101d2a; border-color: #43443e; }
QPushButton#rowAction, QPushButton#addStep { padding: 5px 11px; min-height: 25px; }
QPushButton#primary {
  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f0d28e, stop:1 #bd9452);
  color: #102035; border: 1px solid #f6dfa6; font-size: 14px; font-weight: 700;
}
QPushButton#primary:hover { background: #f7dfa4; color: #071321; }
QPushButton#stop { background: #723d38; color: #ffe4bc; border: 1px solid #dbac80; font-size: 14px; font-weight: 700; }
QPushButton#stop:hover { background: #8d4b43; }
QTabBar { background: #0a1c2e; border: 1px solid #514d3d; border-radius: 4px; }
QTabBar::tab {
  background: #0d2033; color: #c6ab74; border: none; border-bottom: 3px solid #4e5048;
  padding: 9px 20px; min-width: 100px; font-weight: 600;
}
QTabBar::tab:hover { background: #19344c; color: #f5dfa9; }
QTabBar::tab:selected { background: #17324c; color: #f5dfa9; border-bottom: 3px solid #e4bd74; }
QTabBar::tab:focus { border-bottom: 3px solid #fff1bd; }
QScrollArea, QWidget#scrollContent { background: transparent; border: none; }
QScrollBar:vertical { background: #0b1b2b; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #856d48; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QToolTip { background: #173047; color: #f5dfa9; border: 1px solid #c5a466; }
"""

DIALOG_STYLE = """
QDialog { background: #071321; color: #e6c47d; font-family: 'Microsoft YaHei UI'; }
QLabel, QCheckBox { color: #e8cd94; background: transparent; }
QLabel#dialogTitle { color: #f5dfa9; font-size: 21px; font-weight: 700; }
QLabel#dialogHint { color: #c2ae83; font-size: 11px; }
QFrame#dialogCard { background: #10243a; border: 1px solid #716449; border-radius: 5px; }
QSpinBox { background: #071626; color: #f3dba6; border: 1px solid #8b754e;
  border-radius: 4px; padding: 6px 8px; min-height: 28px; }
QSpinBox:focus { border: 2px solid #f5d995; }
QPushButton { background: #132b43; color: #edd29a; border: 1px solid #94784d;
  border-radius: 4px; padding: 7px 13px; min-height: 29px; }
QPushButton:hover { background: #1d3b58; border-color: #e0bc79; }
QPushButton:focus { border: 2px solid #f5d995; }
QPushButton#dialogPrimary { background: #d9b472; color: #102035; font-weight: 700; }
QPushButton#dialogPrimary:hover { background: #f1d493; }
QSlider::groove:horizontal { height: 4px; background: #5c5b4a; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #d5b16c; border-radius: 2px; }
QSlider::handle:horizontal { background: #f3d99f; border: 1px solid #8f7146;
  width: 13px; margin: -5px 0; border-radius: 7px; }
QCheckBox::indicator { width: 17px; height: 17px; }
"""
