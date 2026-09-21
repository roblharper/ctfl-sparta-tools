# ctfl-sparta-tools

Generate ready-to-run SPARTA DSMC input scripts from freestream conditions. Built
for the CTFL SPARTA build, so it emits the group's custom commands (`relax
variable vibmodel`, `usecelltemperature`, `mgdscollide`, ...). You do not need to
know DSMC to get a working script.

## Install

```bash
pip install -e .
```

## Use

CLI:

```bash
sparta-tools gen examples/reentry_1d.toml -o reentry_1d.in
sparta-tools info examples/reentry_1d.toml     # derived quantities, no file written
sparta-tools gen case.toml --set velocity=5000 --set n_ppc=50
```

Python (turnkey package — script, output dirs, summary, README):

```python
from sparta_tools import SPARTACase, WallConfig

case = SPARTACase(
    name="reentry_1d",
    species={"N2": 0.79, "O2": 0.21},
    velocity=4236.0, temperature=634.0, density=1.57e-3,
    domain=(-0.034, 0.0, 0.0, 0.04, -1e-4, 1e-4),
    grid=(200, 200, 1), dimension=2, symmetry="axisymmetric",
    wall=WallConfig(temperature=1626.0, wall_boundary="xhi"),
)
case.write_package("reentry_1d")
```

See [examples/](examples/) for the 1D stagnation-line and surface-mesh cases.

## What it sets for you

From freestream conditions the engine computes Mach, mean free path, post-shock
state, timestep, `fnum`, warm-up steps, and an MFP-checked grid. It also sets
`global gridcut` to twice the freestream MFP so ghost-cell memory stays bounded.

## Two modes

- **1D stagnation-line** (`wall.wall_boundary` set): the wall is a box face via
  `bound_modify`; the script runs an AMR steady-state loop. This is the turnkey
  path for re-entry stagnation cases.
- **Surface mesh** (`surface_file` set): the wall is a `.surf` mesh via
  `read_surf` + `surf_collide`, with surface heat-flux dumps.

## Data files

The tool does **not** generate `species.list`, `collision.list`, or the air
chemistry — those are the group's fixed default databases, bundled in
[sparta_tools/data/](sparta_tools/data/). `write_package` copies them next to the
`.in` so a generated case is self-contained. SPARTA ignores species not declared
in them, so the same files cover every case. (`gen`/CLI writes only the `.in`;
copy the three data files yourself, or use `write_package`.)
