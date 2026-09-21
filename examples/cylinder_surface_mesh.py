"""2D cylinder case with a surface mesh (read_surf + surf_collide).

Set a surface_file instead of a wall_boundary to run the full mesh mode, which
emits numbered grid/surf computes and surface heat-flux dumps.
"""

from sparta_tools import SPARTACase, ComputeDumpConfig, AMRConfig

case = SPARTACase(
    name="cyl_run",
    species={"N2": 0.79, "O2": 0.21},
    velocity=3000.0, temperature=200.0, density=1e-4,
    domain=(-0.034, 0.0, 0.0, 0.04, -1e-4, 1e-4),
    grid=(170, 200, 1),
    surface_file="quarter_cylinder.surf",     # placed next to the .in at run time
    compute_dump=ComputeDumpConfig(named_ids=False),   # numbered computes
    amr=AMRConfig(enabled=False),
)

print(case.write("cyl_run.in"))
print(case.summary())
