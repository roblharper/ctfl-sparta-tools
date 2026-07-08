"""Chemistry tab — TCE gas-phase reactions and surface chemistry (Park carbon)."""

from __future__ import annotations

import math
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QScrollArea, QAbstractItemView,
    QHeaderView, QCheckBox, QLineEdit, QComboBox, QSizePolicy, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from .state import AppStateSignals, GasReaction, SurfReaction, ChemistryState
from .widgets import hline, section_label, LabeledField

_R = 8.314  # J/(mol·K)

# Columns for the TCE gas-phase reaction table
_GAS_COLS = [
    ("enabled",  "On",      "check"),
    ("reaction", "Reaction", str),
    ("rxn_type", "Type",    str),
    ("C1",       "DoF",     float),
    ("C2",       "Ea (J)",  float),
    ("C3",       "A (m³/s)", float),
    ("C4",       "b",       float),
    ("C5",       "ΔE (J)",  float),
]

# Columns for the surface reaction table
_SURF_COLS = [
    ("enabled",   "On",        "check"),
    ("reaction",  "Reaction",  str),
    ("rxn_type",  "Type",      str),
    ("gamma",     "γ",         float),
    ("E_kJ",      "E (kJ/mol)", float),
    ("delta_E",   "ΔE (J)",    float),
    ("_prob",     "P @ T_wall", float),  # computed column, read-only
]


def _surf_prob(gamma: float, E_kJ: float, T_wall: float) -> float:
    if E_kJ == 0.0 or T_wall <= 0:
        return gamma
    return gamma * math.exp(-E_kJ * 1e3 / (_R * T_wall))


class ChemistryTab(QWidget):
    def __init__(self, bus: AppStateSignals, parent=None):
        super().__init__(parent)
        self.bus = bus
        self._loading = False
        self._setup_ui()
        self.refresh_from_state()

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

        layout.addWidget(self._build_gas_group())
        layout.addWidget(self._build_surf_group())
        layout.addStretch()

    # ── Gas-phase TCE ─────────────────────────────────────────────────────────

    def _build_gas_group(self) -> QGroupBox:
        box = QGroupBox("Gas-Phase Chemistry (TCE — Park 1993 11-species air)")
        vl = QVBoxLayout(box)

        note = QLabel(
            "The full Park 1993 reaction set is always written to the chemistry file. "
            "SPARTA only activates reactions for which all reactants and products are "
            "defined as active species, so the full file works for any subset. "
            "Uncheck individual reactions to exclude them, or edit rate coefficients."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-size: 11px;")
        vl.addWidget(note)

        self.gas_table = QTableWidget(0, len(_GAS_COLS))
        self.gas_table.setHorizontalHeaderLabels([c[1] for c in _GAS_COLS])
        hdr = self.gas_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # checkbox
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)             # reaction
        for i in range(2, len(_GAS_COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.gas_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.gas_table.setAlternatingRowColors(True)
        self.gas_table.setMinimumHeight(260)
        self.gas_table.itemChanged.connect(self._on_gas_cell_changed)
        vl.addWidget(self.gas_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Reaction")
        add_btn.clicked.connect(self._add_gas_reaction)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_gas_reaction)
        reset_btn = QPushButton("Reset to Park Defaults")
        reset_btn.clicked.connect(self._reset_gas_defaults)
        for b in [add_btn, remove_btn, reset_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        vl.addLayout(btn_row)

        return box

    # ── Surface chemistry ─────────────────────────────────────────────────────

    def _build_surf_group(self) -> QGroupBox:
        box = QGroupBox("Surface Chemistry (prob style — Park carbon)")
        vl = QVBoxLayout(box)

        top_row = QHBoxLayout()
        self.surf_enabled_check = QCheckBox("Enable surface chemistry (surf_react)")
        top_row.addWidget(self.surf_enabled_check)
        top_row.addStretch()
        vl.addLayout(top_row)

        note = QLabel(
            "Reaction probability is evaluated at the current wall temperature: "
            "P = γ × exp(−E×10³ / (R×T_wall)). "
            "The P @ T_wall column updates automatically when wall temperature changes."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #555; font-size: 11px;")
        vl.addWidget(note)

        # Output filename row
        fn_row = QHBoxLayout()
        fn_row.addWidget(QLabel("Output file:"))
        self.surf_file_edit = QLineEdit()
        self.surf_file_edit.setPlaceholderText("surface.react")
        self.surf_file_edit.setMaximumWidth(220)
        fn_row.addWidget(self.surf_file_edit)
        fn_row.addStretch()
        vl.addLayout(fn_row)

        self.surf_table = QTableWidget(0, len(_SURF_COLS))
        self.surf_table.setHorizontalHeaderLabels([c[1] for c in _SURF_COLS])
        hdr = self.surf_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in range(2, len(_SURF_COLS)):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.surf_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.surf_table.setAlternatingRowColors(True)
        self.surf_table.setMinimumHeight(160)
        self.surf_table.itemChanged.connect(self._on_surf_cell_changed)
        vl.addWidget(self.surf_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Reaction")
        add_btn.clicked.connect(self._add_surf_reaction)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_surf_reaction)
        reset_btn = QPushButton("Reset to Park Carbon Defaults")
        reset_btn.clicked.connect(self._reset_surf_defaults)
        for b in [add_btn, remove_btn, reset_btn]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        vl.addLayout(btn_row)

        # Connect controls
        self.surf_enabled_check.toggled.connect(self._on_surf_enabled)
        self.surf_file_edit.editingFinished.connect(self._on_surf_file)

        return box

    # ── Public refresh ────────────────────────────────────────────────────────

    def refresh_from_state(self):
        """Push state into the UI tables."""
        state = self.bus.state
        chem = state.chemistry

        # Ensure defaults are populated if lists are empty
        if not chem.gas_reactions:
            from sparta_tools.chem_writer import default_gas_reactions
            for r in default_gas_reactions():
                chem.gas_reactions.append(GasReaction(
                    reaction=r["reaction"],
                    rxn_type=r["type"],
                    style=r["style"],
                    C1=r["C1"], C2=r["C2"], C3=r["C3"], C4=r["C4"], C5=r["C5"],
                    enabled=r["enabled"],
                ))

        if not chem.surf_reactions:
            from sparta_tools.chem_writer import default_surf_reactions
            for r in default_surf_reactions():
                sr = SurfReaction(
                    label=r["label"],
                    comment=r["comment"],
                    reaction=r["reaction"],
                    rxn_type=r["type"],
                    gamma=r["gamma"],
                    E_kJ=r["E_kJ"],
                    delta_E=r.get("delta_E", 0.0),
                    enabled=r.get("enabled", True),
                )
                chem.surf_reactions.append(sr)

        self._loading = True

        # ── Gas table ────────────────────────────────────────────────────────
        self.gas_table.blockSignals(True)
        self.gas_table.setRowCount(0)
        for rxn in chem.gas_reactions:
            self._append_gas_row(rxn)
        self.gas_table.blockSignals(False)

        # ── Surf controls ────────────────────────────────────────────────────
        self.surf_enabled_check.blockSignals(True)
        self.surf_enabled_check.setChecked(chem.surf_enabled)
        self.surf_enabled_check.blockSignals(False)
        self.surf_file_edit.blockSignals(True)
        self.surf_file_edit.setText(chem.surf_react_file)
        self.surf_file_edit.blockSignals(False)

        # ── Surf table ───────────────────────────────────────────────────────
        T_wall = state.wall.temperature
        self.surf_table.blockSignals(True)
        self.surf_table.setRowCount(0)
        for rxn in chem.surf_reactions:
            self._append_surf_row(rxn, T_wall)
        self.surf_table.blockSignals(False)

        self._loading = False

    def _append_gas_row(self, rxn: GasReaction):
        row = self.gas_table.rowCount()
        self.gas_table.insertRow(row)
        for col_idx, (field, label, typ) in enumerate(_GAS_COLS):
            if typ == "check":
                cb = QTableWidgetItem()
                cb.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                cb.setCheckState(Qt.Checked if rxn.enabled else Qt.Unchecked)
                self.gas_table.setItem(row, col_idx, cb)
            elif typ == str:
                item = QTableWidgetItem(str(getattr(rxn, field, "")))
                self.gas_table.setItem(row, col_idx, item)
            else:
                val = getattr(rxn, field, 0.0)
                item = QTableWidgetItem(f"{val:.4e}" if abs(val) > 0 and (abs(val) >= 1e4 or abs(val) < 1e-3) else f"{val:.6g}")
                self.gas_table.setItem(row, col_idx, item)

    def _append_surf_row(self, rxn: SurfReaction, T_wall: float):
        row = self.surf_table.rowCount()
        self.surf_table.insertRow(row)
        for col_idx, (field, label, typ) in enumerate(_SURF_COLS):
            if typ == "check":
                cb = QTableWidgetItem()
                cb.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                cb.setCheckState(Qt.Checked if rxn.enabled else Qt.Unchecked)
                self.surf_table.setItem(row, col_idx, cb)
            elif field == "_prob":
                prob = _surf_prob(rxn.gamma, rxn.E_kJ, T_wall)
                item = QTableWidgetItem(f"{prob:.5f}")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setBackground(QColor("#e8f4e8"))
                item.setToolTip(f"P = γ·exp(-E×10³/(R·T)) = {rxn.gamma}·exp(-{rxn.E_kJ*1e3:.0f}/({_R:.3f}·{T_wall:.0f}))")
                self.surf_table.setItem(row, col_idx, item)
            elif field == "rxn_type":
                item = QTableWidgetItem(rxn.rxn_type)
                item.setToolTip("D = dissociation, E = exchange, R = recombination/absorption")
                self.surf_table.setItem(row, col_idx, item)
            elif typ == str:
                self.surf_table.setItem(row, col_idx, QTableWidgetItem(str(getattr(rxn, field, ""))))
            else:
                val = getattr(rxn, field, 0.0)
                self.surf_table.setItem(row, col_idx, QTableWidgetItem(f"{val:.6g}"))

    def _update_surf_prob_column(self):
        """Recompute and refresh the P @ T_wall column without full table rebuild."""
        T_wall = self.bus.state.wall.temperature
        self._loading = True
        self.surf_table.blockSignals(True)
        prob_col = next(i for i, (f, _, _) in enumerate(_SURF_COLS) if f == "_prob")
        for row in range(self.surf_table.rowCount()):
            rxn = self.bus.state.chemistry.surf_reactions[row]
            prob = _surf_prob(rxn.gamma, rxn.E_kJ, T_wall)
            item = self.surf_table.item(row, prob_col)
            if item:
                item.setText(f"{prob:.5f}")
        self.surf_table.blockSignals(False)
        self._loading = False

    # ── Change handlers ───────────────────────────────────────────────────────

    def _on_gas_cell_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        col = item.column()
        chem = self.bus.state.chemistry
        if row >= len(chem.gas_reactions):
            return
        rxn = chem.gas_reactions[row]
        field, _, typ = _GAS_COLS[col]
        if typ == "check":
            rxn.enabled = item.checkState() == Qt.Checked
        elif typ == str:
            setattr(rxn, field, item.text())
        else:
            try:
                setattr(rxn, field, float(item.text()))
            except ValueError:
                return
        self.bus.notify_chemistry()

    def _on_surf_cell_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        col = item.column()
        chem = self.bus.state.chemistry
        if row >= len(chem.surf_reactions):
            return
        rxn = chem.surf_reactions[row]
        field, _, typ = _SURF_COLS[col]
        if field == "_prob":
            return  # read-only
        if typ == "check":
            rxn.enabled = item.checkState() == Qt.Checked
        elif typ == str:
            setattr(rxn, field, item.text())
        else:
            try:
                setattr(rxn, field, float(item.text()))
            except ValueError:
                return
        # Refresh the computed probability column
        self._update_surf_prob_column()
        self.bus.notify_chemistry()

    def _on_surf_enabled(self, checked: bool):
        if self._loading:
            return
        self.bus.state.chemistry.surf_enabled = checked
        self.bus.notify_chemistry()

    def _on_surf_file(self):
        if self._loading:
            return
        self.bus.state.chemistry.surf_react_file = self.surf_file_edit.text().strip() or "surface.react"
        self.bus.notify_chemistry()

    # ── Button handlers ───────────────────────────────────────────────────────

    def _add_gas_reaction(self):
        rxn = GasReaction(reaction="R1 + R2 --> P1 + P2", rxn_type="D", style="A")
        self.bus.state.chemistry.gas_reactions.append(rxn)
        self._loading = True
        self.gas_table.blockSignals(True)
        self._append_gas_row(rxn)
        self.gas_table.blockSignals(False)
        self._loading = False
        self.bus.notify_chemistry()

    def _remove_gas_reaction(self):
        rows = sorted({i.row() for i in self.gas_table.selectedItems()}, reverse=True)
        for r in rows:
            if r < len(self.bus.state.chemistry.gas_reactions):
                del self.bus.state.chemistry.gas_reactions[r]
            self.gas_table.removeRow(r)
        self.bus.notify_chemistry()

    def _reset_gas_defaults(self):
        from sparta_tools.chem_writer import default_gas_reactions
        chem = self.bus.state.chemistry
        chem.gas_reactions = []
        for r in default_gas_reactions():
            chem.gas_reactions.append(GasReaction(
                reaction=r["reaction"],
                rxn_type=r["type"],
                style=r["style"],
                C1=r["C1"], C2=r["C2"], C3=r["C3"], C4=r["C4"], C5=r["C5"],
                enabled=r["enabled"],
            ))
        self._loading = True
        self.gas_table.blockSignals(True)
        self.gas_table.setRowCount(0)
        for rxn in chem.gas_reactions:
            self._append_gas_row(rxn)
        self.gas_table.blockSignals(False)
        self._loading = False
        self.bus.notify_chemistry()

    def _add_surf_reaction(self):
        rxn = SurfReaction(label="", comment="", reaction="R1 --> P1", rxn_type="E", gamma=0.5)
        self.bus.state.chemistry.surf_reactions.append(rxn)
        T_wall = self.bus.state.wall.temperature
        self._loading = True
        self.surf_table.blockSignals(True)
        self._append_surf_row(rxn, T_wall)
        self.surf_table.blockSignals(False)
        self._loading = False
        self.bus.notify_chemistry()

    def _remove_surf_reaction(self):
        rows = sorted({i.row() for i in self.surf_table.selectedItems()}, reverse=True)
        for r in rows:
            if r < len(self.bus.state.chemistry.surf_reactions):
                del self.bus.state.chemistry.surf_reactions[r]
            self.surf_table.removeRow(r)
        self.bus.notify_chemistry()

    def _reset_surf_defaults(self):
        from sparta_tools.chem_writer import default_surf_reactions
        chem = self.bus.state.chemistry
        chem.surf_reactions = []
        for r in default_surf_reactions():
            chem.surf_reactions.append(SurfReaction(
                label=r["label"],
                comment=r["comment"],
                reaction=r["reaction"],
                rxn_type=r["type"],
                gamma=r["gamma"],
                E_kJ=r["E_kJ"],
                delta_E=r.get("delta_E", 0.0),
                enabled=r.get("enabled", True),
            ))
        T_wall = self.bus.state.wall.temperature
        self._loading = True
        self.surf_table.blockSignals(True)
        self.surf_table.setRowCount(0)
        for rxn in chem.surf_reactions:
            self._append_surf_row(rxn, T_wall)
        self.surf_table.blockSignals(False)
        self._loading = False
        self.bus.notify_chemistry()
