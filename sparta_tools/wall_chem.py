"""Park carbon surface chemistry, written at the wall temperature.

The reaction probabilities are Arrhenius in the wall temperature,
P = gamma * exp(-E / (R * T_wall)), so the file must be regenerated whenever the
wall temperature changes. Reactions P1, P2, P3, P5 of Mussoni (2024) Table 2.4;
P4 sublimation is omitted (negligible against the O flux at these temperatures).
"""

from __future__ import annotations

import math

_R = 8.314  # J/(mol*K)

# (label, reaction, sparta_type, gamma, E_kJ_per_mol)
_PARK_CARBON = [
    ("P1", "O --> CO",       "E", 0.63,  9.644),   # oxidation
    ("P2", "O2 --> CO + CO", "D", 0.50,  0.0),      # oxidation
    ("P3", "N --> CN",       "E", 0.003, 0.0),      # nitridation
    ("P5", "C3 --> NULL",    "R", 0.10,  0.0),      # C3 condensation
]


def _prob(gamma: float, e_kj: float, t_wall: float) -> float:
    if e_kj == 0.0 or t_wall <= 0:
        return gamma
    return gamma * math.exp(-e_kj * 1e3 / (_R * t_wall))


def write_wall_chem(t_wall: float, out_path: str) -> str:
    """Write the Park carbon surf_react prob file evaluated at *t_wall* (K)."""
    lines = [
        f"# Park surface model at Tw = {t_wall:.0f} K: reactions P1, P2, P3, P5 of Mussoni (2024) Table 2.4.",
        "",
    ]
    for _label, reaction, rtype, gamma, e_kj in _PARK_CARBON:
        lines.append(reaction)
        lines.append(f"{rtype}\tS\t{_prob(gamma, e_kj, t_wall):.5f}")
        lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines).rstrip() + "\n")
    return out_path
