"""Main application window."""

import os
import json
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QStatusBar, QPushButton, QLabel, QSplitter, QFileDialog, QMessageBox,
    QToolBar,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QFont

from .state import AppStateSignals
from .engine import compute, auto_grid
from .tab_case import CaseTab
from .tab_physics import PhysicsTab
from .tab_geometry import GeometryTab
from .tab_derived import DerivedTab
from .tab_writer import WriterTab
from .tab_computes import ComputesTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.bus = AppStateSignals()
        self._pending_recompute = False
        self._save_path: str = ""   # current file path; empty = never saved

        self.setWindowTitle("SPARTA DSMC Setup — ctfl-sparta-tools")
        self.resize(1100, 800)

        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

        # Debounced recompute — avoids thrashing while user types
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._recompute)

        self.bus.changed.connect(self._schedule_recompute)
        self.geo_tab.auto_grid_requested.connect(self._auto_grid)

        # Initial compute
        self._recompute()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_menu(self):
        mb = self.menuBar()
        file_menu = mb.addMenu("&File")

        new_act = QAction("&New Case", self)
        new_act.setShortcut(QKeySequence.New)
        new_act.triggered.connect(self._new_case)
        file_menu.addAction(new_act)

        open_act = QAction("&Open Case…", self)
        open_act.setShortcut(QKeySequence.Open)
        open_act.triggered.connect(self._open_case)
        file_menu.addAction(open_act)

        self._save_act = QAction("&Save Case", self)
        self._save_act.setShortcut(QKeySequence.Save)
        self._save_act.triggered.connect(self._save_case)
        file_menu.addAction(self._save_act)

        save_as_act = QAction("Save Case &As…", self)
        save_as_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_as_act.triggered.connect(self._save_case_as)
        file_menu.addAction(save_as_act)

        file_menu.addSeparator()
        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        tools_menu = mb.addMenu("&Tools")
        gen_act = QAction("Generate Input Script", self)
        gen_act.setShortcut("Ctrl+G")
        gen_act.triggered.connect(self._generate_and_switch)
        tools_menu.addAction(gen_act)

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        gen_btn = QPushButton("Generate .in")
        gen_btn.setToolTip("Generate SPARTA input script (Ctrl+G)")
        gen_btn.clicked.connect(self._generate_and_switch)
        tb.addWidget(gen_btn)

        tb.addSeparator()

        self.status_indicator = QLabel("  ○ not computed")
        self.status_indicator.setStyleSheet("color: gray;")
        tb.addWidget(self.status_indicator)

    def _build_central(self):
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        self.case_tab = CaseTab(self.bus)
        self.phys_tab = PhysicsTab(self.bus)
        self.geo_tab = GeometryTab(self.bus)
        self.computes_tab = ComputesTab(self.bus)
        self.derived_tab = DerivedTab(self.bus)
        self.writer_tab = WriterTab(self.bus)

        self.tabs.addTab(self.case_tab,      "Case")
        self.tabs.addTab(self.phys_tab,      "Physics")
        self.tabs.addTab(self.geo_tab,       "Geometry")
        self.tabs.addTab(self.computes_tab,  "Computes/Dumps")
        self.tabs.addTab(self.derived_tab,   "Derived Quantities")
        self.tabs.addTab(self.writer_tab,    "Input Writer")

        self.setCentralWidget(self.tabs)

    def _build_statusbar(self):
        sb = self.statusBar()
        self.sb_label = QLabel("Ready")
        sb.addWidget(self.sb_label)

    # ── Compute pipeline ──────────────────────────────────────────────────────

    def _schedule_recompute(self):
        self._timer.start()

    def _recompute(self):
        state = self.bus.state
        species_file = state.species_file
        if not species_file or not os.path.isfile(species_file):
            import os as _os
            species_file = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "species.json")

        L_ref = self.derived_tab.get_lref()
        derived = compute(state, species_file, L_ref=L_ref)

        self.derived_tab.update(derived)
        self.writer_tab.set_derived(derived)

        if derived.error:
            self.status_indicator.setText(f"  ✗ {derived.error[:60]}")
            self.status_indicator.setStyleSheet("color: red;")
            self.sb_label.setText(f"Error: {derived.error}")
        else:
            mfp = derived.mfp_free
            mach = derived.mach
            kn = derived.kn_free
            self.status_indicator.setText(
                f"  ✓  M={mach:.2f}  λ∞={mfp:.3e} m  Kn={kn:.3e}"
            )
            self.status_indicator.setStyleSheet("color: green;")
            self.sb_label.setText(
                f"Computed — M={mach:.2f}, λ∞={mfp:.3e} m, τ∞={derived.tau_free:.3e} s"
            )

            # Update grid info display
            dx_mfp = derived.grid_dx / mfp if mfp > 0 else 0
            dy_mfp = derived.grid_dy / mfp if mfp > 0 else 0
            self.geo_tab.update_grid_display(
                f"Δx={derived.grid_dx:.3e} m ({dx_mfp:.1f} λ)  "
                f"Δy={derived.grid_dy:.3e} m ({dy_mfp:.1f} λ)  "
                f"Total cells: {derived.n_cells:,}"
            )

    def _auto_grid(self):
        """Compute auto grid and apply to geometry tab."""
        state = self.bus.state
        species_file = state.species_file
        if not species_file or not os.path.isfile(species_file):
            import os as _os
            species_file = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "species.json")

        derived = compute(state, species_file, L_ref=self.derived_tab.get_lref())
        if derived.error or derived.mfp_free <= 0:
            self.sb_label.setText("Cannot auto-grid: " + (derived.error or "mfp is zero"))
            return

        n_mfp = state.geometry.n_mfp_per_cell
        nx, ny, nz = auto_grid(state, derived, n_mfp)
        self.geo_tab.apply_auto_grid(nx, ny, nz)
        self.sb_label.setText(f"Auto-grid: {nx}×{ny}×{nz} ({n_mfp:.1f} λ/cell)")

    def _generate_and_switch(self):
        self.writer_tab.regenerate()
        self.tabs.setCurrentWidget(self.writer_tab)

    # ── File I/O ──────────────────────────────────────────────────────────────

    def _new_case(self):
        from .state import AppState
        self.bus.state = AppState()
        self._save_path = ""
        self._rebuild_ui_from_state()
        self.setWindowTitle("SPARTA DSMC Setup — ctfl-sparta-tools")
        self.bus.notify()

    def _save_case(self):
        if self._save_path:
            self._write_case(self._save_path)
        else:
            self._save_case_as()

    def _save_case_as(self):
        default = self._save_path or f"{self.bus.state.case_name}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Case As", default, "Case files (*.json);;All files (*)"
        )
        if path:
            self._write_case(path)

    def _write_case(self, path: str):
        import dataclasses
        try:
            data = dataclasses.asdict(self.bus.state)
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self._save_path = path
            self.setWindowTitle(f"SPARTA DSMC Setup — {os.path.basename(path)}")
            self.sb_label.setText(f"Saved: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _open_case(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Case", "", "Case files (*.json);;All files (*)"
        )
        if not path:
            return
        try:
            with open(path) as f:
                data = json.load(f)
            self._apply_case_dict(data)
            self._save_path = path
            self.setWindowTitle(f"SPARTA DSMC Setup — {os.path.basename(path)}")
            self.sb_label.setText(f"Loaded: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Load failed", str(e))

    def _apply_case_dict(self, data: dict):
        """Re-hydrate AppState from a saved JSON dict."""
        from .state import (AppState, FreestreamState, WallState,
                             PhysicsState, GeometryState, SimulationState,
                             ComputeDumpState, MixtureEntry)

        state = AppState()
        self.bus.state = state

        def _fill(obj, d: dict):
            for k, v in d.items():
                if hasattr(obj, k) and not isinstance(v, (dict, list)):
                    setattr(obj, k, v)

        _fill(state, data)
        if "freestream" in data:
            _fill(state.freestream, data["freestream"])
        if "wall" in data:
            _fill(state.wall, data["wall"])
        if "physics" in data:
            _fill(state.physics, data["physics"])
        if "geometry" in data:
            _fill(state.geometry, data["geometry"])
        if "simulation" in data:
            _fill(state.simulation, data["simulation"])
        if "compute_dump" in data:
            _fill(state.compute_dump, data["compute_dump"])
        if "species_list" in data:
            state.species_list = [
                MixtureEntry(e["species_id"], e["mol_frac"])
                for e in data["species_list"]
            ]
        if "species_file" in data:
            state.species_file = data["species_file"]

        self._rebuild_ui_from_state()
        self.bus.notify()

    def _rebuild_ui_from_state(self):
        """Push current state back into all tab widgets."""
        state = self.bus.state
        fs = state.freestream

        ct = self.case_tab
        ct._loading = True
        ct.case_name_edit.setText(state.case_name)
        ct.vel_spin.setValue(fs.velocity)
        ct.T_spin.setValue(fs.temperature)
        ct.Tvib_spin.setValue(fs.t_vib)
        ct.rho_spin.setValue(fs.density)
        ct.P_spin.setValue(fs.pressure)
        ct.Twall_spin.setValue(state.wall.temperature)
        ct.accom_spin.setValue(state.wall.accommodation)
        ct.n_ppc_spin.setValue(state.simulation.n_ppc)
        ct.dt_factor_spin.setValue(state.simulation.dt_factor)
        ct.warmup_spin.setValue(state.simulation.warmup_factor)

        # Rebuild mix table
        ct.mix_table.setRowCount(0)
        for e in state.species_list:
            ct._loading = True
            row = ct.mix_table.rowCount()
            ct.mix_table.insertRow(row)
            from PySide6.QtWidgets import QTableWidgetItem, QPushButton
            from PySide6.QtCore import Qt
            ct.mix_table.setItem(row, 0, QTableWidgetItem(e.species_id))
            fi = QTableWidgetItem(f"{e.mol_frac:.4f}")
            fi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            ct.mix_table.setItem(row, 1, fi)
            del_btn = QPushButton("✕")
            del_btn.setMaximumWidth(30)
            sp_id = e.species_id
            del_btn.clicked.connect(lambda checked=False, s=sp_id: ct._remove_row(s))
            ct.mix_table.setCellWidget(row, 2, del_btn)
        ct._loading = False

        # Physics
        ph = state.physics
        pt = self.phys_tab
        pt.collide_combo.setCurrentText(ph.collision_model)
        pt.alpha_spin.setValue(ph.alpha)
        pt.rotate_combo.setCurrentText(ph.rotate)
        pt.rot_relax_combo.setCurrentText(ph.rot_relax_model)
        pt.use_cell_temp_check.setChecked(ph.use_cell_temperature)
        pt.vibrate_combo.setCurrentText(ph.vibrate)
        pt.vib_relax_combo.setCurrentText(ph.vib_relax_model)
        pt.react_check.setChecked(ph.react_enabled)
        pt.react_style_combo.setCurrentText(ph.react_style)
        pt.react_file_edit.setText(ph.react_file)

        # Geometry
        geo = state.geometry
        gt = self.geo_tab
        gt.dim_combo.setCurrentText(str(geo.dimension))
        gt.sym_combo.setCurrentText(geo.symmetry)
        gt.xlo.setValue(geo.xlo)
        gt.xhi.setValue(geo.xhi)
        gt.ylo.setValue(geo.ylo)
        gt.yhi.setValue(geo.yhi)
        gt.zlo.setValue(geo.zlo)
        gt.zhi.setValue(geo.zhi)
        gt.bc_x.setCurrentText(geo.boundary_x)
        gt.bc_y.setCurrentText(geo.boundary_y)
        gt.bc_z.setCurrentText(geo.boundary_z)
        gt.nx_spin.setValue(geo.n_cells_x)
        gt.ny_spin.setValue(geo.n_cells_y)
        gt.nz_spin.setValue(geo.n_cells_z)
        gt.surf_file_edit.setText(geo.surface_file)
        gt.surf_units_combo.setCurrentText(geo.surface_units)
        gt.surf_scale_spin.setValue(geo.surface_scale)
        gt.amr_cells_spin.setValue(state.simulation.n_cells_amr)
        gt.flow_vol_combo.setCurrentText(state.simulation.flow_volume_mode)
        gt.sparta_vol_spin.setValue(state.simulation.flow_volume_sparta)
        gt._update_flow_vol_row_visibility(state.simulation.flow_volume_mode)

        # Computes/Dumps
        self.computes_tab.refresh_from_state()
