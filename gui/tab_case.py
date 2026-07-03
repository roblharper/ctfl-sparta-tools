"""Case tab — freestream conditions, mixture, wall settings."""

import os
import sys
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QMessageBox, QScrollArea, QFrame, QSpinBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from .widgets import ScientificSpinBox, section_label, hline, LabeledField
from .state import AppStateSignals, MixtureEntry

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


class CaseTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._loading = False
        self._setup_ui()
        self._connect()

    # ── UI setup ─────────────────────────────────────────────────────────────

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

        layout.addWidget(self._build_case_name())
        layout.addWidget(self._build_freestream())
        layout.addWidget(self._build_mixture())
        layout.addWidget(self._build_wall())
        layout.addWidget(self._build_simulation())
        layout.addStretch()

    def _build_case_name(self) -> QGroupBox:
        box = QGroupBox("Case")
        hl = QHBoxLayout(box)
        hl.addWidget(QLabel("Case name:"))
        self.case_name_edit = QLineEdit(self.bus.state.case_name)
        hl.addWidget(self.case_name_edit)
        return box

    def _build_freestream(self) -> QGroupBox:
        box = QGroupBox("Freestream Conditions")
        vl = QVBoxLayout(box)

        fs = self.bus.state.freestream

        self.vel_spin = ScientificSpinBox(fs.velocity)
        self.vel_spin.setMinimumWidth(160)
        vl.addWidget(LabeledField("Velocity  u∞", self.vel_spin, "m/s"))

        self.T_spin = ScientificSpinBox(fs.temperature)
        vl.addWidget(LabeledField("Temperature  T∞", self.T_spin, "K"))

        self.Tvib_spin = ScientificSpinBox(fs.t_vib)
        self.Tvib_spin.setToolTip("Vibrational temperature (K). Leave 0 to use T∞.")
        vl.addWidget(LabeledField("T_vib (0 = T∞)", self.Tvib_spin, "K"))

        vl.addWidget(hline())
        note = QLabel("Provide any two of: Density, Pressure, Temperature")
        note.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(note)

        self.rho_spin = ScientificSpinBox(fs.density)
        vl.addWidget(LabeledField("Density  ρ∞", self.rho_spin, "kg/m³"))

        self.P_spin = ScientificSpinBox(fs.pressure)
        self.P_spin.setToolTip("0 = derive from T and ρ")
        vl.addWidget(LabeledField("Pressure  P∞", self.P_spin, "Pa"))

        return box

    def _build_mixture(self) -> QGroupBox:
        box = QGroupBox("Gas Mixture")
        vl = QVBoxLayout(box)

        # Species file selector
        hl = QHBoxLayout()
        hl.addWidget(QLabel("Species database:"))
        self.species_file_edit = QLineEdit()
        default_db = os.path.join(_HERE, "species.json")
        self.species_file_edit.setText(default_db)
        self.bus.state.species_file = default_db
        hl.addWidget(self.species_file_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_species_file)
        hl.addWidget(browse_btn)
        vl.addLayout(hl)

        # Available species dropdown + add button
        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Add species:"))
        self.species_combo = QComboBox()
        self.species_combo.setMinimumWidth(120)
        hl2.addWidget(self.species_combo)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_species)
        hl2.addWidget(add_btn)
        hl2.addStretch()
        vl.addLayout(hl2)

        # Quick presets
        preset_hl = QHBoxLayout()
        preset_hl.addWidget(QLabel("Presets:"))
        for label, species_dict in [
            ("5-species air", {"N2": 0.79, "O2": 0.21, "N": 0.0, "O": 0.0, "NO": 0.0}),
            ("N2/O2 (78/22)", {"N2": 0.78, "O2": 0.22}),
            ("Pure N2", {"N2": 1.0}),
            ("Pure Ar", {"Ar": 1.0}),
        ]:
            btn = QPushButton(label)
            btn.setMaximumWidth(130)
            btn.clicked.connect(lambda checked, sd=species_dict: self._apply_preset(sd))
            preset_hl.addWidget(btn)
        preset_hl.addStretch()
        vl.addLayout(preset_hl)

        # Table of species + mole fractions
        self.mix_table = QTableWidget(0, 3)
        self.mix_table.setHorizontalHeaderLabels(["Species", "Mole Fraction", ""])
        self.mix_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.mix_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.mix_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.mix_table.setMaximumHeight(200)
        vl.addWidget(self.mix_table)

        self.frac_sum_label = QLabel("Sum: 0.000")
        vl.addWidget(self.frac_sum_label)

        self._load_species_combo()
        return box

    def _build_wall(self) -> QGroupBox:
        box = QGroupBox("Wall / Surface Boundary Conditions")
        vl = QVBoxLayout(box)

        wall = self.bus.state.wall

        self.Twall_spin = ScientificSpinBox(wall.temperature)
        vl.addWidget(LabeledField("Wall temperature  T_w", self.Twall_spin, "K"))

        self.accom_spin = QDoubleSpinBox()
        self.accom_spin.setRange(0.0, 1.0)
        self.accom_spin.setSingleStep(0.05)
        self.accom_spin.setDecimals(3)
        self.accom_spin.setValue(wall.accommodation)
        self.accom_spin.setToolTip("Accommodation coefficient (1.0 = fully diffuse)")
        vl.addWidget(LabeledField("Accommodation coeff.", self.accom_spin))

        return box

    def _build_simulation(self) -> QGroupBox:
        box = QGroupBox("Simulation Parameters")
        vl = QVBoxLayout(box)

        sim = self.bus.state.simulation

        self.n_ppc_spin = QSpinBox()
        self.n_ppc_spin.setRange(1, 10000)
        self.n_ppc_spin.setValue(sim.n_ppc)
        self.n_ppc_spin.setToolTip("Target particles per cell")
        vl.addWidget(LabeledField("Particles per cell", self.n_ppc_spin))

        self.dt_factor_spin = QDoubleSpinBox()
        self.dt_factor_spin.setRange(0.001, 1.0)
        self.dt_factor_spin.setSingleStep(0.01)
        self.dt_factor_spin.setDecimals(4)
        self.dt_factor_spin.setValue(sim.dt_factor)
        self.dt_factor_spin.setToolTip("dt = factor × τ_coll_shock")
        vl.addWidget(LabeledField("Timestep factor (× τ)", self.dt_factor_spin))

        self.warmup_spin = QDoubleSpinBox()
        self.warmup_spin.setRange(1.0, 100.0)
        self.warmup_spin.setSingleStep(1.0)
        self.warmup_spin.setDecimals(1)
        self.warmup_spin.setValue(sim.warmup_factor)
        vl.addWidget(LabeledField("Warmup (flow-through ×)", self.warmup_spin))

        self.fnum_override_edit = ScientificSpinBox(0.0)
        self.fnum_override_edit.setToolTip("Override fnum (0 = auto-compute)")
        vl.addWidget(LabeledField("fnum override (0=auto)", self.fnum_override_edit))

        note = QLabel("  Averaging window (Nevery, Nrepeat, Nfreq) and dump settings are in the Computes/Dumps tab.")
        note.setStyleSheet("color: gray; font-size: 10px;")
        note.setWordWrap(True)
        vl.addWidget(note)

        return box

    # ── Actions ──────────────────────────────────────────────────────────────

    def _browse_species_file(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select species.json", _HERE, "JSON (*.json)")
        if path:
            self.species_file_edit.setText(path)
            self.bus.state.species_file = path
            self._load_species_combo()

    def _load_species_combo(self):
        path = self.species_file_edit.text()
        if not os.path.isfile(path):
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self.species_combo.clear()
            for sp_id in sorted(data.keys()):
                self.species_combo.addItem(sp_id)
        except Exception:
            pass

    def _add_species(self):
        sp_id = self.species_combo.currentText()
        if not sp_id:
            return
        # check not already in table
        for row in range(self.mix_table.rowCount()):
            if self.mix_table.item(row, 0) and self.mix_table.item(row, 0).text() == sp_id:
                return
        row = self.mix_table.rowCount()
        self.mix_table.insertRow(row)
        self.mix_table.setItem(row, 0, QTableWidgetItem(sp_id))
        frac_item = QTableWidgetItem("0.0")
        frac_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.mix_table.setItem(row, 1, frac_item)
        del_btn = QPushButton("✕")
        del_btn.setMaximumWidth(30)
        del_btn.clicked.connect(lambda: self._remove_row(sp_id))
        self.mix_table.setCellWidget(row, 2, del_btn)
        self._sync_mix_from_table()

    def _apply_preset(self, species_dict: dict):
        self.mix_table.setRowCount(0)
        for sp_id, frac in species_dict.items():
            row = self.mix_table.rowCount()
            self.mix_table.insertRow(row)
            self.mix_table.setItem(row, 0, QTableWidgetItem(sp_id))
            frac_item = QTableWidgetItem(f"{frac:.4f}")
            frac_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.mix_table.setItem(row, 1, frac_item)
            del_btn = QPushButton("✕")
            del_btn.setMaximumWidth(30)
            sp_id_cap = sp_id
            del_btn.clicked.connect(lambda checked=False, s=sp_id_cap: self._remove_row(s))
            self.mix_table.setCellWidget(row, 2, del_btn)
        self._sync_mix_from_table()

    def _remove_row(self, sp_id: str):
        for row in range(self.mix_table.rowCount()):
            item = self.mix_table.item(row, 0)
            if item and item.text() == sp_id:
                self.mix_table.removeRow(row)
                break
        self._sync_mix_from_table()

    def _sync_mix_from_table(self):
        entries = []
        total = 0.0
        for row in range(self.mix_table.rowCount()):
            sp_item = self.mix_table.item(row, 0)
            frac_item = self.mix_table.item(row, 1)
            if sp_item and frac_item:
                try:
                    frac = float(frac_item.text())
                except ValueError:
                    frac = 0.0
                entries.append(MixtureEntry(sp_item.text(), frac))
                total += frac
        self.bus.state.species_list = entries
        self.frac_sum_label.setText(f"Sum: {total:.4f}")
        color = "green" if abs(total - 1.0) < 0.01 else "red"
        self.frac_sum_label.setStyleSheet(f"color: {color};")
        if not self._loading:
            self.bus.notify_species()

    # ── Signal connections ────────────────────────────────────────────────────

    def _connect(self):
        self.case_name_edit.editingFinished.connect(self._on_case_name)
        self.vel_spin.valueChanged.connect(self._on_freestream)
        self.T_spin.valueChanged.connect(self._on_freestream)
        self.Tvib_spin.valueChanged.connect(self._on_freestream)
        self.rho_spin.valueChanged.connect(self._on_freestream)
        self.P_spin.valueChanged.connect(self._on_freestream)
        self.Twall_spin.valueChanged.connect(self._on_wall)
        self.accom_spin.valueChanged.connect(self._on_wall)
        self.n_ppc_spin.valueChanged.connect(self._on_sim)
        self.dt_factor_spin.valueChanged.connect(self._on_sim)
        self.warmup_spin.valueChanged.connect(self._on_sim)
        self.fnum_override_edit.valueChanged.connect(self._on_sim)
        self.mix_table.cellChanged.connect(self._on_table_cell_changed)
        self.species_file_edit.editingFinished.connect(self._on_species_file_change)

    def _on_case_name(self):
        self.bus.state.case_name = self.case_name_edit.text().strip() or "new_case"

    def _on_freestream(self):
        fs = self.bus.state.freestream
        fs.velocity = self.vel_spin.value()
        fs.temperature = self.T_spin.value()
        fs.t_vib = self.Tvib_spin.value()
        fs.density = self.rho_spin.value()
        fs.pressure = self.P_spin.value()
        self.bus.notify()

    def _on_wall(self):
        wall = self.bus.state.wall
        wall.temperature = self.Twall_spin.value()
        wall.accommodation = self.accom_spin.value()
        self.bus.notify()

    def _on_sim(self):
        sim = self.bus.state.simulation
        sim.n_ppc = self.n_ppc_spin.value()
        sim.dt_factor = self.dt_factor_spin.value()
        sim.warmup_factor = self.warmup_spin.value()
        sim.fnum_override = self.fnum_override_edit.value()
        self.bus.notify()

    def _on_table_cell_changed(self, row, col):
        if not self._loading:
            self._sync_mix_from_table()

    def _on_species_file_change(self):
        path = self.species_file_edit.text()
        self.bus.state.species_file = path
        self._load_species_combo()
