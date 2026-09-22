"""Pure-Python SPARTA case definition.  No Qt, safe on HPC nodes."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Optional

# Allow running from the repo root without installation
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# The group's canonical SPARTA data files, shipped in the package.
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEFAULT_SPECIES_LIST = "species.list"
DEFAULT_COLLISION_LIST = "collision.list"
DEFAULT_CHEM_FILE = "air12_sp_complete.chem"

# Resolution presets for non-experts: standard DSMC targets. mfp_per_cell sizes
# the streamwise grid from the freestream MFP; ppc, warmup, and samples scale up
# with fidelity. AMR then refines the shock below these baselines.
RESOLUTION_PRESETS = {
    "coarse": dict(mfp_per_cell=4.0, n_ppc=15, warmup_factor=15.0, samples=4000),
    "medium": dict(mfp_per_cell=2.0, n_ppc=30, warmup_factor=25.0, samples=8000),
    "fine":   dict(mfp_per_cell=1.0, n_ppc=60, warmup_factor=40.0, samples=16000),
}


# ── Sub-configs ───────────────────────────────────────────────────────────────

@dataclass
class FreestreamConfig:
    velocity: float = 0.0       # m/s
    temperature: float = 0.0    # K
    t_vib: float = 0.0          # K  (0 = use temperature)
    pressure: float = 0.0       # Pa (0 = derive from rho+T)
    density: float = 0.0        # kg/m³


@dataclass
class WallConfig:
    temperature: float = 300.0
    accommodation: float = 1.0         # diffuse BC accommodation coeff
    # Set wall_boundary (a box face) for the 1D stagnation-line wall via
    # bound_modify; leave it empty when a surface mesh carries the wall.
    wall_boundary: str = ""            # "" | "xhi" | "xlo" | "yhi" | ...
    surf_collide_id: str = "wall"      # name used in surf_collide / bound_modify
    # Surface chemistry (carbon ablation etc.)
    surf_react_enabled: bool = False
    surf_react_file: str = ""          # prob-style file, e.g. "wall.chem"
    surf_react_id: str = "wall"        # name used in surf_react / bound_modify
    surf_react_style: str = "prob"     # "prob" | "adsorb" | ...


@dataclass
class PhysicsConfig:
    collision_model: str = "vss"       # "vss" | "none"
    alpha: float = 1.0                 # VSS angular scattering (1.0 = VHS)
    rotate: str = "smooth"             # "no" | "smooth"
    vibrate: str = "smooth"            # "no" | "smooth" | "discrete"
    rot_relax_model: str = "parker"    # "constant" | "parker"
    vib_relax_model: str = "MW"        # "constant" | "MW" | "MWHTP" | "MWHTHB" | "BIRD"
    use_cell_temperature: bool = True  # CTFL: usecelltemperature yes on collide line
    parker_off: bool = False           # CTFL: parkeroff yes on collide line
    # CTFL collide_modify extensions (see AdditionalCommands.readme)
    exchange_style: str = "doubleprohibit"   # "" | "doubleprohibit"
    mgds_collide: bool = True                # CTFL MGDS collision algorithm
    # Reactions
    react_enabled: bool = False
    react_file: str = ""               # user-supplied chem file referenced by `react`
    react_style: str = "tce"           # "tce" | "qk"
    react_modify_partial_energy: Optional[bool] = None  # None = omit react_modify line


@dataclass
class GridConfig:
    xlo: float = 0.0
    xhi: float = 0.0
    ylo: float = 0.0
    yhi: float = 0.0
    zlo: float = -1e-4
    zhi: float = 1e-4
    dimension: int = 2
    symmetry: str = "none"             # "none" | "axisymmetric"
    boundary_x: str = "oo"
    boundary_y: str = "oo"
    boundary_z: str = "p"
    n_cells_x: int = 100
    n_cells_y: int = 100
    n_cells_z: int = 1
    balance_mode: str = "cell"         # "cell" | "part" — argument to balance_grid rcb
    surface_file: str = ""
    surface_units: str = "m"           # "m" | "mm" | "cm" | "in"
    surface_scale: float = 1.0


@dataclass
class SimConfig:
    n_ppc: int = 20
    warmup_factor: float = 5.0
    # fix ave/grid is a block average; the engine enforces window == freq*samples
    # so samples never overlap. Change freq/samples together, not window.
    freq: int = 5                       # Nevery  — sample interval (steps)
    samples: int = 5000                 # Nrepeat — samples per window
    window: int = 0                     # Nfreq   — 0 = auto (= freq * samples)
    fnum_override: float = 0.0          # 0 = auto
    dt_factor: float = 0.1
    flow_volume_mode: str = "auto"      # "auto" | "sparta" | "computed"
    flow_volume_sparta: float = 0.0
    n_cells_amr: int = 0               # 0 = use uniform n_cells_x*y*z
    # target_cells>0 sizes the initial NX×NY from this budget + domain aspect
    # ratio (overriding n_cells_x/y), then MFP-checks it.
    target_cells: int = 0              # 0 = use explicit GridConfig.n_cells_x/y
    max_cells_per_mfp: float = 3.0     # warn if a cell edge exceeds this × MFP
    # Inflow (freestream injection)
    inflow_enabled: bool = True        # fix emit/face + create_particles n 0
    inflow_face: str = "xlo"           # box face the freestream enters through
    inflow_mixture: str = "air"        # mixture name to emit
    # --- Restart ---
    restart_file: str = ""             # e.g. "restart/case.restart" — "" disables


@dataclass
class AMRConfig:
    """Adaptive mesh refinement + steady-state detection loop.

    The run loop advances one averaging window at a time; when the relative
    change in particle count drops below `np_tol` it refines on the per-cell
    Knudsen number, re-balances, and writes a restart. Non-experts: keep the
    defaults; lower `kn_refine_below` to refine harder, raise `np_tol` to stop
    sooner.
    """
    enabled: bool = True
    max_iter: int = 20                 # hard cap on steady-state windows
    np_tol: float = 0.1                # relative Δnp to declare steady state
    n_loops: int = 1                   # number of refine passes to perform
    kn_field: str = "kn"               # fix ID that holds the per-cell Kn (column 2)
    kn_refine_below: float = 0.5       # refine cells with Kn < this
    kn_coarsen_above: float = 100.0    # coarsen cells with Kn > this
    cells_split: tuple = (2, 2, 1)     # child cells per refined cell (Nx Ny Nz)
    write_restart_on_converge: bool = True


@dataclass
class ComputeDumpConfig:
    # Grid quantities
    grid_n: bool = True
    grid_nrho: bool = True
    grid_u: bool = True
    grid_v: bool = True
    grid_w: bool = False
    grid_temp: bool = True
    grid_trot: bool = True
    grid_tvib: bool = True
    grid_erot: bool = False
    grid_evib: bool = False
    grid_press: bool = False
    grid_ke: bool = False
    # Surf quantities (only emitted when surface_file is set)
    surf_n: bool = False
    surf_press: bool = True
    surf_ke: bool = True
    surf_erot: bool = True
    surf_evib: bool = True
    surf_etot: bool = True
    # named_ids emits physically-named computes (gridprops, Tt, Tr, Tv, nrho_sp,
    # kn) for the 1D stagnation-line style instead of numbered ones.
    named_ids: bool = True
    thermal_temp: bool = True           # use thermal/grid (drift-subtracted) for T_tr
    per_species_nrho: bool = True       # compute nrho per species (grid all species nrho)
    knudsen: bool = True                # compute lambda/grid Kn field (needs the two above)
    dump_geometry: bool = True          # include id xlo ylo xhi yhi in the grid dump
    # Stats
    stats_nevery: int = 100
    stats_fields: str = "step cpu np nattempt ncoll nscoll nreact"
    # Dump filenames
    grid_dump_file: str = "data/grid.*.dat"
    surf_dump_file: str = "surf.*.dat"
    particle_dump_enabled: bool = False
    particle_dump_file: str = "particle.*.dat"
    particle_dump_nevery: int = 0       # 0 = use window


# ── Main case object ──────────────────────────────────────────────────────────

class SPARTACase:
    """A fully-specified SPARTA DSMC case.

    Provide freestream conditions (any two of density/pressure/temperature), the
    box `domain`, `grid` counts, and either a `surface_file` (mesh mode) or a
    `wall.wall_boundary` (1D stagnation-line mode).  See examples/ for usage.
    """

    def __init__(
        self,
        name: str = "sparta_case",
        species: Optional[dict[str, float]] = None,
        *,
        velocity: float = 0.0,
        temperature: float = 0.0,
        t_vib: float = 0.0,
        density: float = 0.0,
        pressure: float = 0.0,
        domain: tuple = (0.0, 0.0, 0.0, 0.0, -1e-4, 1e-4),
        grid: tuple = (100, 100, 1),
        surface_file: str = "",
        surface_units: str = "m",
        surface_scale: float = 1.0,
        dimension: int = 2,
        symmetry: str = "none",
        boundary_x: str = "oo",
        boundary_y: str = "oo",
        boundary_z: str = "p",
        species_file: str = "",
        extra_species: Optional[list] = None,
        resolution: str = "",              # "coarse"|"medium"|"fine": sets grid+ppc
        # sub-configs (override everything above if supplied)
        freestream: Optional[FreestreamConfig] = None,
        wall: Optional[WallConfig] = None,
        physics: Optional[PhysicsConfig] = None,
        sim: Optional[SimConfig] = None,
        compute_dump: Optional[ComputeDumpConfig] = None,
        amr: Optional[AMRConfig] = None,
    ):
        self.name = name
        self.species_dict: dict[str, float] = dict(species or {})
        # Reaction-product species that start at zero fraction but must be
        # declared (e.g. carbon-ablation products C, C2, CO, CN ...).  When
        # provided, this is authoritative and the library will NOT try to
        # auto-infer products from a built-in reaction set.
        self.extra_species: list = list(extra_species or [])

        # Freestream
        self.freestream = freestream or FreestreamConfig(
            velocity=velocity,
            temperature=temperature,
            t_vib=t_vib,
            density=density,
            pressure=pressure,
        )

        # Grid / geometry
        xlo, xhi, ylo, yhi, zlo, zhi = (domain + (0.0,) * 6)[:6]
        nx, ny, nz = (tuple(grid) + (1,) * 3)[:3]
        self.grid = GridConfig(
            xlo=xlo, xhi=xhi, ylo=ylo, yhi=yhi, zlo=zlo, zhi=zhi,
            dimension=dimension, symmetry=symmetry,
            boundary_x=boundary_x, boundary_y=boundary_y, boundary_z=boundary_z,
            n_cells_x=int(nx), n_cells_y=int(ny), n_cells_z=int(nz),
            surface_file=surface_file,
            surface_units=surface_units,
            surface_scale=surface_scale,
        )

        self.wall = wall or WallConfig()
        self.physics = physics or PhysicsConfig()
        self.sim = sim or SimConfig()
        self.compute_dump = compute_dump or ComputeDumpConfig()
        self.amr = amr or AMRConfig()

        # Locate species.json.  Prefer the copy shipped inside the package
        # (works when pip-installed), then fall back to the repo root (dev mode).
        if species_file:
            self.species_file = species_file
        else:
            _pkg_data = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "data", "species.json")
            _repo_root = os.path.join(_ROOT, "species.json")
            self.species_file = (
                _pkg_data if os.path.isfile(_pkg_data)
                else _repo_root if os.path.isfile(_repo_root)
                else ""
            )

        # Run compute engine immediately so .derived is always available
        self._derived = None
        self._compute()

        # A resolution preset sizes the streamwise grid from the freestream MFP
        # and sets ppc/warmup/samples, then recomputes. Done after the first
        # compute because it needs the MFP.
        if resolution:
            self._apply_resolution(resolution)

    def _apply_resolution(self, level: str):
        """Size the grid + sampling from a coarse/medium/fine preset."""
        if level not in RESOLUTION_PRESETS:
            raise ValueError(f"resolution must be one of {sorted(RESOLUTION_PRESETS)}")
        p = RESOLUTION_PRESETS[level]
        mfp = self._derived.mfp_free
        if mfp > 0:
            g = self.grid
            cell = p["mfp_per_cell"] * mfp
            g.n_cells_x = max(1, round(abs(g.xhi - g.xlo) / cell))
            g.n_cells_y = max(1, round(abs(g.yhi - g.ylo) / cell))
        self.sim.n_ppc = p["n_ppc"]
        self.sim.warmup_factor = p["warmup_factor"]
        self.sim.samples = p["samples"]
        self._compute()

    # ── Compute ───────────────────────────────────────────────────────────────

    def _compute(self):
        from .engine import compute as _compute, build_mixture_from_dict
        self._derived = _compute(self, self.species_file)

    @property
    def derived(self):
        """DerivedQuantities from the last compute run."""
        return self._derived

    def recompute(self):
        """Re-run the engine after mutating any config fields."""
        self._compute()
        return self

    # ── Output ────────────────────────────────────────────────────────────────

    def generate(self, dt_override: float = 0.0) -> str:
        """Return the full SPARTA input script as a string."""
        from .generate import generate as _gen
        return _gen(self, self._derived, dt_override=dt_override)

    def write(self, path: str, dt_override: float = 0.0) -> str:
        """Write the SPARTA input script to *path* and return the path."""
        script = self.generate(dt_override=dt_override)
        with open(path, "w") as f:
            f.write(script)
        return path

    # ── Turnkey package ───────────────────────────────────────────────────────

    def write_package(
        self,
        out_dir: str = ".",
        *,
        in_filename: str = "",
        make_data_dir: bool = True,
        make_restart_dir: bool = True,
        write_readme: bool = True,
        dt_override: float = 0.0,
    ) -> dict:
        """Write the .in script, output dirs, summary, and README to *out_dir*.

        Returns a map of artifact name → path. Species/collision/chem files are
        not written; SPARTA's default databases are supplied alongside the run.
        """
        out = os.path.abspath(out_dir)
        os.makedirs(out, exist_ok=True)
        written: dict[str, str] = {}

        in_name = in_filename or f"{self.name}.in"
        in_path = os.path.join(out, in_name)
        self.write(in_path, dt_override=dt_override)
        written["input"] = in_path

        # Companion restart script: reads the grid the main run saves
        # (write_grid grid.adapted) and just samples — no warmup-length AMR.
        if getattr(self, "amr", None) and self.amr.enabled and self.wall.wall_boundary:
            from .generate import generate as _gen
            restart_name = f"{os.path.splitext(in_name)[0]}_restart.in"
            with open(os.path.join(out, restart_name), "w") as f:
                f.write(_gen(self, self._derived, dt_override=dt_override,
                             from_grid="grid.adapted"))
            written["restart_input"] = os.path.join(out, restart_name)

        # Copy the group's canonical data files so the case is self-contained;
        # the .in references these by name (species.list, collision.list, chem).
        import shutil
        for key, name in (("species", DEFAULT_SPECIES_LIST),
                          ("collision", DEFAULT_COLLISION_LIST)):
            shutil.copyfile(os.path.join(_DATA_DIR, name), os.path.join(out, name))
            written[key] = os.path.join(out, name)
        if self.physics.react_enabled:
            chem = os.path.basename(self.physics.react_file) or DEFAULT_CHEM_FILE
            shutil.copyfile(os.path.join(_DATA_DIR, DEFAULT_CHEM_FILE),
                            os.path.join(out, chem))
            written["gas_chem"] = os.path.join(out, chem)

        # Surface chemistry is Arrhenius in the wall temperature, so it is
        # generated per case rather than copied.
        if self.wall.surf_react_enabled:
            from .wall_chem import write_wall_chem
            wchem = os.path.basename(self.wall.surf_react_file) or "wall.chem"
            write_wall_chem(self.wall.temperature, os.path.join(out, wchem))
            written["wall_chem"] = os.path.join(out, wchem)

        # --- Output directories referenced by the script ---
        if make_data_dir:
            data_ref = os.path.dirname(self.compute_dump.grid_dump_file)
            if data_ref:
                d = os.path.join(out, data_ref)
                os.makedirs(d, exist_ok=True)
                written["data_dir"] = d

        if make_restart_dir:
            restart_ref = self.sim.restart_file
            if not restart_ref and getattr(self, "amr", None) and self.amr.enabled \
                    and self.amr.write_restart_on_converge:
                restart_ref = "restart/case.restart"
            rdir = os.path.dirname(restart_ref)
            if rdir:
                d = os.path.join(out, rdir)
                os.makedirs(d, exist_ok=True)
                written["restart_dir"] = d

        sp = os.path.join(out, f"{self.name}.summary.txt")
        with open(sp, "w") as f:
            f.write(self.summary(full=True))
        written["summary"] = sp

        if write_readme:
            p = os.path.join(out, "README.md")
            with open(p, "w") as f:
                f.write(self._generate_readme(in_name, written))
            written["readme"] = p

        return written

    def _generate_readme(self, in_name: str, artifacts: dict) -> str:
        from .readme import generate_readme
        return generate_readme(self, in_name, artifacts)

    def summary(self, full: bool = False) -> str:
        """Human-readable derived-quantities summary; full=True adds the grid,
        DSMC, and averaging details for the *.summary.txt log."""
        d = self._derived
        if d.error:
            return f"Error: {d.error}"
        lines = [
            f"Case: {self.name}",
            f"  Mach              {d.mach:.4f}",
            f"  Speed of sound    {d.speed_of_sound:.2f} m/s",
            f"  γ_mix             {d.gamma_mix:.4f}",
            f"  n∞                {d.n_free:.4e} m⁻³",
            f"  λ∞  (mfp)        {d.mfp_free:.4e} m",
            f"  τ∞  (coll time)  {d.tau_free:.4e} s",
            f"  Kn∞               {d.kn_free:.4e}",
        ]
        if d.T_shock:
            lines += [
                f"  — Normal shock —",
                f"  T₂                {d.T_shock:.1f} K",
                f"  λ₂                {d.mfp_shock:.4e} m",
                f"  τ₂                {d.tau_shock:.4e} s",
            ]
        lines += [
            f"  dt (recommended)  {d.dt_recommended:.4e} s",
            f"  fnum              {d.fnum:.4e}",
            f"  Flow volume       {d.flow_volume:.4e} m³",
            f"  Cells (fnum)      {d.n_cells:,}",
            f"  Warmup steps      {d.warmup_steps:,}",
            f"  Total steps       {d.total_steps:,}",
        ]

        if full:
            g = self.grid
            s = self.sim
            lines += [
                "",
                "── Initial grid (before AMR) ─────────────────────────",
                f"  Domain (x)        {abs(g.xhi-g.xlo):.4e} m",
                f"  Domain (y)        {abs(g.yhi-g.ylo):.4e} m",
                f"  Cells             {d.n_cells_x} × {d.n_cells_y} = "
                f"{d.n_cells_x*d.n_cells_y:,}",
                f"  Cell dx           {d.grid_dx:.4e} m  ({1.0/d.cells_per_mfp_x:.2f} MFP)"
                if d.cells_per_mfp_x else f"  Cell dx           {d.grid_dx:.4e} m",
                f"  Cell dy           {d.grid_dy:.4e} m  ({1.0/d.cells_per_mfp_y:.2f} MFP)"
                if d.cells_per_mfp_y else f"  Cell dy           {d.grid_dy:.4e} m",
                f"  Cells per MFP     {d.cells_per_mfp_x:.2f} (x), {d.cells_per_mfp_y:.2f} (y)",
            ]
            if d.grid_warning:
                lines += [
                    "",
                    "  ⚠ GRID RESOLUTION WARNING",
                    f"    {d.grid_warning}",
                ]
            lines += [
                "",
                "── Averaging statistics (fix ave/grid) ───────────────",
                f"  freq (Nevery)     {s.freq}   (sample every {s.freq} steps)",
                f"  samples (Nrepeat) {s.samples}",
                f"  window (Nfreq)    {s.window}   (= freq × samples)",
                "",
                "── DSMC parameters ───────────────────────────────────",
                f"  Particles/cell    {s.n_ppc}",
                f"  Timestep factor   {s.dt_factor}  (dt = factor × collision time)",
                f"  Warmup factor     {s.warmup_factor}× flow-through time",
            ]
            if getattr(self, "amr", None) and self.amr.enabled:
                a = self.amr
                lines += [
                    "",
                    "── AMR (adaptive refinement) ─────────────────────────",
                    f"  Steady-state tol  {a.np_tol} (relative Δnp)",
                    f"  Refine passes     {a.n_loops}",
                    f"  Refine below Kn   {a.kn_refine_below}",
                    f"  Coarsen above Kn  {a.kn_coarsen_above}",
                    f"  Max windows       {a.max_iter}",
                ]
        return "\n".join(lines)

    def print_summary(self):
        print(self.summary())

    # ── TOML / JSON I/O ───────────────────────────────────────────────────────

    @classmethod
    def from_toml(cls, path: str) -> "SPARTACase":
        """Load a case from a TOML file."""
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            import tomli as tomllib  # pip install tomli on older Pythons
        with open(path, "rb") as f:
            data = tomllib.load(f)
        return cls._from_dict(data, base_dir=os.path.dirname(os.path.abspath(path)))

    @classmethod
    def from_json(cls, path: str) -> "SPARTACase":
        """Load a case from a JSON file (GUI save format)."""
        import json
        with open(path) as f:
            data = json.load(f)
        return cls._from_gui_dict(data)

    @classmethod
    def _from_dict(cls, d: dict, base_dir: str = "") -> "SPARTACase":
        """Build from a flat/nested TOML dict."""
        def _get(section: str, key: str, default=None):
            return d.get(section, {}).get(key, d.get(key, default))

        fs_d  = d.get("freestream", d)
        geo_d = d.get("geometry",   d)
        sim_d = d.get("simulation", d)
        phy_d = d.get("physics",    d)
        wal_d = d.get("wall",       d)
        cd_d  = d.get("compute_dump", {})
        amr_d = d.get("amr",        {})

        def _fill(dc_cls, src):
            import dataclasses
            kwargs = {}
            for f in dataclasses.fields(dc_cls):
                if f.name in src:
                    val = src[f.name]
                    # TOML has no tuples — coerce list back to tuple where the
                    # dataclass default is a tuple (e.g. cells_split).
                    if isinstance(f.default, tuple) and isinstance(val, list):
                        val = tuple(val)
                    kwargs[f.name] = val
            return dc_cls(**kwargs)

        # domain tuple
        xlo = geo_d.get("xlo", 0.0); xhi = geo_d.get("xhi", 0.0)
        ylo = geo_d.get("ylo", 0.0); yhi = geo_d.get("yhi", 0.0)
        zlo = geo_d.get("zlo", -1e-4); zhi = geo_d.get("zhi", 1e-4)
        grid = (geo_d.get("n_cells_x", 100),
                geo_d.get("n_cells_y", 100),
                geo_d.get("n_cells_z", 1))

        # surface path: resolve relative to TOML location
        surf = geo_d.get("surface_file", "")
        if surf and base_dir and not os.path.isabs(surf):
            surf = os.path.join(base_dir, surf)

        sp_file = d.get("species_file", "")
        if sp_file and base_dir and not os.path.isabs(sp_file):
            sp_file = os.path.join(base_dir, sp_file)

        return cls(
            name=d.get("name", "sparta_case"),
            species=d.get("species", {}),
            extra_species=d.get("extra_species", []),
            domain=(xlo, xhi, ylo, yhi, zlo, zhi),
            grid=grid,
            surface_file=surf,
            surface_units=geo_d.get("surface_units", "m"),
            surface_scale=geo_d.get("surface_scale", 1.0),
            dimension=geo_d.get("dimension", 2),
            symmetry=geo_d.get("symmetry", "none"),
            boundary_x=geo_d.get("boundary_x", "oo"),
            boundary_y=geo_d.get("boundary_y", "oo"),
            boundary_z=geo_d.get("boundary_z", "p"),
            species_file=sp_file,
            freestream=_fill(FreestreamConfig, fs_d),
            wall=_fill(WallConfig, wal_d),
            physics=_fill(PhysicsConfig, phy_d),
            sim=_fill(SimConfig, sim_d),
            compute_dump=_fill(ComputeDumpConfig, cd_d),
            amr=_fill(AMRConfig, amr_d) if amr_d else None,
        )

    @classmethod
    def _from_gui_dict(cls, data: dict) -> "SPARTACase":
        """Re-hydrate from a GUI JSON save file."""
        import dataclasses

        def _fill(dc_cls, src: dict):
            kwargs = {}
            for f in dataclasses.fields(dc_cls):
                if f.name in src and not isinstance(src[f.name], (dict, list)):
                    kwargs[f.name] = src[f.name]
            return dc_cls(**kwargs)

        geo = data.get("geometry", {})
        sim = data.get("simulation", {})
        sp_list = data.get("species_list", [])
        species = {e["species_id"]: e["mol_frac"] for e in sp_list if e.get("species_id")}

        return cls(
            name=data.get("case_name", "sparta_case"),
            species=species,
            domain=(geo.get("xlo", 0), geo.get("xhi", 0),
                    geo.get("ylo", 0), geo.get("yhi", 0),
                    geo.get("zlo", -1e-4), geo.get("zhi", 1e-4)),
            grid=(geo.get("n_cells_x", 100), geo.get("n_cells_y", 100), geo.get("n_cells_z", 1)),
            surface_file=geo.get("surface_file", ""),
            surface_units=geo.get("surface_units", "m"),
            surface_scale=geo.get("surface_scale", 1.0),
            dimension=geo.get("dimension", 2),
            symmetry=geo.get("symmetry", "none"),
            boundary_x=geo.get("boundary_x", "oo"),
            boundary_y=geo.get("boundary_y", "oo"),
            boundary_z=geo.get("boundary_z", "p"),
            species_file=data.get("species_file", ""),
            freestream=_fill(FreestreamConfig, data.get("freestream", {})),
            wall=_fill(WallConfig, data.get("wall", {})),
            physics=_fill(PhysicsConfig, data.get("physics", {})),
            sim=_fill(SimConfig, sim),
            compute_dump=_fill(ComputeDumpConfig, data.get("compute_dump", {})),
            amr=_fill(AMRConfig, data.get("amr", {})) if data.get("amr") else None,
        )

    def to_toml(self) -> str:
        """Serialise case to a TOML string."""
        lines = [f'name = "{self.name}"']
        if self.extra_species:
            _es = ", ".join(f'"{s}"' for s in self.extra_species)
            lines.append(f"extra_species = [{_es}]")
        lines.append("")
        lines.append("[species]")
        for sp, frac in self.species_dict.items():
            lines.append(f"{sp} = {frac}")
        lines += [
            "",
            "[freestream]",
            f"velocity    = {self.freestream.velocity}",
            f"temperature = {self.freestream.temperature}",
            f"t_vib       = {self.freestream.t_vib}",
            f"density     = {self.freestream.density}",
            f"pressure    = {self.freestream.pressure}",
            "",
            "[wall]",
            f"temperature      = {self.wall.temperature}",
            f"accommodation    = {self.wall.accommodation}",
            f"wall_boundary    = \"{self.wall.wall_boundary}\"",
            f"surf_collide_id  = \"{self.wall.surf_collide_id}\"",
            f"surf_react_enabled = {str(self.wall.surf_react_enabled).lower()}",
            f"surf_react_file  = \"{self.wall.surf_react_file}\"",
            f"surf_react_id    = \"{self.wall.surf_react_id}\"",
            f"surf_react_style = \"{self.wall.surf_react_style}\"",
            "",
            "[geometry]",
            f"dimension   = {self.grid.dimension}",
            f"symmetry    = \"{self.grid.symmetry}\"",
            f"xlo = {self.grid.xlo}",
            f"xhi = {self.grid.xhi}",
            f"ylo = {self.grid.ylo}",
            f"yhi = {self.grid.yhi}",
            f"zlo = {self.grid.zlo}",
            f"zhi = {self.grid.zhi}",
            f"boundary_x = \"{self.grid.boundary_x}\"",
            f"boundary_y = \"{self.grid.boundary_y}\"",
            f"boundary_z = \"{self.grid.boundary_z}\"",
            f"n_cells_x = {self.grid.n_cells_x}",
            f"n_cells_y = {self.grid.n_cells_y}",
            f"n_cells_z = {self.grid.n_cells_z}",
            f"balance_mode  = \"{self.grid.balance_mode}\"",
            f"surface_file  = \"{self.grid.surface_file}\"",
            f"surface_units = \"{self.grid.surface_units}\"",
            f"surface_scale = {self.grid.surface_scale}",
            "",
            "[simulation]",
            f"n_ppc           = {self.sim.n_ppc}",
            f"warmup_factor   = {self.sim.warmup_factor}",
            f"freq            = {self.sim.freq}",
            f"samples         = {self.sim.samples}",
            f"window          = {self.sim.window}",
            f"target_cells    = {self.sim.target_cells}",
            f"max_cells_per_mfp = {self.sim.max_cells_per_mfp}",
            f"fnum_override   = {self.sim.fnum_override}",
            f"dt_factor       = {self.sim.dt_factor}",
            f"flow_volume_mode   = \"{self.sim.flow_volume_mode}\"",
            f"flow_volume_sparta = {self.sim.flow_volume_sparta}",
            f"n_cells_amr        = {self.sim.n_cells_amr}",
            f"inflow_enabled  = {str(self.sim.inflow_enabled).lower()}",
            f"inflow_face     = \"{self.sim.inflow_face}\"",
            f"inflow_mixture  = \"{self.sim.inflow_mixture}\"",
            f"restart_file    = \"{self.sim.restart_file}\"",
            "",
            "[physics]",
            f"collision_model   = \"{self.physics.collision_model}\"",
            f"alpha             = {self.physics.alpha}",
            f"rotate            = \"{self.physics.rotate}\"",
            f"vibrate           = \"{self.physics.vibrate}\"",
            f"rot_relax_model   = \"{self.physics.rot_relax_model}\"",
            f"vib_relax_model   = \"{self.physics.vib_relax_model}\"",
            f"use_cell_temperature = {str(self.physics.use_cell_temperature).lower()}",
            f"parker_off        = {str(self.physics.parker_off).lower()}",
            f"exchange_style    = \"{self.physics.exchange_style}\"",
            f"mgds_collide      = {str(self.physics.mgds_collide).lower()}",
            f"react_enabled     = {str(self.physics.react_enabled).lower()}",
            f"react_file        = \"{self.physics.react_file}\"",
            f"react_style       = \"{self.physics.react_style}\"",
        ]
        if self.physics.react_modify_partial_energy is not None:
            lines.append(
                f"react_modify_partial_energy = "
                f"{str(self.physics.react_modify_partial_energy).lower()}"
            )
        lines += [
            "",
            "[compute_dump]",
            f"named_ids        = {str(self.compute_dump.named_ids).lower()}",
            f"thermal_temp     = {str(self.compute_dump.thermal_temp).lower()}",
            f"per_species_nrho = {str(self.compute_dump.per_species_nrho).lower()}",
            f"knudsen          = {str(self.compute_dump.knudsen).lower()}",
            f"grid_trot        = {str(self.compute_dump.grid_trot).lower()}",
            f"grid_tvib        = {str(self.compute_dump.grid_tvib).lower()}",
            f"dump_geometry    = {str(self.compute_dump.dump_geometry).lower()}",
            f"stats_nevery     = {self.compute_dump.stats_nevery}",
            f"stats_fields     = \"{self.compute_dump.stats_fields}\"",
            f"grid_dump_file   = \"{self.compute_dump.grid_dump_file}\"",
            "",
            "[amr]",
            f"enabled          = {str(self.amr.enabled).lower()}",
            f"max_iter         = {self.amr.max_iter}",
            f"np_tol           = {self.amr.np_tol}",
            f"n_loops          = {self.amr.n_loops}",
            f"kn_refine_below  = {self.amr.kn_refine_below}",
            f"kn_coarsen_above = {self.amr.kn_coarsen_above}",
            f"cells_split      = [{', '.join(str(c) for c in self.amr.cells_split)}]",
            f"write_restart_on_converge = {str(self.amr.write_restart_on_converge).lower()}",
        ]
        return "\n".join(lines) + "\n"

    def write_toml(self, path: str) -> str:
        """Write case definition as TOML."""
        with open(path, "w") as f:
            f.write(self.to_toml())
        return path
