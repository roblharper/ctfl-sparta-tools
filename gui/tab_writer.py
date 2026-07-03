"""Input Writer tab — preview and save the generated SPARTA .in file."""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QFileDialog, QTextEdit, QDoubleSpinBox, QLineEdit, QScrollArea,
    QCheckBox, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QColor
import re

from .state import AppStateSignals
from .engine import DerivedQuantities
from . import writer as _writer


# ── Minimal SPARTA syntax highlighter ────────────────────────────────────────

class SpartaHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self._rules = []

        def add(pattern, color, bold=False, italic=False):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(700)
            if italic:
                fmt.setFontItalic(True)
            self._rules.append((re.compile(pattern), fmt))

        # Comments
        add(r"#.*$", "#6a9955", italic=True)
        # Commands (first token on line)
        cmds = (
            r"\b(seed|dimension|units|boundary|create_box|create_grid|balance_grid|"
            r"global|timestep|species|species_modify|mixture|create_particles|"
            r"collide|collide_modify|react|react_modify|read_surf|surf_collide|"
            r"surf_modify|surf_react|fix|unfix|compute|uncompute|stats|stats_style|"
            r"dump|dump_modify|undump|run|reset_timestep|variable|if|jump|label|"
            r"next|include|print|echo|log|quit|restart|read_restart|write_restart|"
            r"read_grid|write_grid|adapt_grid|region|group|balance|read_isurf)\b"
        )
        add(cmds, "#569cd6", bold=True)
        # Numbers
        add(r"[-+]?\b\d+\.?\d*[eE][-+]?\d+\b", "#b5cea8")
        add(r"[-+]?\b\d*\.\d+\b", "#b5cea8")
        add(r"\b\d+\b", "#b5cea8")
        # Keywords / options
        kws = r"\b(vss|none|tce|qk|smooth|discrete|no|yes|rcb|part|cell|diffuse|specular|constant|variable|MW|MWHTP|MWHTHB|BIRD|si)\b"
        add(kws, "#c586c0")
        # Variable refs
        add(r"\$\{[^}]+\}", "#dcdcaa")

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


# ── Tab ───────────────────────────────────────────────────────────────────────

class WriterTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._derived: DerivedQuantities = DerivedQuantities()
        self._setup_ui()

    def _setup_ui(self):
        vl = QVBoxLayout(self)
        vl.setContentsMargins(8, 8, 8, 8)
        vl.setSpacing(8)

        # Top toolbar
        bar = QHBoxLayout()

        bar.addWidget(QLabel("Output file:"))
        self.out_path_edit = QLineEdit()
        self.out_path_edit.setPlaceholderText("e.g.  /path/to/case.in")
        bar.addWidget(self.out_path_edit)

        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output)
        bar.addWidget(browse_btn)

        self.gen_btn = QPushButton("⟳  Regenerate")
        self.gen_btn.setToolTip("Rebuild the script from current settings")
        self.gen_btn.clicked.connect(self.regenerate)
        bar.addWidget(self.gen_btn)

        self.save_btn = QPushButton("💾  Save")
        self.save_btn.clicked.connect(self._save)
        bar.addWidget(self.save_btn)

        vl.addLayout(bar)

        # Editor
        self.editor = QTextEdit()
        self.editor.setFont(QFont("Courier", 10))
        self.editor.setPlaceholderText("Click 'Regenerate' to generate the SPARTA input script…")
        self.editor.setAcceptRichText(False)
        self.highlighter = SpartaHighlighter(self.editor.document())
        vl.addWidget(self.editor, 1)

        # Status bar
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(self.status_label)

    def _browse_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SPARTA input file", f"{self.bus.state.case_name}.in",
            "SPARTA input (*.in);;All files (*)"
        )
        if path:
            self.out_path_edit.setText(path)

    def regenerate(self):
        try:
            script = _writer.generate(self.bus.state, self._derived)
            self.editor.setPlainText(script)
            lines = script.count("\n") + 1
            self.status_label.setText(f"Generated {lines} lines.")
        except Exception as e:
            self.status_label.setText(f"Error: {e}")

    def _save(self):
        path = self.out_path_edit.text().strip()
        if not path:
            self._browse_output()
            path = self.out_path_edit.text().strip()
        if not path:
            return
        try:
            with open(path, "w") as f:
                f.write(self.editor.toPlainText())
            self.status_label.setText(f"Saved: {path}")
        except Exception as e:
            self.status_label.setText(f"Save failed: {e}")

    def set_derived(self, d: DerivedQuantities):
        self._derived = d
        # Auto-set default output path if blank
        if not self.out_path_edit.text():
            self.out_path_edit.setText(f"{self.bus.state.case_name}.in")
