# DSMC Tools — Expansion Plan

This document outlines proposed new modules and features for the `ctfl_tools/DSMC` package.
Each section describes what the feature does, what it would contain, and how it would integrate
with the existing `Flow` / `Mixture` / `Species` stack.

---

## 1. SPARTA Input Script Writer

**Goal:** programmatically generate a complete, valid SPARTA `.input` file from Python objects
rather than maintaining hand-edited templates.

### Rationale

Looking at `experiments/dsmc.input` and `experiments/cylinder_case_heatflux.input`, every
input file shares the same structural skeleton (box, grid, species/mixture, collision model,
computes, dumps, run). SPARTA's `variable` system is perfect for a template approach — all
runtime values can be declared as variables at the top and referenced with `${}` throughout,
making the generated file easy to read and modify by hand afterward.

### Proposed API

```python
writer = SPARTAInputWriter(
    flow=flow_free,
    domain=domain,        # see §3 — Domain class
    surface="cyl.surf",   # or None for open-domain cases
    collision_file="collision.list",
)
writer.set_grid(ncells_x=531, ncells_y=478, ncells_z=1)
writer.set_simulation(
    timestep=0.1 * tau,
    warmup_steps=warmup,
    samples=10000,
    sample_freq=5,
)
writer.write("case.input")
```

### Implementation plan

1. **`SPARTAInputWriter` class** in a new `sparta_writer.py` module.
2. Build the file in ordered sections, each a method that returns a list of lines:
   - `_header()` — seed, dimension, units, boundary
   - `_box()` — `create_box` from domain bounds
   - `_grid()` — `create_grid` + `balance_grid`
   - `_global()` — `global nrho`, `global fnum`, `global vstream`, `global temp`
   - `_timestep()` — `timestep`
   - `_species()` — `species` command + `mixture` fractions block
   - `_surface()` — `read_surf` + `surf_collide` + `surf_modify` (skipped if no surface)
   - `_collide()` — `collide vss` + `collide_modify`
   - `_computes()` — standard thermal/grid computes (Tt, Tr, Tv, gridprops, nrho_species)
   - `_fixes()` — `ave/grid`, optional `ave/surf` for heat flux
   - `_dumps()` — grid and surf dump commands
   - `_run()` — `run` command
3. `fnum` and `nrho` are derived from the `Flow` object at write time.
4. Add a `heat_flux=True` flag that appends surface energy flux computes (ke, erot, evib, etot)
   and the corresponding `ave/surf` fix — matching the pattern in `cylinder_case_heatflux.input`.
5. Support optional grid adaptation block (`fix adapt`) for production runs.
6. The boundary condition string (`o o p`, `oo ro pp`, etc.) passed explicitly since it is
   geometry-dependent.

### Notes / open questions
- Should we support SPARTA's `write_grid` / `read_grid` workflow (pre-adapted grids)? If so,
  the writer needs a two-pass mode: pre-adapt script and post-adapt production script.
- SPARTA mixture fractions must sum to exactly 1 — validate and warn before writing.
- The vibrational temperature `tvib` on the mixture line (seen in `cylinder_case_heatflux.input`)
  is only needed when `vibrate discrete` is active. Make this conditional.

---

## 2. Surface File Module (`surf.py`)

**Goal:** read, validate, visualize, transform, and write SPARTA `.surf` files from Python.

### Rationale

Several scripts (e.g. `cyl_case_heatflux.py`) already contain a `scale_surface_file` helper.
`Pre-Processing-Geometry-Scripts/stl2surf.py` has more complete geometry utilities (normal
checking, plotting, deduplication, snap-to-box). These should be consolidated into a single
`Surf` class that the rest of the toolchain can use.

### Proposed API

```python
surf = Surf.read("cyl.surf")          # parse Points + Triangles (or Lines for 2D)
surf.check_airtight()                  # raise if any edge is not shared by exactly 2 triangles
surf.check_normals()                   # report fraction of outward vs inward normals
surf.fix_normals()                     # flip winding where normals point inward
surf.check_inside_domain(domain)       # raise if any point lies outside domain bounds
surf.plot(ax=None, show_normals=False) # matplotlib 2D or 3D visualization
surf.scale(factor)                     # uniform scale in place
surf.translate(dx, dy, dz=0)          # translate in place
surf.snap_to_box(domain, tol=1e-7)    # snap boundary points to exact domain bounds
surf.write("cyl_scaled.surf")          # write SPARTA .surf format
```

And a constructor for STL input (absorbing `stl2surf.py`):

```python
surf = Surf.from_stl("geometry.stl", scale=1e-3, mode='3d')
```

### Implementation plan

1. **`Surf` class** in `surf.py`.
2. Internal representation: `pts` (N×3 numpy array), `elements` (M×2 for Lines or M×3 for Triangles),
   `mode` (`'2d'` or `'3d'`).
3. **Airtight check (3D):** build an edge-to-face adjacency map. Every edge must appear in exactly
   2 triangles. Report boundary edges (appear once) and non-manifold edges (appear 3+).
4. **Normal check:** for each triangle, compute N = (p2-p1)×(p3-p1) and dot with (centroid - mid).
   A watertight outward-normal mesh should have 100% outward normals.
5. **Visualization:**
   - 2D: `matplotlib` line plot with optional normal arrows (already in `stl2surf.py`).
   - 3D: `matplotlib` `Poly3DCollection` (already in `stl2surf.py`) or optionally `pyvista` for
     interactive viewing (already used in `Pre-Processing-Geometry-Scripts/verify.py`).
6. **STL reader**: absorb `read_stl` + `dedup` + `quantize_points` from `stl2surf.py`. Keep as
   a `@classmethod` factory.
7. The `scale_surface_file` function in `cyl_case_heatflux.py` can be replaced by
   `surf.scale(factor); surf.write(output)`.

### Notes / open questions
- 2D `.surf` files (Lines) come from the convex hull path in `stl2surf.py`. Is that path still
  needed, or are all active cases 3D? If only 3D is used, the 2D reader still needs to exist
  for old files.
- `pyvista` is already in the Pre-Processing venv. Decide whether to add it as a dependency
  here or keep visualization optional with a `try/import` guard.

---

## 3. Domain Class (`domain.py`)

**Goal:** encapsulate the simulation box, grid parameters, and derived quantities (fnum,
flow-through time, simulation schedule) in a single object — replacing the scattered
`domain_bounds`, `domain_lengths`, `compute_fnum`, `print_grid_plan` functions that are
copy-pasted across experiment scripts.

### Rationale

`cyl_case_heatflux.py` and `sphere_cone_case.py` both define `domain_bounds`, `domain_lengths`,
`domain_volume`, `compute_fnum`, `print_flow_properties`, and `print_grid_plan` as module-level
functions. These are nearly identical across files. The `domain.py` cache entry in `__pycache__`
suggests this was once implemented but later removed.

### Proposed API

```python
domain = Domain(
    xlo=-0.0375, xhi=0.0,
    ylo=0.0,     yhi=0.03375,
    zlo=-7.5e-5, zhi=7.5e-5,
)

# Grid sizing
domain.set_grid_from_mfp(flow_free, n_mfp=2)   # compute ncells from mfp
domain.set_grid(ncells_x=531, ncells_y=478, ncells_z=1)  # or explicit

# Particle parameters
domain.compute_fnum(flow, n_ppc=15, flow_volume=sparta_reported_vol)

# Simulation schedule
schedule = domain.simulation_schedule(
    flow_free=flow_free,
    flow_shock=flow_shock,
    warmup_factor=5,
    samples=10000,
    sample_freq=5,
)
# schedule.warmup_steps, schedule.total_steps, schedule.dt, ...

# Reporting
domain.print_summary(flow_free, flow_shock)   # replaces print_flow_properties + print_grid_plan
```

And serialization to/from JSON so domain configs can be saved alongside mixture configs:

```python
domain.save("cyl_domain.json")
domain = Domain.load("cyl_domain.json")
```

### Implementation plan

1. **`Domain` dataclass** in `domain.py` with fields: `xlo, xhi, ylo, yhi, zlo, zhi`,
   `ncells_x, ncells_y, ncells_z`.
2. **`SimulationSchedule` dataclass**: `dt, warmup_steps, sample_freq, samples,
   averaging_window, total_steps`.
3. `domain.volume` property: box volume.
4. `domain.set_grid_from_mfp(flow, n_mfp)`: for each dimension, `ncells = round(len / (n_mfp * mfp))`.
5. `domain.compute_fnum(flow, n_ppc, flow_volume=None)`: `fnum = n * V / (N_cells * n_ppc)`.
   `flow_volume` defaults to `domain.volume` but can be overridden with a SPARTA-reported value.
6. `domain.flow_through_time(u)` and `domain.flow_through_steps(u, dt)`.
7. `domain.print_summary(...)` consolidates the `print_flow_properties` + `print_grid_plan`
   pattern found in every experiment, with a consistent output format.
8. The `domain.check_surf_inside(surf)` method delegates to `Surf.check_inside_domain(self)`.

### Notes / open questions
- Some experiments use a pre-adapt grid and a post-adapt cell count from SPARTA output. The
  `compute_fnum` method should make it easy to pass either the pre-adapt total cells or the
  post-adapt cell count.
- The `Domain` class can also hold the surface file reference so that `SPARTAInputWriter`
  can pull everything it needs from one object.

---

## 4. Integration with `Pre-Processing-Geometry-Scripts`

**Goal:** decide how much of `stl2surf.py` to absorb vs. keep as a standalone CLI.

### Current state

`stl2surf.py` is a self-contained CLI script with full STL → SPARTA conversion, normal
fixing, plotting, decimation, and snap-to-box. It is mature and works well as-is.

### Proposed approach

- Keep `stl2surf.py` as a **CLI tool** (it has a well-designed argparse interface and is
  useful standalone).
- Extract the **core functions** (`read_stl`, `dedup`, `ensure_outward_normals_3d`,
  `snap_to_box`, `write_surf_3d`, `plot_surf_3d`) into the new `surf.py` module and import
  them from `stl2surf.py` — so the CLI continues to work but the DSMC package can also use
  them programmatically.
- This avoids code duplication without breaking the existing CLI workflow.

---

## 5. Flagged items from the cleanup (equations to verify)

These were noticed during the code review. **No code was changed** — these are questions for
you to evaluate against your references before any modification.

### 5a. Cross-species `tref` in `_build_combinations`

```python
tref = sp_a.tref  # only species A's tref used for mixed pairs (e.g. N2-O2)
```

SPARTA's VSS model uses the self-collision reference temperature. For cross-species pairs,
different implementations use different conventions (e.g. only species A, geometric mean,
or averaging). Worth verifying this matches how `collision.list` was generated and how SPARTA
itself handles it when you give it a `collision.list` with per-species tref values.

### 5b. Factor of 2 in `mean_collision_time`

```python
inverse_tau += temp_term * 2 * sp_q.mol_frac * self.n * pair.dref**2 * math.sqrt(sqrt_term)
```

The factor of `2` appears uniformly for all species pairs including self-collisions (s == q).
In Bird (1994), the collision rate for like-molecule pairs already includes a factor of 2 from
counting (each collision involves two identical particles), while unlike pairs do not. Verify
whether this factor is intentional and consistent with the reference.

### 5c. `gamma` assuming fully excited vibrational modes

```python
f = 3 + self.rotdof + self.vibdof
return (f + 2) / f
```

This is the classical equipartition result, treating all vibrational modes as fully excited.
At temperatures below the vibrational characteristic temperature, this overestimates the
effective gamma and therefore underestimates the speed of sound. This affects `flow.M` and
the downstream `normal_shock` calculation. For high-enthalpy cases (T >> vibtemp) it's
fine; for cold freestream conditions it may introduce error. A quantum-corrected gamma
could be added as a separate property if needed.

---

## Implementation order (suggested)

1. **`Domain`** — most immediately useful; eliminates the copy-paste across experiments.
2. **`Surf`** — needed for Domain's `check_surf_inside` and for the writer.
3. **`SPARTAInputWriter`** — highest payoff once Domain and Surf exist.
4. **STL integration** — lower priority; `stl2surf.py` already works well standalone.
