"""Reusable widget helpers."""

from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QHBoxLayout, QVBoxLayout,
    QDoubleSpinBox, QSpinBox, QComboBox, QGroupBox, QSizePolicy,
    QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPalette


def section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    font = lbl.font()
    font.setBold(True)
    font.setPointSize(font.pointSize() + 1)
    lbl.setFont(font)
    return lbl


def hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Sunken)
    return line


class LabeledField(QWidget):
    """A label + input widget pair in a single row."""

    def __init__(self, label: str, widget: QWidget, unit: str = "", parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(label)
        lbl.setFixedWidth(200)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(lbl)
        layout.addWidget(widget)
        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setFixedWidth(50)
            layout.addWidget(unit_lbl)
        else:
            layout.addStretch()


class ScientificSpinBox(QLineEdit):
    """QLineEdit that accepts and displays scientific notation floats."""

    valueChanged = Signal(float)

    def __init__(self, value: float = 0.0, parent=None):
        super().__init__(parent)
        self._value = value
        self.setText(self._format(value))
        self.editingFinished.connect(self._parse)

    def _format(self, v: float) -> str:
        if v == 0.0:
            return "0.0"
        if abs(v) >= 1e4 or (abs(v) < 1e-3 and v != 0):
            return f"{v:.4e}"
        return f"{v:.6g}"

    def _parse(self):
        try:
            v = float(self.text())
            self._value = v
            self.setText(self._format(v))
            self.valueChanged.emit(v)
        except ValueError:
            self.setText(self._format(self._value))

    def value(self) -> float:
        return self._value

    def setValue(self, v: float):
        self._value = v
        self.setText(self._format(v))


class ResultBox(QGroupBox):
    """Read-only display of computed results."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._layout = QVBoxLayout(self)
        self._rows: dict[str, QLabel] = {}

    def set_row(self, key: str, label: str, value: str, unit: str = ""):
        if key not in self._rows:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setFixedWidth(260)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val = QLabel()
            val.setMinimumWidth(140)
            val.setFont(QFont("Courier", 10))
            unit_lbl = QLabel(unit)
            unit_lbl.setFixedWidth(60)
            hl.addWidget(lbl)
            hl.addWidget(val)
            hl.addWidget(unit_lbl)
            hl.addStretch()
            self._layout.addWidget(row)
            self._rows[key] = val
        self._rows[key].setText(value)

    def clear_all(self):
        for lbl in self._rows.values():
            lbl.setText("—")
