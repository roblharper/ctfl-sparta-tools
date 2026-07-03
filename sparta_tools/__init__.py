"""sparta_tools — headless SPARTA DSMC pre-processing API.

No Qt dependency. Safe to import on HPC nodes.

Typical usage::

    from sparta_tools import SPARTACase
    case = SPARTACase(name="run01", species={"N2": 0.79, "O2": 0.21},
                      velocity=3000, temperature=200, density=1e-4,
                      domain=(-0.1, 0.1, 0.0, 0.04, -1e-4, 1e-4),
                      grid=(100, 80, 1))
    case.write("run01.in")          # write SPARTA .in file
    print(case.derived.mach)        # access computed quantities
"""

from .case import (
    SPARTACase,
    FreestreamConfig,
    WallConfig,
    PhysicsConfig,
    GridConfig,
    SimConfig,
    ComputeDumpConfig,
)
from .generate import generate
from . import engine as _engine

__all__ = [
    "SPARTACase",
    "FreestreamConfig",
    "WallConfig",
    "PhysicsConfig",
    "GridConfig",
    "SimConfig",
    "ComputeDumpConfig",
    "generate",
]
