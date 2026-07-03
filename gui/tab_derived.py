"""Derived Quantities tab — live computed display of all DSMC-relevant quantities."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QScrollArea,
    QDoubleSpinBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from .widgets import ResultBox, section_label, hline
from .state import AppStateSignals
from .engine import DerivedQuantities


def _fmt(v, fmt=".4e", fallback="—") -> str:
    try:
        return format(v, fmt)
    except Exception:
        return fallback


class DerivedTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._setup_ui()
        self._last: DerivedQuantities = DerivedQuantities()

    def _setup_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        vl = QVBoxLayout(inner)
        vl.setSpacing(12)
        vl.setContentsMargins(16, 16, 16, 16)

        # L_ref for Knudsen number
        hl_lref = QHBoxLayout()
        hl_lref.addWidget(QLabel("Reference length  L_ref:"))
        self.lref_spin = QDoubleSpinBox()
        self.lref_spin.setRange(1e-9, 100.0)
        self.lref_spin.setDecimals(6)
        self.lref_spin.setSingleStep(0.001)
        self.lref_spin.setValue(0.025)
        self.lref_spin.setToolTip("Used to compute Kn = λ / L_ref")
        hl_lref.addWidget(self.lref_spin)
        hl_lref.addWidget(QLabel("m"))
        hl_lref.addStretch()
        vl.addLayout(hl_lref)
        self.lref_spin.valueChanged.connect(self._request_refresh)

        # Error banner
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; font-weight: bold;")
        self.error_label.setWordWrap(True)
        vl.addWidget(self.error_label)

        # --- Flow properties ---
        self.flow_box = ResultBox("Flow Properties")
        for key, lbl, unit in [
            ("mach",   "Mach number  M∞",          ""),
            ("a",      "Speed of sound  a∞",        "m/s"),
            ("gamma",  "γ_mix (classical)",          ""),
            ("n_free", "Number density  n∞",         "m⁻³"),
            ("P_free", "Pressure  P∞",               "Pa"),
            ("T_free", "Temperature  T∞",            "K"),
            ("rho",    "Density  ρ∞",                "kg/m³"),
        ]:
            self.flow_box.set_row(key, lbl, "—", unit)
        vl.addWidget(self.flow_box)

        # --- DSMC quantities ---
        self.dsmc_box = ResultBox("DSMC Quantities (Freestream)")
        for key, lbl, unit in [
            ("mfp_free",  "Mean free path  λ∞",         "m"),
            ("tau_free",  "Mean collision time  τ∞",     "s"),
            ("kn_free",   "Knudsen number  Kn∞",         ""),
        ]:
            self.dsmc_box.set_row(key, lbl, "—", unit)
        vl.addWidget(self.dsmc_box)

        # --- Normal shock ---
        self.shock_box = ResultBox("Normal Shock (Rankine-Hugoniot, frozen comp.)")
        for key, lbl, unit in [
            ("T_shock",   "Temperature  T₂",             "K"),
            ("P_shock",   "Pressure  P₂",                "Pa"),
            ("rho_shock", "Density  ρ₂",                 "kg/m³"),
            ("u_shock",   "Velocity  u₂",                "m/s"),
            ("n_shock",   "Number density  n₂",          "m⁻³"),
            ("mfp_shock", "Mean free path  λ₂",          "m"),
            ("tau_shock", "Mean collision time  τ₂",     "s"),
            ("kn_shock",  "Knudsen number  Kn₂",         ""),
        ]:
            self.shock_box.set_row(key, lbl, "—", unit)
        vl.addWidget(self.shock_box)

        # --- Timestep & schedule ---
        self.dt_box = ResultBox("Timestep & Simulation Schedule")
        for key, lbl, unit in [
            ("dt_rec",    "Recommended dt  (0.1 τ₂)",    "s"),
            ("dt_cons",   "Conservative dt (0.01 τ₂)",   "s"),
            ("ftt",       "Flow-through time",            "s"),
            ("fnum",      "fnum (real/simulated)",        ""),
            ("warmup",    "Warmup steps",                 ""),
            ("total",     "Total steps",                  ""),
        ]:
            self.dt_box.set_row(key, lbl, "—", unit)
        vl.addWidget(self.dt_box)

        # --- Grid check ---
        self.grid_box = ResultBox("Grid Quality")
        for key, lbl, unit in [
            ("n_cells",   "Total cells",                  ""),
            ("dx",        "Cell size Δx",                 "m"),
            ("dy",        "Cell size Δy",                 "m"),
            ("dx_mfp",    "Δx / λ∞",                      ""),
            ("dy_mfp",    "Δy / λ∞",                      ""),
        ]:
            self.grid_box.set_row(key, lbl, "—", unit)
        vl.addWidget(self.grid_box)

        # --- Collision frequency table ---
        cf_group = QGroupBox("Pair Collision Frequencies (freestream)")
        cf_vl = QVBoxLayout(cf_group)
        self.cf_table = QTableWidget(0, 3)
        self.cf_table.setHorizontalHeaderLabels(["Pair", "ν_AB (s⁻¹)", ""])
        self.cf_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.cf_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.cf_table.setMaximumHeight(180)
        cf_vl.addWidget(self.cf_table)
        vl.addWidget(cf_group)

        vl.addStretch()

    # ── Public update method ──────────────────────────────────────────────────

    def update(self, d: DerivedQuantities):
        self._last = d

        if d.error:
            self.error_label.setText(f"⚠  {d.error}")
        else:
            self.error_label.setText("")

        fs = self.bus.state.freestream

        # Flow
        self.flow_box.set_row("mach",   "Mach number  M∞",        _fmt(d.mach, ".4f"))
        self.flow_box.set_row("a",      "Speed of sound  a∞",     _fmt(d.speed_of_sound, ".2f"), "m/s")
        self.flow_box.set_row("gamma",  "γ_mix (classical)",       _fmt(d.gamma_mix, ".4f"))
        self.flow_box.set_row("n_free", "Number density  n∞",      _fmt(d.n_free), "m⁻³")
        self.flow_box.set_row("P_free", "Pressure  P∞",            _fmt(fs.pressure or (d.n_free * 1.380649e-23 * fs.temperature)), "Pa")
        self.flow_box.set_row("T_free", "Temperature  T∞",         _fmt(fs.temperature, ".1f"), "K")
        self.flow_box.set_row("rho",    "Density  ρ∞",             _fmt(fs.density), "kg/m³")

        # DSMC freestream
        self.dsmc_box.set_row("mfp_free", "Mean free path  λ∞",      _fmt(d.mfp_free), "m")
        self.dsmc_box.set_row("tau_free", "Mean collision time  τ∞",  _fmt(d.tau_free), "s")
        self.dsmc_box.set_row("kn_free",  "Knudsen number  Kn∞",      _fmt(d.kn_free, ".4e"))

        # Normal shock
        self.shock_box.set_row("T_shock",   "Temperature  T₂",    _fmt(d.T_shock, ".1f") if d.T_shock else "M∞ ≤ 1", "K")
        self.shock_box.set_row("P_shock",   "Pressure  P₂",        _fmt(d.P_shock) if d.P_shock else "—", "Pa")
        self.shock_box.set_row("rho_shock", "Density  ρ₂",         _fmt(d.rho_shock) if d.rho_shock else "—", "kg/m³")
        self.shock_box.set_row("u_shock",   "Velocity  u₂",        _fmt(d.u_shock, ".2f") if d.u_shock else "—", "m/s")
        self.shock_box.set_row("n_shock",   "Number density  n₂",  _fmt(d.n_shock) if d.n_shock else "—", "m⁻³")
        self.shock_box.set_row("mfp_shock", "Mean free path  λ₂",  _fmt(d.mfp_shock) if d.mfp_shock else "—", "m")
        self.shock_box.set_row("tau_shock", "Mean coll. time  τ₂", _fmt(d.tau_shock) if d.tau_shock else "—", "s")
        self.shock_box.set_row("kn_shock",  "Knudsen number  Kn₂", _fmt(d.kn_shock) if d.kn_shock else "—")

        # Schedule
        self.dt_box.set_row("dt_rec",  "Recommended dt  (0.1 τ₂)",  _fmt(d.dt_recommended), "s")
        self.dt_box.set_row("dt_cons", "Conservative dt (0.01 τ₂)", _fmt(d.dt_conservative), "s")
        self.dt_box.set_row("ftt",     "Flow-through time",          _fmt(d.flow_through_time), "s")
        self.dt_box.set_row("fnum",    "fnum (real/simulated)",      _fmt(d.fnum))
        self.dt_box.set_row("warmup",  "Warmup steps",               str(d.warmup_steps))
        self.dt_box.set_row("total",   "Total steps",                str(d.total_steps))

        # Grid
        self.grid_box.set_row("n_cells", "Total cells",   str(d.n_cells))
        self.grid_box.set_row("dx",      "Cell size Δx",  _fmt(d.grid_dx), "m")
        self.grid_box.set_row("dy",      "Cell size Δy",  _fmt(d.grid_dy), "m")
        if d.mfp_free > 0:
            self.grid_box.set_row("dx_mfp", "Δx / λ∞", _fmt(d.grid_dx / d.mfp_free, ".2f"))
            self.grid_box.set_row("dy_mfp", "Δy / λ∞", _fmt(d.grid_dy / d.mfp_free, ".2f"))

        # Collision freq table
        self.cf_table.setRowCount(0)
        for pair, freq in d.collision_freqs.items():
            row = self.cf_table.rowCount()
            self.cf_table.insertRow(row)
            self.cf_table.setItem(row, 0, QTableWidgetItem(pair))
            item = QTableWidgetItem(_fmt(freq))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cf_table.setItem(row, 1, item)

    def _request_refresh(self):
        self.bus.notify()

    def get_lref(self) -> float:
        return self.lref_spin.value()
