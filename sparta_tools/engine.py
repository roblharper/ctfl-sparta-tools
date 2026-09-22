"""Headless compute engine — wraps Flow/Mixture/shock, no Qt dependency."""

from __future__ import annotations

import os
import sys
import math
from dataclasses import dataclass, field
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from species import Species
from mixture import Mixture
from flow import Flow
from shock import normal_shock


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
    # MFP-aware grid diagnostics
    n_cells_x: int = 0                 # resolved streamwise cell count
    n_cells_y: int = 0                 # resolved wall-normal cell count
    cells_per_mfp_x: float = 0.0       # mfp_free / grid_dx  (>1 = finer than MFP)
    cells_per_mfp_y: float = 0.0       # mfp_free / grid_dy
    grid_warning: str = ""             # non-empty if cells are too coarse for DSMC
    collision_freqs: dict = field(default_factory=dict)
    error: str = ""


def build_mixture_from_dict(species_dict: dict[str, float], species_file: str) -> Optional[Mixture]:
    """Build Mixture from {species_id: mol_frac}; returns None on failure."""
    if not species_dict:
        return None
    total = sum(species_dict.values())
    if total <= 0:
        return None
    normalised = {k: v / total for k, v in species_dict.items() if v > 0}
    try:
        return Mixture(species_dict=normalised, species_file=species_file)
    except Exception:
        return None


def _polygon_area(pts: list) -> float:
    """Shoelace formula for polygon area from list of (x, y) tuples."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n))
    return abs(area) * 0.5


def _surf_polygon_area(surf_path: str) -> float:
    """Parse a 2D SPARTA .surf file and return the enclosed polygon area."""
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
                    break
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


def _resolve_flow_volume(case, box_volume: float) -> float:
    sim = case.sim
    mode = sim.flow_volume_mode
    if mode == "sparta" and sim.flow_volume_sparta > 0:
        return sim.flow_volume_sparta
    if mode == "computed":
        surf_path = case.grid.surface_file
        if surf_path and os.path.isfile(surf_path):
            geo = case.grid
            zlen = abs(geo.zhi - geo.zlo) if geo.dimension == 3 else 1.0
            area = _surf_polygon_area(surf_path)
            if area > 0:
                return max(0.0, box_volume - area * zlen)
    return box_volume


def compute(case, species_file: str, L_ref: float = 1.0) -> DerivedQuantities:
    """Run all DSMC calculations for *case*.  L_ref in metres (for Kn)."""
    result = DerivedQuantities()

    mix = build_mixture_from_dict(case.species_dict, species_file)
    if mix is None:
        result.error = "Define at least one species with nonzero mole fraction."
        return result

    fs = case.freestream
    fq: dict = {"u": fs.velocity}

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
        result.error = "Provide at least two of: temperature, pressure, density."
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

    tau_ref = result.tau_shock if result.tau_shock else result.tau_free
    result.dt_recommended = case.sim.dt_factor * tau_ref
    result.dt_conservative = 0.01 * tau_ref

    geo = case.grid
    sim = case.sim
    xlen = abs(geo.xhi - geo.xlo)
    ylen = abs(geo.yhi - geo.ylo)
    zlen = abs(geo.zhi - geo.zlo) if geo.dimension == 3 else 1.0

    # SPARTA revolves axisymmetric cells about y=0: V = pi*(yhi^2-ylo^2)*xlen
    # (grid.cpp). Using the 2D unit-depth volume here makes fnum wrong by orders
    # of magnitude, which either starves or explodes particle creation.
    if geo.symmetry == "axisymmetric" and geo.dimension == 2:
        box_volume = math.pi * (geo.yhi**2 - geo.ylo**2) * xlen
    else:
        box_volume = xlen * ylen * zlen
    result.flow_volume = _resolve_flow_volume(case, box_volume)

    # --- Resolve initial grid ------------------------------------------------
    # Two modes:
    #   (a) target_cells > 0 : decompose that budget into NX×NY matching the
    #       domain aspect ratio, so cells are roughly square in physical space.
    #   (b) otherwise         : use the explicit GridConfig.n_cells_x/y.
    # Either way we then check cell size against the freestream MFP and record a
    # warning if the grid is too coarse for accurate DSMC (cells should be a
    # small multiple of the MFP; ideally <~1 MFP, and always < max_cells_per_mfp).
    import math as _math

    if sim.target_cells > 0 and xlen > 0 and ylen > 0:
        aspect = xlen / ylen                       # >1 → wider than tall
        ny = max(1, int(round(_math.sqrt(sim.target_cells / aspect))))
        nx = max(1, int(round(sim.target_cells / ny)))
        geo.n_cells_x, geo.n_cells_y = nx, ny
        geo.n_cells_z = 1

    nx = geo.n_cells_x
    ny = geo.n_cells_y
    result.n_cells_x = nx
    result.n_cells_y = ny

    uniform_cells = nx * ny * (geo.n_cells_z if geo.dimension == 3 else 1)
    result.n_cells = sim.n_cells_amr if sim.n_cells_amr > 0 else uniform_cells
    result.n_cells_uniform = uniform_cells
    result.grid_dx = xlen / nx if nx > 0 else 0.0
    result.grid_dy = ylen / ny if ny > 0 else 0.0

    # MFP-resolution diagnostics + guardrail
    if result.mfp_free > 0:
        if result.grid_dx > 0:
            result.cells_per_mfp_x = result.mfp_free / result.grid_dx
        if result.grid_dy > 0:
            result.cells_per_mfp_y = result.mfp_free / result.grid_dy
        dx_mfp = result.grid_dx / result.mfp_free if result.mfp_free else 0.0
        dy_mfp = result.grid_dy / result.mfp_free if result.mfp_free else 0.0
        worst = max(dx_mfp, dy_mfp)
        if worst > sim.max_cells_per_mfp:
            result.grid_warning = (
                f"Initial cell size is {worst:.1f}× the freestream MFP "
                f"(dx={dx_mfp:.1f} MFP, dy={dy_mfp:.1f} MFP); recommended < "
                f"{sim.max_cells_per_mfp:.0f}. Increase target_cells or rely on AMR "
                f"to refine the shock region."
            )

    if sim.fnum_override > 0:
        result.fnum = sim.fnum_override
    elif geo.symmetry == "axisymmetric" and geo.dimension == 2 and ny > 0:
        # With `global weight cell radius`, create_particles distributes particles
        # by volume/weight = 2*pi*dy_row per cell (radius and dx cancel). So ppc is
        # the same on any x-refinement -> one fnum works for the coarse AND refined
        # grid. dy_row = radial extent / ny.  (verified against create_particles.cpp)
        dy_row = (geo.yhi - geo.ylo) / ny
        result.fnum = flow_free.n * 2.0 * math.pi * dy_row / sim.n_ppc
    elif result.n_cells > 0 and result.flow_volume > 0:
        result.fnum = (flow_free.n * result.flow_volume) / (result.n_cells * sim.n_ppc)

    # Enforce the block-average coupling: window == freq * samples.
    # If window is unset (0) it is derived; if set inconsistently it is corrected
    # so the ave/grid statistics remain a clean, non-overlapping block average.
    if sim.window <= 0 or sim.window != sim.freq * sim.samples:
        sim.window = sim.freq * sim.samples
    prod_steps = sim.window
    if fs.velocity > 0 and xlen > 0 and result.dt_recommended > 0:
        result.flow_through_time = xlen / fs.velocity
        fts = max(1, int(result.flow_through_time / result.dt_recommended))
        result.warmup_steps = int(sim.warmup_factor * fts)
        result.total_steps = result.warmup_steps + prod_steps

    try:
        for sp_a in mix.species_ids:
            for sp_b in mix.species_ids:
                result.collision_freqs[f"{sp_a}-{sp_b}"] = flow_free.collision_freq(sp_a, sp_b)
    except Exception:
        pass

    return result
