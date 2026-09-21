"""1D axisymmetric stagnation-line re-entry case (the turnkey path).

Give freestream conditions and a wall; the tool sizes the grid, timestep, fnum,
and gridcut, then writes a ready-to-run package. No DSMC expertise needed.
"""

from sparta_tools import SPARTACase, WallConfig, PhysicsConfig

case = SPARTACase(
    name="reentry_1d",
    species={"N2": 0.79, "O2": 0.21},
    extra_species=["NO", "N", "O"],          # reaction products in the chem file
    velocity=4236.0, temperature=634.0, density=1.57e-3,
    domain=(-0.034, 0.0, 0.0, 0.04, -1e-4, 1e-4),
    grid=(200, 200, 1),
    dimension=2, symmetry="axisymmetric",
    wall=WallConfig(temperature=1626.0, wall_boundary="xhi"),
    physics=PhysicsConfig(react_enabled=True, react_file="air12_sp_complete.chem"),
)

# Writes reentry_1d.in, data/, restart/, summary, and README into ./reentry_1d/.
artifacts = case.write_package("reentry_1d")
print(f"Mach {case.derived.mach:.2f}, Kn∞ {case.derived.kn_free:.2e}")
for name, path in artifacts.items():
    print(f"  {name}: {path}")
