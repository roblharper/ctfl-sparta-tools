"""Species & Collisions tab — view/edit per-species and per-pair VSS parameters."""

from __future__ import annotations

import json
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QScrollArea, QAbstractItemView,
    QHeaderView, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from .state import AppStateSignals, SpeciesOverride, CollisionOverride
from .widgets import hline, section_label


_WARNING = (
    "⚠  Modifying these values changes collision physics. "
    "CTFL defaults are loaded from species.json — only override if you have "
    "species-specific data. Changes here do not affect gas-phase reaction rates."
)

# Columns shown in the species table
_SP_COLS = [
    ("id",        "Species",    str),
    ("diameter",  "d_ref (m)",  float),
    ("omega",     "ω",          float),
    ("alpha",     "α (VSS)",    float),
    ("rotc1",     "Parker C1",  float),
    ("rotc2",     "Parker C2",  float),
    ("MWA",       "MW-A",       float),
    ("MWB",       "MW-B",       float),
]

# Columns shown in the collision pair table
_COL_COLS = [
    ("pair_key",  "Pair",       str),
    ("diameter",  "d_ref (m)",  float),
    ("omega",     "ω",          float),
    ("alpha",     "α",          float),
    ("tref",      "T_ref (K)",  float),
]


def _load_db(species_file: str) -> dict:
    if not species_file or not os.path.isfile(species_file):
        return {}
    with open(species_file) as f:
        return json.load(f)


def _pair_key(sp1: str, sp2: str) -> str:
    return "-".join(sorted([sp1, sp2]))


def _mixing(d1: dict, d2: dict, field: str, default: float = 0.0) -> float:
    return 0.5 * (d1.get(field, default) + d2.get(field, default))


class SpeciesTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._loading = False
        self._db: dict = {}
        self._setup_ui()
        self._load_db_and_refresh()

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

        # Warning banner
        warn = QLabel(_WARNING)
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "background: #fff3cd; color: #856404; border: 1px solid #ffc107; "
            "border-radius: 4px; padding: 8px;"
        )
        layout.addWidget(warn)

        layout.addWidget(self._build_species_group())
        layout.addWidget(self._build_collision_group())
        layout.addStretch()

    # ── Species parameters table ──────────────────────────────────────────────

    def _build_species_group(self) -> QGroupBox:
        box = QGroupBox("Per-Species Parameters (from species.json database)")
        vl = QVBoxLayout(box)

        note = QLabel(
            "Parameters shown for active species only (set in the Case tab). "
            "Click any cell to edit — empty = use database default."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-size: 11px;")
        vl.addWidget(note)

        self.sp_table = QTableWidget(0, len(_SP_COLS))
        self.sp_table.setHorizontalHeaderLabels([c[1] for c in _SP_COLS])
        self.sp_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sp_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.sp_table.setAlternatingRowColors(True)
        self.sp_table.setMinimumHeight(200)
        self.sp_table.itemChanged.connect(self._on_species_cell_changed)
        vl.addWidget(self.sp_table)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setToolTip("Clear all per-species overrides and reload from species.json")
        reset_btn.clicked.connect(self._reset_species)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        vl.addLayout(btn_row)

        return box

    # ── Collision pair parameters table ──────────────────────────────────────

    def _build_collision_group(self) -> QGroupBox:
        box = QGroupBox("Per-Pair VSS Collision Parameters (mixing rules applied)")
        vl = QVBoxLayout(box)

        note = QLabel(
            "Arithmetic mean for diameter, geometric mean for ω and α. "
            "Edit a cell to override the mixing rule for a specific pair."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-size: 11px;")
        vl.addWidget(note)

        self.col_table = QTableWidget(0, len(_COL_COLS))
        self.col_table.setHorizontalHeaderLabels([c[1] for c in _COL_COLS])
        self.col_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.col_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.col_table.setAlternatingRowColors(True)
        self.col_table.setMinimumHeight(200)
        self.col_table.itemChanged.connect(self._on_collision_cell_changed)
        vl.addWidget(self.col_table)

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.setToolTip("Clear all per-pair overrides and recompute from mixing rules")
        reset_btn.clicked.connect(self._reset_collisions)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        vl.addLayout(btn_row)

        return box

    # ── Public refresh ────────────────────────────────────────────────────────

    def _load_db_and_refresh(self):
        state = self.bus.state
        sp_file = state.species_file
        if not sp_file or not os.path.isfile(sp_file):
            sp_file = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "species.json"
            )
        self._db = _load_db(sp_file)
        self.refresh_from_state()

    def refresh_from_state(self):
        """Called externally when active species list changes."""
        self._load_db_and_refresh_tables()

    def _load_db_and_refresh_tables(self):
        state = self.bus.state
        active = [e.species_id for e in state.species_list if e.species_id]

        # Build override lookup
        sp_ovr = {o.species_id: o for o in state.species_overrides}
        col_ovr = {o.pair_key: o for o in state.collision_overrides}

        # ── Species table ────────────────────────────────────────────────────
        self._loading = True
        self.sp_table.blockSignals(True)
        self.sp_table.setRowCount(0)

        for sp in active:
            row = self.sp_table.rowCount()
            self.sp_table.insertRow(row)
            db_entry = self._db.get(sp, {})
            ovr = sp_ovr.get(sp)

            for col_idx, (field, label, typ) in enumerate(_SP_COLS):
                if field == "id":
                    item = QTableWidgetItem(sp)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setBackground(QColor("#f0f0f0"))
                    self.sp_table.setItem(row, col_idx, item)
                    continue

                # Check for override
                ovr_val = None
                if ovr is not None:
                    raw = getattr(ovr, field, None)
                    if raw is not None and raw != 0.0 and raw != -1.0:
                        ovr_val = raw

                if ovr_val is not None:
                    item = QTableWidgetItem(f"{ovr_val:.6g}")
                    item.setForeground(QColor("#c0392b"))  # red = overridden
                    item.setToolTip(
                        f"Override active. Database default: {db_entry.get(field, 'N/A'):.6g}"
                        if isinstance(db_entry.get(field), float) else
                        f"Override active. Database default: {db_entry.get(field, 'N/A')}"
                    )
                else:
                    db_val = db_entry.get(field)
                    text = f"{db_val:.6g}" if isinstance(db_val, float) else str(db_val or "")
                    item = QTableWidgetItem(text)
                    item.setForeground(QColor("#555"))  # gray = database value

                self.sp_table.setItem(row, col_idx, item)

        self.sp_table.blockSignals(False)
        self._loading = False

        # ── Collision pair table ─────────────────────────────────────────────
        self._loading = True
        self.col_table.blockSignals(True)
        self.col_table.setRowCount(0)

        for i, sp1 in enumerate(active):
            for sp2 in active[i:]:
                row = self.col_table.rowCount()
                self.col_table.insertRow(row)
                d1 = self._db.get(sp1, {})
                d2 = self._db.get(sp2, {})
                key = _pair_key(sp1, sp2)
                ovr = col_ovr.get(key)

                # Compute mixing-rule defaults
                defaults = {
                    "pair_key": key,
                    "diameter": _mixing(d1, d2, "diameter"),
                    "omega":    _mixing(d1, d2, "omega", 0.75),
                    "alpha":    _mixing(d1, d2, "alpha", 1.0),
                    "tref":     _mixing(d1, d2, "tref", 273.15),
                }

                for col_idx, (field, label, typ) in enumerate(_COL_COLS):
                    if field == "pair_key":
                        item = QTableWidgetItem(key)
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                        item.setBackground(QColor("#f0f0f0"))
                        self.col_table.setItem(row, col_idx, item)
                        continue

                    ovr_val = None
                    if ovr is not None:
                        raw = getattr(ovr, field, None)
                        if raw is not None and raw != 0.0:
                            ovr_val = raw

                    def_val = defaults[field]
                    if ovr_val is not None:
                        item = QTableWidgetItem(f"{ovr_val:.6g}")
                        item.setForeground(QColor("#c0392b"))
                        item.setToolTip(f"Override active. Mixing rule default: {def_val:.6g}")
                    else:
                        item = QTableWidgetItem(f"{def_val:.6g}")
                        item.setForeground(QColor("#555"))

                    self.col_table.setItem(row, col_idx, item)

        self.col_table.blockSignals(False)
        self._loading = False

    # ── Change handlers ───────────────────────────────────────────────────────

    def _on_species_cell_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        col = item.column()
        if col == 0:
            return  # id column not editable

        sp_item = self.sp_table.item(row, 0)
        if not sp_item:
            return
        sp_id = sp_item.text()
        field = _SP_COLS[col][0]
        text = item.text().strip()

        state = self.bus.state
        # Find or create override
        ovr = next((o for o in state.species_overrides if o.species_id == sp_id), None)
        if ovr is None:
            ovr = SpeciesOverride(species_id=sp_id)
            state.species_overrides.append(ovr)

        if text == "":
            # Reset this field
            _DEFAULTS = {"diameter": 0.0, "omega": 0.0, "alpha": 0.0,
                         "MWA": -1.0, "MWB": -1.0, "rotc1": -1.0, "rotc2": -1.0}
            setattr(ovr, field, _DEFAULTS.get(field, 0.0))
        else:
            try:
                setattr(ovr, field, float(text))
            except ValueError:
                return

        item.setForeground(QColor("#c0392b") if text else QColor("#555"))
        self.bus.notify()

    def _on_collision_cell_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        col = item.column()
        if col == 0:
            return

        key_item = self.col_table.item(row, 0)
        if not key_item:
            return
        key = key_item.text()
        field = _COL_COLS[col][0]
        text = item.text().strip()

        state = self.bus.state
        ovr = next((o for o in state.collision_overrides if o.pair_key == key), None)
        if ovr is None:
            ovr = CollisionOverride(pair_key=key)
            state.collision_overrides.append(ovr)

        if text == "":
            setattr(ovr, field, 0.0)
        else:
            try:
                setattr(ovr, field, float(text))
            except ValueError:
                return

        item.setForeground(QColor("#c0392b") if text else QColor("#555"))
        self.bus.notify()

    def _reset_species(self):
        self.bus.state.species_overrides = []
        self._load_db_and_refresh_tables()
        self.bus.notify()

    def _reset_collisions(self):
        self.bus.state.collision_overrides = []
        self._load_db_and_refresh_tables()
        self.bus.notify()
