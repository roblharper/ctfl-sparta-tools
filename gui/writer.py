"""GUI writer — converts AppState to SPARTACase and delegates to sparta_tools.generate."""

from __future__ import annotations

from .state import AppStateSignals
from .engine import DerivedQuantities


def _app_state_to_case(state):
    """Convert AppState (Qt-aware) into a headless SPARTACase."""
    from sparta_tools.case import (
        SPARTACase, FreestreamConfig, WallConfig, PhysicsConfig,
        GridConfig, SimConfig, ComputeDumpConfig,
    )
    import dataclasses

    def _copy(src_obj, dst_cls):
        kwargs = {}
        src_fields = {f.name for f in dataclasses.fields(src_obj)}
        for f in dataclasses.fields(dst_cls):
            if f.name in src_fields:
                kwargs[f.name] = getattr(src_obj, f.name)
        return dst_cls(**kwargs)

    geo = state.geometry
    sim = state.simulation
    fs  = state.freestream

    case = SPARTACase.__new__(SPARTACase)
    case.name         = state.case_name
    case.species_dict = {e.species_id: e.mol_frac for e in state.species_list if e.species_id and e.mol_frac > 0}
    case.species_file = state.species_file
    case.freestream   = _copy(fs, FreestreamConfig)
    case.wall         = _copy(state.wall, WallConfig)
    case.physics      = _copy(state.physics, PhysicsConfig)
    case.sim          = _copy(sim, SimConfig)
    case.compute_dump = _copy(state.compute_dump, ComputeDumpConfig)
    case.grid = GridConfig(
        xlo=geo.xlo, xhi=geo.xhi,
        ylo=geo.ylo, yhi=geo.yhi,
        zlo=geo.zlo, zhi=geo.zhi,
        dimension=geo.dimension,
        symmetry=geo.symmetry,
        boundary_x=geo.boundary_x,
        boundary_y=geo.boundary_y,
        boundary_z=geo.boundary_z,
        n_cells_x=geo.n_cells_x,
        n_cells_y=geo.n_cells_y,
        n_cells_z=geo.n_cells_z,
        surface_file=geo.surface_file,
        surface_units=geo.surface_units,
        surface_scale=geo.surface_scale,
    )
    case._derived = None  # caller supplies derived separately
    return case


def generate(state, derived: DerivedQuantities, dt_override: float = 0.0) -> str:
    """Return the full SPARTA input script as a string."""
    from sparta_tools.generate import generate as _gen
    case = _app_state_to_case(state)
    case._derived = derived
    # Surface chemistry wiring
    chem = getattr(state, "chemistry", None)
    if chem and getattr(chem, "surf_enabled", False):
        case._surf_react_file = chem.surf_react_file or "surface.react"
    else:
        case._surf_react_file = ""
    return _gen(case, derived, dt_override=dt_override)


def write_support_files(state, out_dir: str) -> list[str]:
    """Write species, collision, TCE chemistry, and surface chemistry files.

    Returns a list of written file paths.
    """
    import os
    from sparta_tools.species_writer import write_species_file, write_collision_file
    from sparta_tools.chem_writer import (
        write_tce_chem_file, write_surf_chem_file,
        default_gas_reactions, default_surf_reactions,
        species_in_reactions,
    )
    from .state import GasReaction, SurfReaction

    # Inflow species (non-zero mole fraction)
    inflow_ids = [e.species_id for e in state.species_list if e.species_id and e.mol_frac > 0]

    # Determine gas reactions to use (custom or defaults)
    chem = state.chemistry
    gas_rxns = chem.gas_reactions if chem.gas_reactions else []
    if not gas_rxns:
        gas_dicts = default_gas_reactions()
    else:
        gas_dicts = [
            {
                "reaction": r.reaction, "type": r.rxn_type, "style": r.style,
                "C1": r.C1, "C2": r.C2, "C3": r.C3, "C4": r.C4, "C5": r.C5,
                "enabled": r.enabled,
            }
            for r in gas_rxns
        ]

    # Full species set = inflow + all reaction product species
    if state.physics.react_enabled:
        rxn_sp = species_in_reactions(gas_dicts)
        extra = sorted(rxn_sp - set(inflow_ids))
    else:
        extra = []
    species_ids = inflow_ids + extra

    sp_file = state.species_file

    written: list[str] = []

    # Locate species.json if not set
    if not sp_file or not os.path.isfile(sp_file):
        import os as _os
        sp_file = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "species.json")

    # ── Species file ──────────────────────────────────────────────────────────
    sp_overrides = {
        o.species_id: {
            k: v for k, v in {
                "diameter": o.diameter if o.diameter != 0 else None,
                "omega":    o.omega    if o.omega    != 0 else None,
                "alpha":    o.alpha    if o.alpha    != 0 else None,
                "MWA":      o.MWA      if o.MWA      != -1 else None,
                "MWB":      o.MWB      if o.MWB      != -1 else None,
                "rotc1":    o.rotc1    if o.rotc1    != -1 else None,
                "rotc2":    o.rotc2    if o.rotc2    != -1 else None,
            }.items() if v is not None
        }
        for o in state.species_overrides
    }
    sp_out = os.path.join(out_dir, "species.list")
    write_species_file(species_ids, sp_file, sp_overrides, out_path=sp_out)
    written.append(sp_out)

    # ── Collision file ────────────────────────────────────────────────────────
    col_overrides = {
        o.pair_key: {
            k: v for k, v in {
                "diameter": o.diameter if o.diameter != 0 else None,
                "omega":    o.omega    if o.omega    != 0 else None,
                "alpha":    o.alpha    if o.alpha    != 0 else None,
                "tref":     o.tref     if o.tref     != 0 else None,
            }.items() if v is not None
        }
        for o in state.collision_overrides
    }
    col_out = os.path.join(out_dir, "collision.vss")
    write_collision_file(species_ids, sp_file, col_overrides, out_path=col_out)
    written.append(col_out)

    # ── TCE chemistry file ────────────────────────────────────────────────────
    tce_out = os.path.join(out_dir, "air.chem")
    write_tce_chem_file(gas_dicts, out_path=tce_out, header=f"Case: {state.case_name}")
    written.append(tce_out)

    # ── Surface chemistry file ────────────────────────────────────────────────
    if chem.surf_enabled:
        surf_rxns = chem.surf_reactions if chem.surf_reactions else []
        if not surf_rxns:
            surf_dicts = default_surf_reactions()
        else:
            surf_dicts = [
                {
                    "label": r.label, "comment": r.comment, "reaction": r.reaction,
                    "type": r.rxn_type, "gamma": r.gamma, "E_kJ": r.E_kJ,
                    "delta_E": r.delta_E, "enabled": r.enabled,
                }
                for r in surf_rxns
            ]
        surf_out = os.path.join(out_dir, chem.surf_react_file or "surface.react")
        write_surf_chem_file(
            surf_dicts, state.wall.temperature,
            out_path=surf_out,
            header=f"Case: {state.case_name}",
        )
        written.append(surf_out)

    return written
