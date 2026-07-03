"""Central application state — single source of truth shared across all tabs."""

from dataclasses import dataclass, field
from typing import Optional
from PySide6.QtCore import QObject, Signal


@dataclass
class FreestreamState:
    velocity: float = 0.0           # m/s
    temperature: float = 0.0        # K
    t_vib: float = 0.0              # K  (0 = use T_tr)
    pressure: float = 0.0           # Pa (0 = use rho)
    density: float = 0.0            # kg/m³


@dataclass
class MixtureEntry:
    species_id: str = ""
    mol_frac: float = 0.0


@dataclass
class WallState:
    temperature: float = 300.0    # K
    accommodation: float = 1.0    # diffuse BC accommodation coefficient


@dataclass
class PhysicsState:
    collision_model: str = "vss"         # "vss" | "none"
    alpha: float = 1.0                   # VSS scattering (1.0 = VHS behaviour)
    rotate: str = "smooth"               # "no" | "smooth"
    vibrate: str = "discrete"            # "no" | "smooth" | "discrete"
    rot_relax_model: str = "parker"      # "constant" | "parker"
    vib_relax_model: str = "MW"          # "constant" | "MW" | "MWHTP"
    use_cell_temperature: bool = True
    react_enabled: bool = False
    react_file: str = ""
    react_style: str = "tce"            # "tce" | "qk"


@dataclass
class GeometryState:
    dimension: int = 2
    symmetry: str = "none"              # "none" | "axisymmetric"
    xlo: float = 0.0
    xhi: float = 0.0
    ylo: float = 0.0
    yhi: float = 0.0
    zlo: float = -0.5
    zhi: float = 0.5
    boundary_x: str = "oo"
    boundary_y: str = "oo"
    boundary_z: str = "p"
    surface_file: str = ""
    surface_units: str = "m"           # "m" | "mm" | "cm" | "in"
    surface_scale: float = 1.0
    n_cells_x: int = 100
    n_cells_y: int = 100
    n_cells_z: int = 1
    n_mfp_per_cell: float = 2.0        # target mfp/cell for auto-grid


@dataclass
class SimulationState:
    n_ppc: int = 20                    # particles per cell
    warmup_factor: float = 5.0         # flow-through times for warmup
    # averaging window — all three can be set independently; total = Nevery * Nrepeat
    ave_nevery: int = 5                # Nevery: sample every N steps
    ave_nrepeat: int = 10000           # Nrepeat: number of samples per dump
    ave_nfreq: int = 50000             # Nfreq: how often to write (steps); = Nevery * Nrepeat
    fnum_override: float = 0.0         # 0 = auto-compute
    dt_factor: float = 0.1             # fraction of tau_shock
    # grid description for fnum
    flow_volume_mode: str = "auto"     # "auto" | "sparta" | "computed"
    flow_volume_sparta: float = 0.0    # paste from SPARTA log
    n_cells_amr: int = 0              # 0 = use uniform Nx*Ny*Nz; >0 = post-AMR count


@dataclass
class ComputeDumpState:
    # Grid compute quantities (c_grid)
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
    # Surf compute quantities (c_surf) — only active when surface file set
    surf_n: bool = False
    surf_press: bool = True
    surf_ke: bool = True
    surf_erot: bool = True
    surf_evib: bool = True
    surf_etot: bool = True
    # Stats
    stats_nevery: int = 100
    stats_fields: str = "step elapsed np ncoll nattempt nreact"
    # Dump
    grid_dump_file: str = "grid.*.dat"
    surf_dump_file: str = "surf.*.dat"
    particle_dump_enabled: bool = False
    particle_dump_file: str = "particle.*.dat"
    particle_dump_nevery: int = 0      # 0 = use ave_nfreq


@dataclass
class AppState:
    case_name: str = "new_case"
    freestream: FreestreamState = field(default_factory=FreestreamState)
    species_list: list = field(default_factory=list)  # list[MixtureEntry]
    wall: WallState = field(default_factory=WallState)
    physics: PhysicsState = field(default_factory=PhysicsState)
    geometry: GeometryState = field(default_factory=GeometryState)
    simulation: SimulationState = field(default_factory=SimulationState)
    compute_dump: ComputeDumpState = field(default_factory=ComputeDumpState)
    species_file: str = ""            # path to species.json (auto-detected)


class AppStateSignals(QObject):
    """Qt signal bus — emit changed() whenever any state mutates."""
    changed = Signal()
    species_changed = Signal()
    geometry_changed = Signal()

    def __init__(self):
        super().__init__()
        self.state = AppState()

    def notify(self):
        self.changed.emit()

    def notify_species(self):
        self.species_changed.emit()
        self.changed.emit()

    def notify_geometry(self):
        self.geometry_changed.emit()
        self.changed.emit()
