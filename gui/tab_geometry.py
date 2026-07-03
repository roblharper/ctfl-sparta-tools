"""Geometry tab — domain box, grid, surface file."""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QComboBox,
    QPushButton, QScrollArea, QLineEdit, QFileDialog, QSpinBox,
    QDoubleSpinBox, QCheckBox, QTextEdit, QSizePolicy, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal

from .widgets import ScientificSpinBox, section_label, hline, LabeledField
from .state import AppStateSignals


class GeometryTab(QWidget):
    auto_grid_requested = Signal()

    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
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

        layout.addWidget(self._build_domain_type())
        layout.addWidget(self._build_bounds())
        layout.addWidget(self._build_boundary_conditions())
        layout.addWidget(self._build_grid())
        layout.addWidget(self._build_surface())
        layout.addWidget(self._build_fnum_helpers())
        layout.addStretch()

    def _build_domain_type(self) -> QGroupBox:
        box = QGroupBox("Domain Type")
        hl = QHBoxLayout(box)

        hl.addWidget(QLabel("Dimension:"))
        self.dim_combo = QComboBox()
        self.dim_combo.addItems(["2", "3"])
        hl.addWidget(self.dim_combo)

        hl.addWidget(QLabel("   Symmetry:"))
        self.sym_combo = QComboBox()
        self.sym_combo.addItems(["none", "axisymmetric"])
        self.sym_combo.setToolTip(
            "axisymmetric: sets lower-y boundary to 'a' (axi-symmetric, 2D only)"
        )
        hl.addWidget(self.sym_combo)
        hl.addStretch()
        return box

    def _build_bounds(self) -> QGroupBox:
        box = QGroupBox("Box Bounds  (metres)")
        vl = QVBoxLayout(box)

        geo = self.bus.state.geometry

        self.xlo = ScientificSpinBox(geo.xlo)
        self.xhi = ScientificSpinBox(geo.xhi)
        self.ylo = ScientificSpinBox(geo.ylo)
        self.yhi = ScientificSpinBox(geo.yhi)
        self.zlo = ScientificSpinBox(geo.zlo)
        self.zhi = ScientificSpinBox(geo.zhi)

        for label, lo, hi in [("X", self.xlo, self.xhi), ("Y", self.ylo, self.yhi), ("Z", self.zlo, self.zhi)]:
            row = QWidget()
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(QLabel(f"{label}lo:"))
            hl.addWidget(lo)
            hl.addWidget(QLabel(f"{label}hi:"))
            hl.addWidget(hi)
            hl.addStretch()
            vl.addWidget(row)

        self.zlo.setToolTip("For 2D simulations use a thin z-slab (e.g. −7.5e-5 to 7.5e-5)")
        self.zhi.setToolTip("For 2D simulations use a thin z-slab (e.g. −7.5e-5 to 7.5e-5)")

        note = QLabel("  Tip: for 2D set Z to ±7.5e-5 m (one cell thick at typical scale)")
        note.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(note)

        return box

    def _build_boundary_conditions(self) -> QGroupBox:
        box = QGroupBox("Boundary Conditions")
        vl = QVBoxLayout(box)

        choices = ["oo", "pp", "rr", "or", "op", "os", "p", "o", "r", "s", "a"]
        tip = (
            "o = outflow  |  p = periodic  |  r = specular  |  a = axi-symmetric (lower-y only)\n"
            "Two characters set lower/upper faces separately (e.g. 'oo' = both outflow)\n"
        )

        geo = self.bus.state.geometry
        self.bc_x = QComboBox()
        self.bc_x.setEditable(True)
        self.bc_x.addItems(choices)
        self.bc_x.setCurrentText(geo.boundary_x)
        self.bc_x.setToolTip(tip)

        self.bc_y = QComboBox()
        self.bc_y.setEditable(True)
        self.bc_y.addItems(choices)
        self.bc_y.setCurrentText(geo.boundary_y)
        self.bc_y.setToolTip(tip)

        self.bc_z = QComboBox()
        self.bc_z.setEditable(True)
        self.bc_z.addItems(["p", "oo", "o", "r"])
        self.bc_z.setCurrentText(geo.boundary_z)
        self.bc_z.setToolTip("Z is typically periodic (p) for 2D slab domains")

        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        for lbl, combo in [("X:", self.bc_x), ("Y:", self.bc_y), ("Z:", self.bc_z)]:
            hl.addWidget(QLabel(lbl))
            hl.addWidget(combo)
            hl.addSpacing(12)
        hl.addStretch()
        vl.addWidget(row)

        note = QLabel("  boundary x y z — two chars set lo/hi faces; single char applies to both")
        note.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(note)
        return box

    def _build_grid(self) -> QGroupBox:
        box = QGroupBox("Grid")
        vl = QVBoxLayout(box)

        geo = self.bus.state.geometry

        self.nx_spin = QSpinBox()
        self.nx_spin.setRange(1, 100000)
        self.nx_spin.setValue(geo.n_cells_x)
        vl.addWidget(LabeledField("Cells X", self.nx_spin))

        self.ny_spin = QSpinBox()
        self.ny_spin.setRange(1, 100000)
        self.ny_spin.setValue(geo.n_cells_y)
        vl.addWidget(LabeledField("Cells Y", self.ny_spin))

        self.nz_spin = QSpinBox()
        self.nz_spin.setRange(1, 100000)
        self.nz_spin.setValue(geo.n_cells_z)
        self.nz_spin.setToolTip("Set to 1 for 2D simulations")
        vl.addWidget(LabeledField("Cells Z", self.nz_spin))

        hl_auto = QHBoxLayout()
        self.n_mfp_spin = QDoubleSpinBox()
        self.n_mfp_spin.setRange(0.1, 20.0)
        self.n_mfp_spin.setSingleStep(0.5)
        self.n_mfp_spin.setDecimals(1)
        self.n_mfp_spin.setValue(geo.n_mfp_per_cell)
        self.n_mfp_spin.setToolTip("Target cell size in units of mean free path")
        hl_auto.addWidget(QLabel("  Target: cell size ="))
        hl_auto.addWidget(self.n_mfp_spin)
        hl_auto.addWidget(QLabel("× λ_free"))
        auto_btn = QPushButton("Auto-grid")
        auto_btn.setToolTip("Compute Nx/Ny/Nz so each cell is ~N_mfp mean free paths wide")
        auto_btn.clicked.connect(self.auto_grid_requested.emit)
        hl_auto.addWidget(auto_btn)
        hl_auto.addStretch()
        vl.addLayout(hl_auto)

        self.grid_info_label = QLabel("")
        self.grid_info_label.setStyleSheet("color: gray; font-size: 10px;")
        vl.addWidget(self.grid_info_label)

        return box

    def _build_surface(self) -> QGroupBox:
        box = QGroupBox("Surface File")
        vl = QVBoxLayout(box)

        geo = self.bus.state.geometry

        hl = QHBoxLayout()
        hl.addWidget(QLabel("File:"))
        self.surf_file_edit = QLineEdit(geo.surface_file)
        hl.addWidget(self.surf_file_edit)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_surf)
        hl.addWidget(browse)
        vl.addLayout(hl)

        hl2 = QHBoxLayout()
        hl2.addWidget(QLabel("Units in file:"))
        self.surf_units_combo = QComboBox()
        self.surf_units_combo.addItems(["m", "mm", "cm", "in"])
        self.surf_units_combo.setCurrentText(geo.surface_units)
        hl2.addWidget(self.surf_units_combo)

        hl2.addWidget(QLabel("  Scale factor:"))
        self.surf_scale_spin = ScientificSpinBox(geo.surface_scale)
        self.surf_scale_spin.setToolTip("Applied on top of units conversion (1.0 = no extra scaling)")
        hl2.addWidget(self.surf_scale_spin)
        hl2.addStretch()
        vl.addLayout(hl2)

        self.surf_info = QTextEdit()
        self.surf_info.setReadOnly(True)
        self.surf_info.setMaximumHeight(100)
        self.surf_info.setPlaceholderText("Surface file info will appear here after loading…")
        vl.addWidget(self.surf_info)

        inspect_btn = QPushButton("Inspect surface bounds")
        inspect_btn.clicked.connect(self._inspect_surface)
        vl.addWidget(inspect_btn)

        return box

    def _build_fnum_helpers(self) -> QGroupBox:
        box = QGroupBox("fnum Calculation Helpers")
        vl = QVBoxLayout(box)

        sim = self.bus.state.simulation

        # --- Post-AMR cell count ---
        hl_amr = QHBoxLayout()
        hl_amr.addWidget(QLabel("Post-AMR cell count:"))
        self.amr_cells_spin = QSpinBox()
        self.amr_cells_spin.setRange(0, 100_000_000)
        self.amr_cells_spin.setSingleStep(10000)
        self.amr_cells_spin.setValue(sim.n_cells_amr)
        self.amr_cells_spin.setToolTip(
            "Enter total cell count after grid adaptation (from SPARTA log).\n"
            "0 = use Nx×Ny×Nz from the Grid section above."
        )
        hl_amr.addWidget(self.amr_cells_spin)
        amr_note = QLabel("(0 = use uniform Nx×Ny×Nz)")
        amr_note.setStyleSheet("color: gray; font-size: 10px;")
        hl_amr.addWidget(amr_note)
        hl_amr.addStretch()
        vl.addLayout(hl_amr)

        # --- Flow volume mode ---
        hl_mode = QHBoxLayout()
        hl_mode.addWidget(QLabel("Flow volume mode:"))
        self.flow_vol_combo = QComboBox()
        self.flow_vol_combo.addItems(["auto", "sparta", "computed"])
        self.flow_vol_combo.setCurrentText(sim.flow_volume_mode)
        self.flow_vol_combo.setToolTip(
            "auto: use full box volume\n"
            "sparta: paste from SPARTA log (Volume reported)\n"
            "computed: estimate from surf file polygon area × z-thickness"
        )
        hl_mode.addWidget(self.flow_vol_combo)
        hl_mode.addStretch()
        vl.addLayout(hl_mode)

        # SPARTA-reported value (shown only when mode=sparta)
        self._sparta_vol_row = QWidget()
        hl_sv = QHBoxLayout(self._sparta_vol_row)
        hl_sv.setContentsMargins(0, 0, 0, 0)
        hl_sv.addWidget(QLabel("SPARTA reported volume:"))
        from .widgets import ScientificSpinBox
        self.sparta_vol_spin = ScientificSpinBox(sim.flow_volume_sparta)
        self.sparta_vol_spin.setToolTip("Paste the 'Volume' value from SPARTA log here (m³ or m² for 2D slabs)")
        hl_sv.addWidget(self.sparta_vol_spin)
        hl_sv.addWidget(QLabel("m³"))
        hl_sv.addStretch()
        vl.addWidget(self._sparta_vol_row)

        self._update_flow_vol_row_visibility(sim.flow_volume_mode)

        return box

    def _update_flow_vol_row_visibility(self, mode: str):
        self._sparta_vol_row.setVisible(mode == "sparta")

    # ── Actions ──────────────────────────────────────────────────────────────

    def _browse_surf(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select surface file", "",
            "Surface files (*.surf *.stl *.STL *.tif *.tiff);;All files (*)"
        )
        if path:
            self.surf_file_edit.setText(path)
            self.bus.state.geometry.surface_file = path
            self._inspect_surface()
            self.bus.notify_geometry()

    def _inspect_surface(self):
        path = self.surf_file_edit.text()
        if not path or not os.path.isfile(path):
            self.surf_info.setPlainText("File not found.")
            return
        ext = os.path.splitext(path)[1].lower()
        if ext in (".stl",):
            self.surf_info.setPlainText(f"STL file: {os.path.basename(path)}\n(Bounds inspection requires numpy-stl)")
        elif ext in (".tif", ".tiff"):
            self.surf_info.setPlainText(f"TIFF file: {os.path.basename(path)}\n(Bounds inspection requires PIL/Pillow)")
        else:
            # Try as SPARTA surf for .surf and any no-extension file
            self._inspect_sparta_surf(path)

    def _inspect_sparta_surf(self, path: str):
        try:
            pts = []
            in_pts = False
            n_lines = 0
            n_tris = 0
            in_lines = False
            in_tris = False
            mode = None   # '2d' or '3d'
            with open(path) as f:
                for line in f:
                    s = line.strip()
                    if s == "Points":
                        in_pts, in_lines, in_tris = True, False, False
                        continue
                    if s == "Lines":
                        in_pts, in_lines, in_tris = False, True, False
                        mode = "2d"
                        continue
                    if s == "Triangles":
                        in_pts, in_lines, in_tris = False, False, True
                        mode = "3d"
                        continue
                    if not s or s.startswith("#"):
                        continue
                    parts = s.split()
                    if not parts[0].lstrip("-").replace(".", "", 1).isdigit():
                        # header line like "202 points"
                        continue
                    if in_pts and len(parts) >= 3:
                        # 2D: idx x y  |  3D: idx x y z
                        if len(parts) >= 4:
                            pts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                        else:
                            pts.append((float(parts[1]), float(parts[2]), 0.0))
                    elif in_lines:
                        n_lines += 1
                    elif in_tris:
                        n_tris += 1

            if not pts:
                self.surf_info.setPlainText(
                    "No points found.\n"
                    "Expected format:\n"
                    "  Points\n  1 x y      (2D)\n  1 x y z   (3D)"
                )
                return

            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            zs = [p[2] for p in pts]
            dim_str = f"{'2D (Lines)' if mode == '2d' else '3D (Triangles)' if mode == '3d' else 'unknown'}"
            elem_str = f"Lines: {n_lines}" if n_lines else f"Triangles: {n_tris}"
            info = (
                f"Type: {dim_str}   Points: {len(pts)}   {elem_str}\n"
                f"X: [{min(xs):.4e}, {max(xs):.4e}]   span = {max(xs)-min(xs):.4e} m\n"
                f"Y: [{min(ys):.4e}, {max(ys):.4e}]   span = {max(ys)-min(ys):.4e} m\n"
            )
            if mode == "3d":
                info += f"Z: [{min(zs):.4e}, {max(zs):.4e}]   span = {max(zs)-min(zs):.4e} m\n"
            self.surf_info.setPlainText(info)
        except Exception as e:
            self.surf_info.setPlainText(f"Error reading surf: {e}")

    def _refresh_from_state(self):
        geo = self.bus.state.geometry
        self.dim_combo.setCurrentText(str(geo.dimension))
        self.sym_combo.setCurrentText(geo.symmetry)

    def update_grid_display(self, info_text: str):
        self.grid_info_label.setText(info_text)

    def apply_auto_grid(self, nx: int, ny: int, nz: int):
        self._loading = True
        self.nx_spin.setValue(nx)
        self.ny_spin.setValue(ny)
        self.nz_spin.setValue(nz)
        self._loading = False
        self._on_change()

    # ── Connections ──────────────────────────────────────────────────────────

    def _connect(self):
        self.dim_combo.currentTextChanged.connect(self._on_change)
        self.sym_combo.currentTextChanged.connect(self._on_change)
        for w in (self.xlo, self.xhi, self.ylo, self.yhi, self.zlo, self.zhi):
            w.valueChanged.connect(self._on_change)
        self.bc_x.currentTextChanged.connect(self._on_change)
        self.bc_y.currentTextChanged.connect(self._on_change)
        self.bc_z.currentTextChanged.connect(self._on_change)
        self.nx_spin.valueChanged.connect(self._on_change)
        self.ny_spin.valueChanged.connect(self._on_change)
        self.nz_spin.valueChanged.connect(self._on_change)
        self.n_mfp_spin.valueChanged.connect(self._on_n_mfp)
        self.surf_file_edit.editingFinished.connect(self._on_surf_change)
        self.surf_units_combo.currentTextChanged.connect(self._on_surf_change)
        self.surf_scale_spin.valueChanged.connect(self._on_surf_change)
        self.amr_cells_spin.valueChanged.connect(self._on_fnum_helpers)
        self.flow_vol_combo.currentTextChanged.connect(self._on_flow_vol_mode)
        self.sparta_vol_spin.valueChanged.connect(self._on_fnum_helpers)

    def _on_change(self):
        geo = self.bus.state.geometry
        geo.dimension = int(self.dim_combo.currentText())
        geo.symmetry = self.sym_combo.currentText()
        geo.xlo = self.xlo.value()
        geo.xhi = self.xhi.value()
        geo.ylo = self.ylo.value()
        geo.yhi = self.yhi.value()
        geo.zlo = self.zlo.value()
        geo.zhi = self.zhi.value()
        geo.boundary_x = self.bc_x.currentText()
        geo.boundary_y = self.bc_y.currentText()
        geo.boundary_z = self.bc_z.currentText()
        geo.n_cells_x = self.nx_spin.value()
        geo.n_cells_y = self.ny_spin.value()
        geo.n_cells_z = self.nz_spin.value()
        self.bus.notify_geometry()

    def _on_n_mfp(self):
        self.bus.state.geometry.n_mfp_per_cell = self.n_mfp_spin.value()

    def _on_surf_change(self):
        geo = self.bus.state.geometry
        geo.surface_file = self.surf_file_edit.text()
        geo.surface_units = self.surf_units_combo.currentText()
        geo.surface_scale = self.surf_scale_spin.value()
        self.bus.notify()

    def _on_flow_vol_mode(self):
        mode = self.flow_vol_combo.currentText()
        self.bus.state.simulation.flow_volume_mode = mode
        self._update_flow_vol_row_visibility(mode)
        self.bus.notify()

    def _on_fnum_helpers(self):
        sim = self.bus.state.simulation
        sim.n_cells_amr = self.amr_cells_spin.value()
        sim.flow_volume_sparta = self.sparta_vol_spin.value()
        self.bus.notify()
