"""Compute engine: wraps Flow/Mixture/thermo calls, returns structured results."""

from __future__ import annotations
import sys
import os
from dataclasses import dataclass
from typing import Optional

# Allow importing from parent package when run as a standalone app
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from species import Species
from mixture import Mixture
from flow import Flow
from shock import normal_shock
import thermo
import math

BOLTZ = 1.380649e-23


@dataclass
class DerivedQuantities:
    mfp_free: float = 0.0
    mfp_shock: Optional[float] = None
    tau_free: float = 0.0
    tau_shock: Optional[float] = None
    mach: float = 0.0
    kn_free: float = 0.0
    kn_shock: Optional[float] = None
    n_free: float = 0.0
    n_shock: Optional[float] = None
    T_shock: Optional[float] = None
    P_shock: Optional[float] = None
    rho_shock: Optional[float] = None
    u_shock: Optional[float] = None
    gamma_mix: float = 0.0
    speed_of_sound: float = 0.0
    dt_recommended: float = 0.0
    dt_conservative: float = 0.0
    fnum: float = 0.0
    warmup_steps: int = 0
    total_steps: int = 0
    flow_through_time: float = 0.0
    n_cells: int = 0
    n_cells_uniform: int = 0
    flow_volume: float = 0.0
    grid_dx: float = 0.0
    grid_dy: float = 0.0
    # per-species collision freqs
    collision_freqs: dict = None
    error: str = ""

    def __post_init__(self):
        if self.collision_freqs is None:
            self.collision_freqs = {}


def _polygon_area(pts: list) -> float:
    """Shoelace formula for signed polygon area; pts = list of (x, y)."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        area += x0 * y1 - x1 * y0
    return abs(area) * 0.5


def _surf_polygon_area(surf_path: str) -> float:
    """Parse a SPARTA 2D .surf file and return the polygon area via shoelace."""
    pts: list = []
    in_pts = False
    try:
        with open(surf_path) as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                low = line.lower()
                if low.startswith("points"):
                    in_pts = True
                    continue
                if low.startswith("lines") or low.startswith("triangles"):
                    in_pts = False
                    continue
                if in_pts:
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            pts.append((float(parts[1]), float(parts[2])))
                        except ValueError:
                            pass
    except Exception:
        return 0.0
    return _polygon_area(pts)


def _resolve_flow_volume(state, box_volume: float) -> float:
    """Return the flow volume to use for fnum calculation."""
    sim = state.simulation
    mode = sim.flow_volume_mode

    if mode == "sparta" and sim.flow_volume_sparta > 0:
        return sim.flow_volume_sparta

    if mode == "computed":
        surf_path = state.geometry.surface_file
        if surf_path and os.path.isfile(surf_path):
            geo = state.geometry
            zlen = abs(geo.zhi - geo.zlo) if geo.dimension == 3 else 1.0
            surf_area = _surf_polygon_area(surf_path)
            if surf_area > 0:
                return max(0.0, box_volume - surf_area * zlen)
        # fall through to auto if surf unavailable
    return box_volume


def build_mixture(state, species_file: str) -> Optional[Mixture]:
    """Build Mixture from app state; returns None if species list is empty/invalid."""
    entries = state.species_list
    if not entries:
        return None
    species_dict = {e.species_id: e.mol_frac for e in entries if e.species_id}
    if not species_dict:
        return None
    total = sum(species_dict.values())
    if total <= 0:
        return None
    # normalise silently
    species_dict = {k: v / total for k, v in species_dict.items()}
    try:
        mix = Mixture(species_dict=species_dict, species_file=species_file)
        return mix
    except Exception:
        return None


def compute(state, species_file: str, L_ref: float = 1.0) -> DerivedQuantities:
    """Run all flow calculations from current AppState. L_ref in metres."""
    result = DerivedQuantities()

    mix = build_mixture(state, species_file)
    if mix is None:
        result.error = "Define at least one species with nonzero mole fraction."
        return result

    fs = state.freestream
    fq: dict = {"u": fs.velocity}

    # resolve thermodynamic state
    if fs.density > 0 and fs.temperature > 0:
        fq["T"] = fs.temperature
        fq["rho"] = fs.density
    elif fs.pressure > 0 and fs.temperature > 0:
        fq["T"] = fs.temperature
        fq["P"] = fs.pressure
    elif fs.density > 0 and fs.pressure > 0:
        fq["rho"] = fs.density
        fq["P"] = fs.pressure
    else:
        result.error = "Provide at least two of: Temperature, Pressure, Density."
        return result

    try:
        flow_free = Flow(mix, fq)
    except Exception as e:
        result.error = f"Flow construction failed: {e}"
        return result

    result.mfp_free = flow_free.mean_free_path()
    result.tau_free = flow_free.mean_collision_time()
    result.mach = flow_free.M
    result.gamma_mix = flow_free.gamma_mix
    result.speed_of_sound = flow_free.a
    result.n_free = flow_free.n

    if L_ref > 0:
        result.kn_free = result.mfp_free / L_ref

    # try normal shock
    if flow_free.M > 1.0:
        try:
            shock_fq = normal_shock(flow_free)
            shock_fq["u"] = shock_fq.get("u", fs.velocity / 4.0)
            flow_shock = Flow(mix, shock_fq)
            result.mfp_shock = flow_shock.mean_free_path()
            result.tau_shock = flow_shock.mean_collision_time()
            result.n_shock = flow_shock.n
            result.T_shock = flow_shock.T_tr
            result.P_shock = flow_shock.P
            result.rho_shock = flow_shock.rho
            result.u_shock = flow_shock.u
            if L_ref > 0:
                result.kn_shock = result.mfp_shock / L_ref
        except Exception:
            pass

    # timestep
    tau_ref = result.tau_shock if result.tau_shock else result.tau_free
    result.dt_recommended = state.simulation.dt_factor * tau_ref
    result.dt_conservative = 0.01 * tau_ref

    # grid & fnum
    geo = state.geometry
    sim = state.simulation
    xlen = abs(geo.xhi - geo.xlo)
    ylen = abs(geo.yhi - geo.ylo)
    zlen = abs(geo.zhi - geo.zlo) if geo.dimension == 3 else 1.0

    box_volume = xlen * ylen * zlen

    # flow volume — subtract surface if computable, or use SPARTA-reported value
    flow_volume = _resolve_flow_volume(state, box_volume)
    result.flow_volume = flow_volume

    # cell count — prefer post-AMR if provided
    n_cells_x = geo.n_cells_x
    n_cells_y = geo.n_cells_y
    n_cells_z = geo.n_cells_z if geo.dimension == 3 else 1
    uniform_cells = n_cells_x * n_cells_y * n_cells_z
    result.n_cells = sim.n_cells_amr if sim.n_cells_amr > 0 else uniform_cells
    result.n_cells_uniform = uniform_cells
    result.grid_dx = xlen / n_cells_x if n_cells_x > 0 else 0
    result.grid_dy = ylen / n_cells_y if n_cells_y > 0 else 0

    if sim.fnum_override > 0:
        result.fnum = sim.fnum_override
    elif result.n_cells > 0 and flow_volume > 0:
        result.fnum = (flow_free.n * flow_volume) / (result.n_cells * sim.n_ppc)

    # simulation schedule
    prod_steps = sim.ave_nevery * sim.ave_nrepeat
    if fs.velocity > 0 and xlen > 0:
        result.flow_through_time = xlen / fs.velocity
        flow_through_steps = max(1, int(result.flow_through_time / result.dt_recommended)) if result.dt_recommended > 0 else 1
        result.warmup_steps = int(sim.warmup_factor * flow_through_steps)
        result.total_steps = result.warmup_steps + prod_steps

    # collision frequencies
    try:
        for sp_a in mix.species_ids:
            for sp_b in mix.species_ids:
                key = f"{sp_a}-{sp_b}"
                result.collision_freqs[key] = flow_free.collision_freq(sp_a, sp_b)
    except Exception:
        pass

    return result


def auto_grid(state, derived: DerivedQuantities, n_mfp: float = 2.0) -> tuple[int, int, int]:
    """Suggest cell counts so each cell is ~n_mfp * mfp_free wide."""
    geo = state.geometry
    mfp = derived.mfp_free
    if mfp <= 0:
        return geo.n_cells_x, geo.n_cells_y, geo.n_cells_z

    xlen = abs(geo.xhi - geo.xlo)
    ylen = abs(geo.yhi - geo.ylo)
    zlen = abs(geo.zhi - geo.zlo)

    nx = max(1, round(xlen / (n_mfp * mfp)))
    ny = max(1, round(ylen / (n_mfp * mfp)))
    nz = max(1, round(zlen / (n_mfp * mfp))) if geo.dimension == 3 else 1
    return nx, ny, nz
