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
    return _gen(case, derived, dt_override=dt_override)
