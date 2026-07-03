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
    accommodation: float = 1.0  # diffuse BC accommodation coeff


@dataclass
class PhysicsConfig:
    collision_model: str = "vss"       # "vss" | "none"
    alpha: float = 1.0                 # VSS angular scattering (1.0 = VHS)
    rotate: str = "smooth"             # "no" | "smooth"
    vibrate: str = "discrete"          # "no" | "smooth" | "discrete"
    rot_relax_model: str = "parker"    # "constant" | "parker"
    vib_relax_model: str = "MW"        # "constant" | "MW" | "MWHTP"
    use_cell_temperature: bool = True
    react_enabled: bool = False
    react_file: str = ""
    react_style: str = "tce"           # "tce" | "qk"


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
    surface_file: str = ""
    surface_units: str = "m"           # "m" | "mm" | "cm" | "in"
    surface_scale: float = 1.0


@dataclass
class SimConfig:
    n_ppc: int = 20
    warmup_factor: float = 5.0
    ave_nevery: int = 5
    ave_nrepeat: int = 10000
    ave_nfreq: int = 50000
    fnum_override: float = 0.0          # 0 = auto
    dt_factor: float = 0.1
    flow_volume_mode: str = "auto"      # "auto" | "sparta" | "computed"
    flow_volume_sparta: float = 0.0
    n_cells_amr: int = 0               # 0 = use uniform n_cells_x*y*z


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
    # Stats
    stats_nevery: int = 100
    stats_fields: str = "step elapsed np ncoll nattempt nreact"
    # Dump filenames
    grid_dump_file: str = "grid.*.dat"
    surf_dump_file: str = "surf.*.dat"
    particle_dump_enabled: bool = False
    particle_dump_file: str = "particle.*.dat"
    particle_dump_nevery: int = 0       # 0 = use ave_nfreq


# ── Main case object ──────────────────────────────────────────────────────────

class SPARTACase:
    """A fully-specified SPARTA DSMC case.

    Parameters
    ----------
    name : str
        Case identifier (used in the header comment and output filenames).
    species : dict[str, float]
        Species name → mole fraction.  Need not sum to 1; normalised internally.
    velocity, temperature, density, pressure
        Freestream conditions.  Provide any two of density/pressure/temperature.
    domain : tuple of 6 floats  (xlo, xhi, ylo, yhi, zlo, zhi)
        Box bounds in metres.
    grid : tuple of 3 ints  (nx, ny, nz)
        Uniform cell counts.
    surface_file : str, optional
        Path to a SPARTA .surf / STL / TIFF surface file.
    species_file : str, optional
        Path to species.json database.  Auto-detected from repo root if omitted.
    freestream, wall, physics, sim, compute_dump
        Sub-config dataclass instances for fine-grained control.

    Examples
    --------
    >>> case = SPARTACase(
    ...     name="cyl_run",
    ...     species={"N2": 0.79, "O2": 0.21},
    ...     velocity=3000, temperature=200, density=1e-4,
    ...     domain=(-0.034, 0.0, 0.0, 0.04, -1e-4, 1e-4),
    ...     grid=(170, 200, 1),
    ...     surface_file="quarter_cylinder.surf",
    ... )
    >>> case.write("cyl_run.in")
    >>> print(f"Mach {case.derived.mach:.2f}, fnum {case.derived.fnum:.3e}")
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
        # sub-configs (override everything above if supplied)
        freestream: Optional[FreestreamConfig] = None,
        wall: Optional[WallConfig] = None,
        physics: Optional[PhysicsConfig] = None,
        sim: Optional[SimConfig] = None,
        compute_dump: Optional[ComputeDumpConfig] = None,
    ):
        self.name = name
        self.species_dict: dict[str, float] = dict(species or {})

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

        # Locate species.json
        if species_file:
            self.species_file = species_file
        else:
            candidate = os.path.join(_ROOT, "species.json")
            self.species_file = candidate if os.path.isfile(candidate) else ""

        # Run compute engine immediately so .derived is always available
        self._derived = None
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

    def summary(self) -> str:
        """Return a human-readable summary of derived quantities."""
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

        def _fill(dc_cls, src):
            import dataclasses
            kwargs = {}
            for f in dataclasses.fields(dc_cls):
                if f.name in src:
                    kwargs[f.name] = src[f.name]
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
        )

    def to_toml(self) -> str:
        """Serialise case to a TOML string."""
        lines = [f'name = "{self.name}"', ""]
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
            f"temperature   = {self.wall.temperature}",
            f"accommodation = {self.wall.accommodation}",
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
            f"surface_file  = \"{self.grid.surface_file}\"",
            f"surface_units = \"{self.grid.surface_units}\"",
            f"surface_scale = {self.grid.surface_scale}",
            "",
            "[simulation]",
            f"n_ppc           = {self.sim.n_ppc}",
            f"warmup_factor   = {self.sim.warmup_factor}",
            f"ave_nevery      = {self.sim.ave_nevery}",
            f"ave_nrepeat     = {self.sim.ave_nrepeat}",
            f"ave_nfreq       = {self.sim.ave_nfreq}",
            f"fnum_override   = {self.sim.fnum_override}",
            f"dt_factor       = {self.sim.dt_factor}",
            f"flow_volume_mode   = \"{self.sim.flow_volume_mode}\"",
            f"flow_volume_sparta = {self.sim.flow_volume_sparta}",
            f"n_cells_amr        = {self.sim.n_cells_amr}",
            "",
            "[physics]",
            f"collision_model   = \"{self.physics.collision_model}\"",
            f"alpha             = {self.physics.alpha}",
            f"rotate            = \"{self.physics.rotate}\"",
            f"vibrate           = \"{self.physics.vibrate}\"",
            f"rot_relax_model   = \"{self.physics.rot_relax_model}\"",
            f"vib_relax_model   = \"{self.physics.vib_relax_model}\"",
            f"use_cell_temperature = {str(self.physics.use_cell_temperature).lower()}",
            f"react_enabled     = {str(self.physics.react_enabled).lower()}",
            f"react_file        = \"{self.physics.react_file}\"",
            f"react_style       = \"{self.physics.react_style}\"",
        ]
        return "\n".join(lines) + "\n"

    def write_toml(self, path: str) -> str:
        """Write case definition as TOML."""
        with open(path, "w") as f:
            f.write(self.to_toml())
        return path
