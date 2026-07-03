"""Computes/Dumps tab — defines compute quantities, averaging window, dumps, and stats."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QCheckBox,
    QSpinBox, QLineEdit, QScrollArea, QComboBox, QFrame,
)
from PySide6.QtCore import Qt

from .state import AppStateSignals, ComputeDumpState


class ComputesTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._loading = False
        self._setup_ui()
        self._connect()
        self._refresh_from_state()

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

        layout.addWidget(self._build_averaging())
        layout.addWidget(self._build_grid_quantities())
        layout.addWidget(self._build_surf_quantities())
        layout.addWidget(self._build_stats())
        layout.addWidget(self._build_dumps())
        layout.addStretch()

    # ── Group boxes ───────────────────────────────────────────────────────────

    def _build_averaging(self) -> QGroupBox:
        box = QGroupBox("Averaging Window  (fix ave/grid, fix ave/surf)")
        vl = QVBoxLayout(box)

        cd = self.bus.state.compute_dump

        hl1 = QHBoxLayout()
        hl1.addWidget(QLabel("Nevery:"))
        self.nevery_spin = QSpinBox()
        self.nevery_spin.setRange(1, 1_000_000)
        self.nevery_spin.setValue(self.bus.state.simulation.ave_nevery)
        self.nevery_spin.setToolTip("Sample every N timesteps")
        hl1.addWidget(self.nevery_spin)

        hl1.addSpacing(16)
        hl1.addWidget(QLabel("Nrepeat:"))
        self.nrepeat_spin = QSpinBox()
        self.nrepeat_spin.setRange(1, 10_000_000)
        self.nrepeat_spin.setSingleStep(1000)
        self.nrepeat_spin.setValue(self.bus.state.simulation.ave_nrepeat)
        self.nrepeat_spin.setToolTip("Number of samples to accumulate per output")
        hl1.addWidget(self.nrepeat_spin)

        hl1.addSpacing(16)
        hl1.addWidget(QLabel("Nfreq:"))
        self.nfreq_spin = QSpinBox()
        self.nfreq_spin.setRange(1, 100_000_000)
        self.nfreq_spin.setSingleStep(10000)
        self.nfreq_spin.setValue(self.bus.state.simulation.ave_nfreq)
        self.nfreq_spin.setToolTip("How often to write output (steps); should equal Nevery × Nrepeat")
        hl1.addWidget(self.nfreq_spin)
        hl1.addStretch()
        vl.addLayout(hl1)

        self.ave_info_label = QLabel("")
        self.ave_info_label.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(self.ave_info_label)
        self._update_ave_info()

        return box

    def _build_grid_quantities(self) -> QGroupBox:
        box = QGroupBox("Grid Compute Quantities  (compute … grid all all …)")
        vl = QVBoxLayout(box)

        cd = self.bus.state.compute_dump
        self._grid_checks: dict[str, QCheckBox] = {}

        defs = [
            ("grid_n",     "n",     "Number density per cell"),
            ("grid_nrho",  "nrho",  "Mass density per cell"),
            ("grid_u",     "u",     "x-velocity"),
            ("grid_v",     "v",     "y-velocity"),
            ("grid_w",     "w",     "z-velocity"),
            ("grid_temp",  "temp",  "Translational temperature"),
            ("grid_trot",  "trot",  "Rotational temperature"),
            ("grid_tvib",  "tvib",  "Vibrational temperature"),
            ("grid_erot",  "erot",  "Rotational energy"),
            ("grid_evib",  "evib",  "Vibrational energy"),
            ("grid_press", "press", "Pressure"),
            ("grid_ke",    "ke",    "Kinetic energy"),
        ]

        row_layout = QHBoxLayout()
        col_count = 0
        col_vl = QVBoxLayout()
        for attr, label, tip in defs:
            cb = QCheckBox(label)
            cb.setChecked(getattr(cd, attr))
            cb.setToolTip(tip)
            self._grid_checks[attr] = cb
            col_vl.addWidget(cb)
            col_count += 1
            if col_count == 6:
                row_layout.addLayout(col_vl)
                col_vl = QVBoxLayout()
        row_layout.addLayout(col_vl)
        row_layout.addStretch()
        vl.addLayout(row_layout)

        return box

    def _build_surf_quantities(self) -> QGroupBox:
        box = QGroupBox("Surface Compute Quantities  (compute … surf all all …)  — active when surface file is set")
        vl = QVBoxLayout(box)

        cd = self.bus.state.compute_dump
        self._surf_checks: dict[str, QCheckBox] = {}

        defs = [
            ("surf_n",     "n",     "Particle flux (number)"),
            ("surf_press", "press", "Pressure"),
            ("surf_ke",    "ke",    "Kinetic energy flux"),
            ("surf_erot",  "erot",  "Rotational energy flux"),
            ("surf_evib",  "evib",  "Vibrational energy flux"),
            ("surf_etot",  "etot",  "Total energy flux"),
        ]

        hl = QHBoxLayout()
        for attr, label, tip in defs:
            cb = QCheckBox(label)
            cb.setChecked(getattr(cd, attr))
            cb.setToolTip(tip)
            self._surf_checks[attr] = cb
            hl.addWidget(cb)
        hl.addStretch()
        vl.addLayout(hl)

        return box

    def _build_stats(self) -> QGroupBox:
        box = QGroupBox("Stats Output")
        vl = QVBoxLayout(box)

        cd = self.bus.state.compute_dump

        hl1 = QHBoxLayout()
        hl1.addWidget(QLabel("stats every N steps:"))
        self.stats_nevery_spin = QSpinBox()
        self.stats_nevery_spin.setRange(1, 1_000_000)
        self.stats_nevery_spin.setValue(cd.stats_nevery)
        hl1.addWidget(self.stats_nevery_spin)
        hl1.addStretch()
        vl.addLayout(hl1)

        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("stats_style fields:"))
        self.stats_fields_edit = QLineEdit(cd.stats_fields)
        self.stats_fields_edit.setToolTip(
            "Space-separated list of stats keywords: step, elapsed, np, ncoll, nattempt, nreact, ..."
        )
        hl2.addWidget(self.stats_fields_edit)
        vl.addLayout(hl2)

        return box

    def _build_dumps(self) -> QGroupBox:
        box = QGroupBox("Dump Files")
        vl = QVBoxLayout(box)

        cd = self.bus.state.compute_dump

        hl_grid = QHBoxLayout()
        hl_grid.addWidget(QLabel("Grid dump file:"))
        self.grid_dump_edit = QLineEdit(cd.grid_dump_file)
        self.grid_dump_edit.setToolTip("Use * for timestep wildcard: grid.*.dat")
        hl_grid.addWidget(self.grid_dump_edit)
        vl.addLayout(hl_grid)

        hl_surf = QHBoxLayout()
        hl_surf.addWidget(QLabel("Surf dump file:"))
        self.surf_dump_edit = QLineEdit(cd.surf_dump_file)
        self.surf_dump_edit.setToolTip("Use * for timestep wildcard: surf.*.dat")
        hl_surf.addWidget(self.surf_dump_edit)
        vl.addLayout(hl_surf)

        # particle dump
        hl_part_top = QHBoxLayout()
        self.particle_dump_check = QCheckBox("Enable particle dump")
        self.particle_dump_check.setChecked(cd.particle_dump_enabled)
        hl_part_top.addWidget(self.particle_dump_check)
        hl_part_top.addStretch()
        vl.addLayout(hl_part_top)

        self._particle_dump_row = QWidget()
        hl_part = QHBoxLayout(self._particle_dump_row)
        hl_part.setContentsMargins(0, 0, 0, 0)
        hl_part.addWidget(QLabel("  Particle dump file:"))
        self.particle_dump_edit = QLineEdit(cd.particle_dump_file)
        hl_part.addWidget(self.particle_dump_edit)
        hl_part.addWidget(QLabel("  Every N steps:"))
        self.particle_dump_nevery_spin = QSpinBox()
        self.particle_dump_nevery_spin.setRange(0, 100_000_000)
        self.particle_dump_nevery_spin.setSingleStep(1000)
        self.particle_dump_nevery_spin.setValue(cd.particle_dump_nevery)
        self.particle_dump_nevery_spin.setToolTip("0 = use Nfreq")
        hl_part.addWidget(self.particle_dump_nevery_spin)
        hl_part.addStretch()
        vl.addWidget(self._particle_dump_row)
        self._particle_dump_row.setVisible(cd.particle_dump_enabled)

        return box

    # ── Connections ───────────────────────────────────────────────────────────

    def _connect(self):
        self.nevery_spin.valueChanged.connect(self._on_averaging)
        self.nrepeat_spin.valueChanged.connect(self._on_averaging)
        self.nfreq_spin.valueChanged.connect(self._on_averaging)

        for attr, cb in self._grid_checks.items():
            cb.stateChanged.connect(self._on_grid_checks)
        for attr, cb in self._surf_checks.items():
            cb.stateChanged.connect(self._on_surf_checks)

        self.stats_nevery_spin.valueChanged.connect(self._on_stats)
        self.stats_fields_edit.editingFinished.connect(self._on_stats)

        self.grid_dump_edit.editingFinished.connect(self._on_dumps)
        self.surf_dump_edit.editingFinished.connect(self._on_dumps)
        self.particle_dump_check.stateChanged.connect(self._on_particle_toggle)
        self.particle_dump_edit.editingFinished.connect(self._on_dumps)
        self.particle_dump_nevery_spin.valueChanged.connect(self._on_dumps)

    def _on_averaging(self):
        if self._loading:
            return
        sim = self.bus.state.simulation
        sim.ave_nevery = self.nevery_spin.value()
        sim.ave_nrepeat = self.nrepeat_spin.value()
        sim.ave_nfreq = self.nfreq_spin.value()
        self._update_ave_info()
        self.bus.notify()

    def _update_ave_info(self):
        nevery = self.nevery_spin.value()
        nrepeat = self.nrepeat_spin.value()
        nfreq = self.nfreq_spin.value()
        prod = nevery * nrepeat
        warn = " ⚠ Nfreq ≠ Nevery×Nrepeat" if nfreq != prod else ""
        self.ave_info_label.setText(
            f"  Production steps per dump: Nevery×Nrepeat = {prod:,}{warn}"
        )

    def _on_grid_checks(self):
        if self._loading:
            return
        cd = self.bus.state.compute_dump
        for attr, cb in self._grid_checks.items():
            setattr(cd, attr, cb.isChecked())
        self.bus.notify()

    def _on_surf_checks(self):
        if self._loading:
            return
        cd = self.bus.state.compute_dump
        for attr, cb in self._surf_checks.items():
            setattr(cd, attr, cb.isChecked())
        self.bus.notify()

    def _on_stats(self):
        if self._loading:
            return
        cd = self.bus.state.compute_dump
        cd.stats_nevery = self.stats_nevery_spin.value()
        cd.stats_fields = self.stats_fields_edit.text().strip()
        self.bus.notify()

    def _on_dumps(self):
        if self._loading:
            return
        cd = self.bus.state.compute_dump
        cd.grid_dump_file = self.grid_dump_edit.text().strip()
        cd.surf_dump_file = self.surf_dump_edit.text().strip()
        cd.particle_dump_file = self.particle_dump_edit.text().strip()
        cd.particle_dump_nevery = self.particle_dump_nevery_spin.value()
        self.bus.notify()

    def _on_particle_toggle(self):
        if self._loading:
            return
        enabled = self.particle_dump_check.isChecked()
        self.bus.state.compute_dump.particle_dump_enabled = enabled
        self._particle_dump_row.setVisible(enabled)
        self.bus.notify()

    # ── Public: called from mainwindow._rebuild_ui_from_state ─────────────────

    def refresh_from_state(self):
        self._loading = True
        sim = self.bus.state.simulation
        cd = self.bus.state.compute_dump

        self.nevery_spin.setValue(sim.ave_nevery)
        self.nrepeat_spin.setValue(sim.ave_nrepeat)
        self.nfreq_spin.setValue(sim.ave_nfreq)

        for attr, cb in self._grid_checks.items():
            cb.setChecked(getattr(cd, attr))
        for attr, cb in self._surf_checks.items():
            cb.setChecked(getattr(cd, attr))

        self.stats_nevery_spin.setValue(cd.stats_nevery)
        self.stats_fields_edit.setText(cd.stats_fields)
        self.grid_dump_edit.setText(cd.grid_dump_file)
        self.surf_dump_edit.setText(cd.surf_dump_file)
        self.particle_dump_check.setChecked(cd.particle_dump_enabled)
        self.particle_dump_edit.setText(cd.particle_dump_file)
        self.particle_dump_nevery_spin.setValue(cd.particle_dump_nevery)
        self._particle_dump_row.setVisible(cd.particle_dump_enabled)

        self._loading = False
        self._update_ave_info()

    def _refresh_from_state(self):
        self.refresh_from_state()
