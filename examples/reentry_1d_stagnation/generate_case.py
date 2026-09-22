"""1D axisymmetric stagnation-line re-entry case (blunt-body, the turnkey path).

Give freestream conditions, the wall, and the nose radius; the tool sizes the
grid, timestep, fnum (with radius weighting), and gridcut, and writes a two-run
package: run 1 warms up and refines the grid (write_grid), run 2 reads that grid
and samples. No DSMC expertise needed.

Boundary conditions for the stagnation line:
  xlo = freestream inflow    xhi = wall (diffuse + Park carbon ablation)
  ylo = axis of symmetry     yhi = radial outflow (decelerated gas vents here)
The radial extent is a fraction of the nose radius so the vent develops.
"""

from sparta_tools import SPARTACase, WallConfig, PhysicsConfig, AMRConfig

# Pick a fidelity: "coarse" (fast laptop check), "medium" (default), or "fine"
# (production). It sizes the grid off the mean free path and sets particles/cell,
# warmup, and sampling. Everything else stays fixed.
RESOLUTION = "medium"

R_NOSE = 2.75 * 0.0254             # capsule nose radius (m)
XLEN   = 0.005                     # streamwise extent (freestream + shock + wall)
YEXT   = R_NOSE / 20               # radial vent extent (fraction of nose radius)

case = SPARTACase(
    name="reentry_1d",
    species={"N2": 0.79, "O2": 0.21},
    # gas (air12) + Park carbon surface products; undeclared species are dropped.
    extra_species=["NO", "N", "O", "CO", "CN", "C", "C2", "C3", "CO2"],
    velocity=4236.0, temperature=634.0, density=1.57e-3,
    domain=(-XLEN, 0.0, 0.0, YEXT, -1e-4, 1e-4),
    dimension=2, symmetry="axisymmetric",
    resolution=RESOLUTION,            # grid + ppc + warmup + samples
    wall=WallConfig(
        temperature=1626.0, wall_boundary="xhi",
        surf_react_enabled=True,
        surf_react_file="wall.chem",
    ),
    physics=PhysicsConfig(react_enabled=True, react_file="air12_sp_complete.chem"),
    amr=AMRConfig(n_loops=2, max_iter=16, kn_refine_below=1.0),
)

artifacts = case.write_package("reentry_1d")
d, g = case.derived, case.grid
print(f"[{RESOLUTION}]  Mach {d.mach:.2f}  Kn∞ {d.kn_free:.2e}  T₂ {d.T_shock:.0f} K")
print(f"grid {g.n_cells_x}x{g.n_cells_y}  {d.grid_dx/d.mfp_free:.1f} MFP/cell  "
      f"ppc {case.sim.n_ppc}  warmup {case.sim.warmup_factor}x")
for name, path in artifacts.items():
    print(f"  {name}: {path}")
