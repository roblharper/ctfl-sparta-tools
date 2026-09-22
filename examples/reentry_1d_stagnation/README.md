# 1D axisymmetric stagnation-line re-entry (with carbon ablation)

A blunt-body hypersonic stagnation streamline in air, with Park carbon surface
ablation at the wall. This folder reproduces the DSMC **data** exactly; plotting
is separate.

## What it models

The stagnation streamline of a 2.75-inch-nose capsule at Mach 8.7. Freestream
air enters at `xlo`, passes through a bow shock, and stagnates at the wall
(`xhi`). Boundary conditions:

| Face | Condition |
|------|-----------|
| `xlo` | freestream inflow (`fix emit/face`) |
| `xhi` | wall — diffuse @ 1626 K + Park carbon ablation (`bound_modify`) |
| `ylo` | axis of symmetry |
| `yhi` | radial outflow — decelerated gas vents here (this is what lets the flow reach steady state) |

Freestream: velocity 4236 m/s, T 634 K, ρ 1.57×10⁻³ kg/m³ → Mach 8.74,
Kn∞ 5.0×10⁻⁵, post-shock T₂ ≈ 7420 K.

## Requirements

- The CTFL SPARTA build (executable named whatever your build produces, e.g.
  `spa_mpi`). This case uses group extensions: `relax variable vibmodel`,
  `usecelltemperature`, `mgdscollide`.
- Python 3.9+ with `ctfl-sparta-tools` installed (`pip install -e .` from the repo root).

## Reproduce the data

**1. Generate the case package.**

```bash
python generate_case.py
```

This writes a `reentry_1d/` folder containing two input scripts, the data files
(species.list, collision.list, air12_sp_complete.chem, wall.chem — copied from
the group defaults; wall.chem is generated at the 1626 K wall temperature), and
the `data/` output directory.

**2. Run — two stages.** SPARTA needs no MPI for a case this size; run serial.

```bash
cd reentry_1d

# Stage 1: warm up (25 flow-throughs), let AMR refine the shock, write grid.adapted
spa_mpi -in reentry_1d.in -log log.main

# Stage 2: read the refined grid, sample the converged field
spa_mpi -in reentry_1d_restart.in -log log.restart
```

`spa_mpi` is a placeholder — use whatever your SPARTA build named the executable.
To run in parallel, `mpirun -np N spa_mpi -in ...` — but confirm `mpirun` and the
binary use the same MPI (a mismatched launcher fails at `MPI_Init`).

## What to expect

- **Stage 1** takes the bulk of the time (the 25× warmup). Watch `Np` in the log:
  it climbs then **plateaus** (mass in = mass out through wall + radial vent).
  A plateau means the stagnation flow reached steady state.
- The wall heat flux prints each window as `Window N: q_wall=... rel_dq=...`;
  `rel_dq` is the relative change (convergence indicator).
- Grid dumps land in `reentry_1d/data/grid.<step>.dat` (SPARTA text format).
- The physical result: a flat freestream, a sharp shock ~1.3 mm off the wall,
  T_tr overshooting to ~10⁴ K in thermal nonequilibrium, and CO produced at the
  wall by ablation.

## Resolution — pick one knob

Set `RESOLUTION` at the top of `generate_case.py` to `"coarse"`, `"medium"`, or
`"fine"`. It sizes the grid off the mean free path and sets particles/cell,
warmup, and sampling — no DSMC expertise needed. AMR then refines the shock below
these baselines.

| Level | Cell size | Particles/cell | Warmup | Samples | Use |
|-------|-----------|----------------|--------|---------|-----|
| coarse | 4 MFP | 15 | 15× | 4000 | fast laptop check |
| medium | 2 MFP | 30 | 25× | 8000 | default |
| fine   | 1 MFP | 60 | 40× | 16000 | production |

## Other parameters (edit `generate_case.py` to change)

| Knob | Value | Meaning |
|------|-------|---------|
| nose radius | 2.75 in | sets the radial vent extent (`R_nose/20`) |
| domain x | 5 mm | freestream + shock + wall layer |
| AMR | 2 passes | x-only refinement of the shock |

## Species

Air (N2, O2, NO, N, O) plus the gas-phase and Park carbon surface reaction
products (CO, CN, C, C2, C3, CO2). All must be declared or SPARTA silently drops
them — `generate_case.py` lists them in `extra_species`.

## Plotting (optional)

`plot_profiles.py` reads the newest grid dump and writes temperature,
density/velocity, and air/carbon species profiles along the stagnation line.
This is a convenience, not part of the data reproduction.
