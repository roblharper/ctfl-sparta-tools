"""Physics tab — collision model, rotation, vibration, chemistry."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QCheckBox, QDoubleSpinBox, QPushButton, QScrollArea, QLineEdit,
    QFileDialog,
)
from PySide6.QtCore import Qt

from .widgets import ScientificSpinBox, section_label, hline, LabeledField
from .state import AppStateSignals


class PhysicsTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._setup_ui()
        self._connect()
        self._refresh_visibility()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        layout.addWidget(self._build_collision())
        layout.addWidget(self._build_internal_energy())
        layout.addWidget(self._build_chemistry())
        layout.addStretch()

    def _build_collision(self) -> QGroupBox:
        box = QGroupBox("Collision Model")
        vl = QVBoxLayout(box)

        hl = QHBoxLayout()
        hl.addWidget(QLabel("Collision style:"))
        self.collide_combo = QComboBox()
        self.collide_combo.addItems(["vss", "none"])
        self.collide_combo.setCurrentText(self.bus.state.physics.collision_model)
        self.collide_combo.setToolTip("VSS with α=1.0 behaves identically to VHS")
        hl.addWidget(self.collide_combo)
        hl.addStretch()
        vl.addLayout(hl)

        self.alpha_spin = QDoubleSpinBox()
        self.alpha_spin.setRange(0.5, 2.0)
        self.alpha_spin.setSingleStep(0.05)
        self.alpha_spin.setDecimals(3)
        self.alpha_spin.setValue(self.bus.state.physics.alpha)
        self.alpha_spin.setToolTip("VSS scattering parameter α. α=1.0 → VHS behaviour.")
        vl.addWidget(LabeledField("VSS alpha (α)", self.alpha_spin))

        return box

    def _build_internal_energy(self) -> QGroupBox:
        box = QGroupBox("Internal Energy Exchange")
        vl = QVBoxLayout(box)

        # Rotation
        rot_label = section_label("Rotation")
        vl.addWidget(rot_label)

        hl_rot = QHBoxLayout()
        hl_rot.addWidget(QLabel("rotate:"))
        self.rotate_combo = QComboBox()
        self.rotate_combo.addItems(["smooth", "no"])
        self.rotate_combo.setCurrentText(self.bus.state.physics.rotate)
        self.rotate_combo.setToolTip("smooth: stochastic rotational energy exchange per collision")
        hl_rot.addWidget(self.rotate_combo)
        hl_rot.addStretch()
        vl.addLayout(hl_rot)

        hl_rotrel = QHBoxLayout()
        hl_rotrel.addWidget(QLabel("Rotational collision number model:"))
        self.rot_relax_combo = QComboBox()
        self.rot_relax_combo.addItems(["parker", "constant"])
        self.rot_relax_combo.setCurrentText(self.bus.state.physics.rot_relax_model)
        self.rot_relax_combo.setToolTip(
            "parker: Z_rot(T) via Parker model (per-cell temperature)\n"
            "constant: fixed Z_rot from species.rotrel"
        )
        hl_rotrel.addWidget(self.rot_relax_combo)
        hl_rotrel.addStretch()
        vl.addLayout(hl_rotrel)

        self.use_cell_temp_check = QCheckBox("Use cell temperature for Parker / Z_vib (usecelltemperature)")
        self.use_cell_temp_check.setChecked(self.bus.state.physics.use_cell_temperature)
        vl.addWidget(self.use_cell_temp_check)

        vl.addWidget(hline())

        # Vibration
        vib_label = section_label("Vibration")
        vl.addWidget(vib_label)

        hl_vib = QHBoxLayout()
        hl_vib.addWidget(QLabel("vibrate:"))
        self.vibrate_combo = QComboBox()
        self.vibrate_combo.addItems(["discrete", "smooth", "no"])
        self.vibrate_combo.setCurrentText(self.bus.state.physics.vibrate)
        self.vibrate_combo.setToolTip(
            "discrete: quantised SHO vibrational energy (recommended for hypersonic air)\n"
            "smooth: continuous energy exchange\n"
            "no: vibrational modes frozen"
        )
        hl_vib.addWidget(self.vibrate_combo)
        hl_vib.addStretch()
        vl.addLayout(hl_vib)

        hl_vibrel = QHBoxLayout()
        hl_vibrel.addWidget(QLabel("Vibrational relaxation model:"))
        self.vib_relax_combo = QComboBox()
        self.vib_relax_combo.addItems(["MW", "MWHTP", "MWHTHB", "BIRD", "constant"])
        self.vib_relax_combo.setCurrentText(self.bus.state.physics.vib_relax_model)
        self.vib_relax_combo.setToolTip(
            "MW: Millikan-White (standard)\n"
            "MWHTP: MW + Park high-T correction\n"
            "MWHTHB: MW + Haas-Boyd high-T correction\n"
            "BIRD: Bird's model\n"
            "constant: fixed Z_vib from species.vibrel"
        )
        hl_vibrel.addWidget(self.vib_relax_combo)
        hl_vibrel.addStretch()
        vl.addLayout(hl_vibrel)

        return box

    def _build_chemistry(self) -> QGroupBox:
        box = QGroupBox("Chemistry / Reactions")
        vl = QVBoxLayout(box)

        self.react_check = QCheckBox("Enable chemistry (react command)")
        self.react_check.setChecked(self.bus.state.physics.react_enabled)
        vl.addWidget(self.react_check)

        hl_style = QHBoxLayout()
        hl_style.addWidget(QLabel("Reaction style:"))
        self.react_style_combo = QComboBox()
        self.react_style_combo.addItems(["tce", "qk", "none"])
        self.react_style_combo.setCurrentText(self.bus.state.physics.react_style)
        hl_style.addWidget(self.react_style_combo)
        hl_style.addStretch()
        vl.addLayout(hl_style)

        hl_file = QHBoxLayout()
        hl_file.addWidget(QLabel("Reaction file:"))
        self.react_file_edit = QLineEdit(self.bus.state.physics.react_file)
        hl_file.addWidget(self.react_file_edit)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_react_file)
        hl_file.addWidget(browse)
        vl.addLayout(hl_file)

        note = QLabel("  Supported: .chem / .react files in CTFL group format")
        note.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(note)

        self._react_widgets = [self.react_style_combo, self.react_file_edit, browse, note]

        return box

    # ── Actions ──────────────────────────────────────────────────────────────

    def _browse_react_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select reaction file", "",
            "Reaction files (*.chem *.react *.tce *.qk);;All files (*)"
        )
        if path:
            self.react_file_edit.setText(path)
            self.bus.state.physics.react_file = path

    def _refresh_visibility(self):
        react_on = self.react_check.isChecked()
        for w in self._react_widgets:
            w.setEnabled(react_on)

        rot_on = self.rotate_combo.currentText() != "no"
        self.rot_relax_combo.setEnabled(rot_on)
        self.use_cell_temp_check.setEnabled(rot_on)

    # ── Connections ───────────────────────────────────────────────────────────

    def _connect(self):
        self.collide_combo.currentTextChanged.connect(self._on_change)
        self.alpha_spin.valueChanged.connect(self._on_change)
        self.rotate_combo.currentTextChanged.connect(self._on_change)
        self.rot_relax_combo.currentTextChanged.connect(self._on_change)
        self.use_cell_temp_check.toggled.connect(self._on_change)
        self.vibrate_combo.currentTextChanged.connect(self._on_change)
        self.vib_relax_combo.currentTextChanged.connect(self._on_change)
        self.react_check.toggled.connect(self._on_change)
        self.react_style_combo.currentTextChanged.connect(self._on_change)
        self.react_file_edit.editingFinished.connect(self._on_change)

    def _on_change(self):
        ph = self.bus.state.physics
        ph.collision_model = self.collide_combo.currentText()
        ph.alpha = self.alpha_spin.value()
        ph.rotate = self.rotate_combo.currentText()
        ph.rot_relax_model = self.rot_relax_combo.currentText()
        ph.use_cell_temperature = self.use_cell_temp_check.isChecked()
        ph.vibrate = self.vibrate_combo.currentText()
        ph.vib_relax_model = self.vib_relax_combo.currentText()
        ph.react_enabled = self.react_check.isChecked()
        ph.react_style = self.react_style_combo.currentText()
        ph.react_file = self.react_file_edit.text()
        self._refresh_visibility()
        self.bus.notify()
