"""Generate SPARTA chemistry files from reaction databases.

TCE chemistry file format (air11species.chem style):
  Reaction line:    R1 + R2 --> P1 [+ P2]
  Parameters line:  Type Style DoF Ea A b dE

Surface chemistry file format (surf_react prob style):
  Reaction line:    R1 --> P1 [+ P2]
  Parameters line:  Type Style C1 [C2]
  where C1 = probability (pre-evaluated at wall T), C2 = catalytic energy (J)
"""

from __future__ import annotations

import math
import os

_R = 8.314  # J/(mol·K)

# ── Park 1993 11-species air TCE reactions ────────────────────────────────────
# Each entry: (reaction_str, type, style, dof, Ea_J, A_m3s, b, dE_J)
# Source: air11species.chem

_AIR11_REACTIONS: list[tuple] = [
    # ── Dissociation ──────────────────────────────────────────────────────────
    ("N2 + N --> N + N + N",    "D", "A", 1.0,  1.563e-18, 4.982e-08, -1.60, -1.563e-18),
    ("N2 + O --> N + N + O",    "D", "A", 1.0,  1.563e-18, 4.982e-08, -1.60, -1.563e-18),
    ("N2 + N2 --> N + N + N2",  "D", "A", 1.0,  1.563e-18, 1.162e-08, -1.60, -1.563e-18),
    ("N2 + O2 --> N + N + O2",  "D", "A", 1.0,  1.563e-18, 1.162e-08, -1.60, -1.563e-18),
    ("N2 + NO --> N + N + NO",  "D", "A", 1.0,  1.563e-18, 1.162e-08, -1.60, -1.563e-18),
    ("N2 + N+ --> N + N + N+",  "D", "A", 1.0,  1.563e-18, 4.982e-08, -1.60, -1.563e-18),
    ("N2 + O+ --> N + N + O+",  "D", "A", 1.0,  1.563e-18, 4.982e-08, -1.60, -1.563e-18),
    ("N2 + N2+ --> N + N + N2+","D", "A", 1.0,  1.563e-18, 1.162e-08, -1.60, -1.563e-18),
    ("N2 + O2+ --> N + N + O2+","D", "A", 1.0,  1.563e-18, 1.162e-08, -1.60, -1.563e-18),
    ("N2 + NO+ --> N + N + NO+","D", "A", 1.0,  1.563e-18, 1.162e-08, -1.60, -1.563e-18),
    ("N2 + e- --> N + N + e-",  "D", "A", 1.0,  1.563e-18, 1.661e-05, -1.60, -1.563e-18),
    ("O2 + N --> O + O + N",    "D", "A", 1.0,  8.215e-19, 1.661e-08, -1.50, -8.215e-19),
    ("O2 + O --> O + O + O",    "D", "A", 1.0,  8.215e-19, 1.661e-08, -1.50, -8.215e-19),
    ("O2 + N2 --> O + O + N2",  "D", "A", 1.0,  8.215e-19, 3.321e-09, -1.50, -8.215e-19),
    ("O2 + O2 --> O + O + O2",  "D", "A", 1.0,  8.215e-19, 3.321e-09, -1.50, -8.215e-19),
    ("O2 + NO --> O + O + NO",  "D", "A", 1.0,  8.215e-19, 3.321e-09, -1.50, -8.215e-19),
    ("O2 + N+ --> O + O + N+",  "D", "A", 1.0,  8.215e-19, 1.661e-08, -1.50, -8.215e-19),
    ("O2 + O+ --> O + O + O+",  "D", "A", 1.0,  8.215e-19, 1.661e-08, -1.50, -8.215e-19),
    ("O2 + N2+ --> O + O + N2+","D", "A", 1.0,  8.215e-19, 3.321e-09, -1.50, -8.215e-19),
    ("O2 + O2+ --> O + O + O2+","D", "A", 1.0,  8.215e-19, 3.321e-09, -1.50, -8.215e-19),
    ("O2 + NO+ --> O + O + NO+","D", "A", 1.0,  8.215e-19, 3.321e-09, -1.50, -8.215e-19),
    ("NO + N --> N + O + N",    "D", "A", 1.0,  1.042e-18, 1.827e-13,  0.00, -1.042e-18),
    ("NO + O --> N + O + O",    "D", "A", 1.0,  1.042e-18, 1.827e-13,  0.00, -1.042e-18),
    ("NO + N2 --> N + O + N2",  "D", "A", 1.0,  1.042e-18, 8.303e-15,  0.00, -1.042e-18),
    ("NO + O2 --> N + O + O2",  "D", "A", 1.0,  1.042e-18, 8.303e-15,  0.00, -1.042e-18),
    ("NO + NO --> N + O + NO",  "D", "A", 1.0,  1.042e-18, 1.827e-13,  0.00, -1.042e-18),
    ("NO + N+ --> N + O + N+",  "D", "A", 1.0,  1.042e-18, 1.827e-13,  0.00, -1.042e-18),
    ("NO + O+ --> N + O + O+",  "D", "A", 1.0,  1.042e-18, 1.827e-13,  0.00, -1.042e-18),
    ("NO + N2+ --> N + O + N2+","D", "A", 1.0,  1.042e-18, 8.303e-15,  0.00, -1.042e-18),
    ("NO + O2+ --> N + O + O2+","D", "A", 1.0,  1.042e-18, 8.303e-15,  0.00, -1.042e-18),
    ("NO + NO+ --> N + O + NO+","D", "A", 1.0,  1.042e-18, 8.303e-15,  0.00, -1.042e-18),
    # ── Recombination ─────────────────────────────────────────────────────────
    ("N + N --> N2 + N",        "S", "A", 0.0,  0.0, 4.982e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + O",        "S", "A", 0.0,  0.0, 4.982e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + N2",       "S", "A", 0.0,  0.0, 1.162e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + O2",       "S", "A", 0.0,  0.0, 1.162e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + NO",       "S", "A", 0.0,  0.0, 1.162e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + N+",       "S", "A", 0.0,  0.0, 4.982e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + O+",       "S", "A", 0.0,  0.0, 4.982e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + N2+",      "S", "A", 0.0,  0.0, 1.162e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + O2+",      "S", "A", 0.0,  0.0, 1.162e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + NO+",      "S", "A", 0.0,  0.0, 1.162e-08, -1.60, 1.563e-18),
    ("N + N --> N2 + e-",       "S", "A", 0.0,  0.0, 1.661e-05, -1.60, 1.563e-18),
    ("O + O --> O2 + N",        "S", "A", 0.0,  0.0, 1.661e-08, -1.50, 8.215e-19),
    ("O + O --> O2 + O",        "S", "A", 0.0,  0.0, 1.661e-08, -1.50, 8.215e-19),
    ("O + O --> O2 + N2",       "S", "A", 0.0,  0.0, 3.321e-09, -1.50, 8.215e-19),
    ("O + O --> O2 + O2",       "S", "A", 0.0,  0.0, 3.321e-09, -1.50, 8.215e-19),
    ("O + O --> O2 + NO",       "S", "A", 0.0,  0.0, 3.321e-09, -1.50, 8.215e-19),
    ("O + O --> O2 + N+",       "S", "A", 0.0,  0.0, 1.661e-08, -1.50, 8.215e-19),
    ("O + O --> O2 + O+",       "S", "A", 0.0,  0.0, 1.661e-08, -1.50, 8.215e-19),
    ("O + O --> O2 + N2+",      "S", "A", 0.0,  0.0, 3.321e-09, -1.50, 8.215e-19),
    ("O + O --> O2 + O2+",      "S", "A", 0.0,  0.0, 3.321e-09, -1.50, 8.215e-19),
    ("O + O --> O2 + NO+",      "S", "A", 0.0,  0.0, 3.321e-09, -1.50, 8.215e-19),
    ("N + O --> NO + N",        "S", "A", 0.0,  0.0, 1.827e-13,  0.00, 1.042e-18),
    ("N + O --> NO + O",        "S", "A", 0.0,  0.0, 1.827e-13,  0.00, 1.042e-18),
    ("N + O --> NO + N2",       "S", "A", 0.0,  0.0, 8.303e-15,  0.00, 1.042e-18),
    ("N + O --> NO + O2",       "S", "A", 0.0,  0.0, 8.303e-15,  0.00, 1.042e-18),
    ("N + O --> NO + NO",       "S", "A", 0.0,  0.0, 1.827e-13,  0.00, 1.042e-18),
    ("N + O --> NO + N+",       "S", "A", 0.0,  0.0, 1.827e-13,  0.00, 1.042e-18),
    ("N + O --> NO + O+",       "S", "A", 0.0,  0.0, 1.827e-13,  0.00, 1.042e-18),
    ("N + O --> NO + N2+",      "S", "A", 0.0,  0.0, 8.303e-15,  0.00, 1.042e-18),
    ("N + O --> NO + O2+",      "S", "A", 0.0,  0.0, 8.303e-15,  0.00, 1.042e-18),
    ("N + O --> NO + NO+",      "S", "A", 0.0,  0.0, 8.303e-15,  0.00, 1.042e-18),
    # ── Exchange-Forward ──────────────────────────────────────────────────────
    ("NO + O --> N + O2",       "E", "A", 0.0, 2.685e-19, 1.395e-17,  0.00, -2.685e-19),
    ("N2 + O --> NO + N",       "E", "A", 0.0, 5.302e-19, 1.063e-12, -1.00, -5.302e-19),
    ("N + O --> NO+ + e-",      "E", "A", 0.0, 4.404e-19, 1.461e-21,  1.00, -4.404e-19),
    ("O + O --> O2+ + e-",      "E", "A", 0.0, 1.113e-18, 1.179e-27,  2.70, -1.113e-18),
    ("N + N --> N2+ + e-",      "E", "A", 0.0, 9.319e-19, 7.307e-23,  1.50, -9.319e-19),
    ("NO+ + O --> N+ + O2",     "E", "A", 0.0, 1.066e-18, 1.661e-18,  0.50, -1.066e-18),
    ("N+ + N2 --> N2+ + N",     "E", "A", 0.0, 1.684e-19, 1.661e-18,  0.50, -1.684e-19),
    ("O2+ + N --> N+ + O2",     "E", "A", 0.0, 3.949e-19, 1.445e-16,  0.14, -3.949e-19),
    ("O+ + NO --> N+ + O2",     "E", "A", 0.0, 3.672e-19, 2.325e-25,  1.90, -3.672e-19),
    ("O2+ + N2 --> N2+ + O2",   "E", "A", 0.0, 5.619e-19, 1.644e-17,  0.00, -5.619e-19),
    ("O2+ + O --> O+ + O2",     "E", "A", 0.0, 2.485e-19, 6.642e-18, -0.09, -2.485e-19),
    ("NO+ + N --> O+ + N2",     "E", "A", 0.0, 1.767e-19, 5.646e-17, -1.08, -1.767e-19),
    ("NO+ + O2 --> O2+ + NO",   "E", "A", 0.0, 4.501e-19, 3.985e-17,  0.41, -4.501e-19),
    ("NO+ + O --> O2+ + N",     "E", "A", 0.0, 6.710e-19, 1.196e-17,  0.29, -6.710e-19),
    ("O+ + N2 --> N2+ + O2",    "E", "A", 0.0, 3.148e-19, 1.511e-18,  0.36, -3.148e-19),
    ("NO+ + N --> N2+ + O2",    "E", "A", 0.0, 4.901e-19, 1.196e-16,  0.00, -4.901e-19),
    # ── Exchange-Backward ─────────────────────────────────────────────────────
    ("N + O2 --> NO + O",       "F", "A", 0.0, 0.0, 1.395e-17,  0.00, 2.685e-19),
    ("NO + N --> N2 + O",       "F", "A", 0.0, 0.0, 1.063e-12, -1.00, 5.302e-19),
    ("NO+ + e- --> N + O",      "F", "A", 0.0, 0.0, 1.461e-21,  1.00, 4.404e-19),
    ("O2+ + e- --> O + O",      "F", "A", 0.0, 0.0, 1.179e-27,  2.70, 1.113e-18),
    ("N2+ + e- --> N + N",      "F", "A", 0.0, 0.0, 7.307e-23,  1.50, 9.319e-18),
    ("N+ + O2 --> NO+ + O",     "F", "A", 0.0, 0.0, 1.661e-18,  0.50, 1.066e-18),
    ("N2+ + N --> N+ + N2",     "F", "A", 0.0, 0.0, 1.661e-18,  0.50, 1.684e-19),
    ("N+ + O2 --> O2+ + N",     "F", "A", 0.0, 0.0, 1.445e-16,  0.14, 3.949e-19),
    ("N+ + O2 --> O+ + NO",     "F", "A", 0.0, 0.0, 2.325e-25,  1.90, 3.672e-19),
    ("N2+ + O2 --> O2+ + N2",   "F", "A", 0.0, 0.0, 1.644e-17,  0.00, 5.619e-19),
    ("O+ + O2 --> O2+ + O",     "F", "A", 0.0, 0.0, 6.642e-18, -0.09, 2.485e-19),
    ("O+ + N2 --> NO+ + N",     "F", "A", 0.0, 0.0, 5.646e-17, -1.08, 1.767e-19),
    ("O2+ + NO --> NO+ + O2",   "F", "A", 0.0, 0.0, 3.985e-17,  0.41, 4.501e-19),
    ("O2+ + N --> NO+ + O",     "F", "A", 0.0, 0.0, 1.196e-17,  0.29, 6.710e-19),
    ("N2+ + O2 --> O+ + N2",    "F", "A", 0.0, 0.0, 1.511e-18,  0.36, 3.148e-19),
    ("N2+ + O2 --> NO+ + N",    "F", "A", 0.0, 0.0, 1.196e-16,  0.00, 4.901e-19),
]

# ── Park carbon surface reactions (prob style) ────────────────────────────────
# Each entry: (label, reaction_str, rxn_type, gamma, E_kJ_per_mol, delta_E_J)
# E in kJ/mol → P = gamma * exp(-E*1e3 / (R * T_wall))
# delta_E_J: catalytic energy (optional, positive = exothermic); 0 = not specified

_PARK_CARBON_SURF: list[dict] = [
    {
        "label": "P1",
        "comment": "O + (s) + C(b) → CO + (s)  Oxidation",
        "reaction": "O --> CO",
        "type": "E",
        "gamma": 0.63,
        "E_kJ": 9.644,
        "delta_E": 0.0,
    },
    {
        "label": "P2",
        "comment": "O2 + 2(s) + 2C(b) → 2CO + 2(s)  Oxidation",
        "reaction": "O2 --> CO + CO",
        "type": "D",
        "gamma": 0.50,
        "E_kJ": 0.0,
        "delta_E": 0.0,
    },
    {
        "label": "P3",
        "comment": "N + (s) + C(b) → CN + (s)  Nitridation",
        "reaction": "N --> CN",
        "type": "E",
        "gamma": 0.003,
        "E_kJ": 0.0,
        "delta_E": 0.0,
    },
]


def _surf_prob(gamma: float, E_kJ: float, T_wall: float) -> float:
    """Evaluate P = gamma * exp(-E*1e3 / (R*T)) at the given wall temperature."""
    if E_kJ == 0.0 or T_wall <= 0:
        return gamma
    return gamma * math.exp(-E_kJ * 1e3 / (_R * T_wall))


# ── Public API ────────────────────────────────────────────────────────────────

def default_gas_reactions() -> list[dict]:
    """Return Park 1993 11-species air TCE reactions as a list of dicts."""
    result = []
    for rxn_str, rxn_type, style, dof, Ea, A, b, dE in _AIR11_REACTIONS:
        result.append({
            "reaction": rxn_str,
            "type": rxn_type,
            "style": style,
            "C1": dof,
            "C2": Ea,
            "C3": A,
            "C4": b,
            "C5": dE,
            "enabled": True,
        })
    return result


def default_surf_reactions() -> list[dict]:
    """Return Park carbon surface reactions as a list of dicts (gamma/E stored raw)."""
    return [dict(r) for r in _PARK_CARBON_SURF]


def write_tce_chem_file(
    reactions: list[dict],
    *,
    out_path: str = "",
    header: str = "",
) -> str:
    """Generate a SPARTA TCE chemistry file.

    Parameters
    ----------
    reactions : list[dict]
        Each dict has keys: reaction, type, style, C1, C2, C3, C4, C5, enabled.
    out_path : str
        If non-empty, write to file and return path.
    header : str
        Optional extra header comment (e.g. case name).
    """
    lines = [
        "# SPARTA TCE chemistry file — generated by ctfl-sparta-tools",
        "# Park 1993 11-species air model",
    ]
    if header:
        lines.append(f"# {header}")
    lines += [
        "# Format:",
        "#   Reaction",
        "#   [Type] [Style] [DoF] [Ea (J)] [A (m^3/s)] [b] [dE (J)]",
        "#",
        "# Types: D=dissociation, S=recombination, E=exchange-fwd, F=exchange-bwd",
        "",
    ]

    # Group by type for readability
    _type_comments = {
        "D": "Dissociation",
        "S": "Recombination",
        "E": "Exchange-Forward",
        "F": "Exchange-Backward",
    }
    current_type = None
    for r in reactions:
        if not r.get("enabled", True):
            continue
        t = r["type"]
        if t != current_type:
            if current_type is not None:
                lines.append("")
            lines.append(f"# {_type_comments.get(t, t)}")
            current_type = t
        lines.append(r["reaction"])
        lines.append(
            f"{r['type']} {r['style']} "
            f"{r['C1']:.1f} "
            f"{r['C2']:.3E} "
            f"{r['C3']:.3E} "
            f"{r['C4']:.2f} "
            f"{r['C5']:.3E}"
        )
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    if out_path:
        with open(out_path, "w") as f:
            f.write(content)
        return out_path
    return content


def write_surf_chem_file(
    reactions: list[dict],
    wall_temperature: float,
    *,
    out_path: str = "",
    header: str = "",
) -> str:
    """Generate a SPARTA surface chemistry file (surf_react prob style).

    Parameters
    ----------
    reactions : list[dict]
        Each dict has keys: label, comment, reaction, type, gamma, E_kJ, delta_E, enabled.
    wall_temperature : float
        Wall temperature in K — used to evaluate reaction probabilities.
    out_path : str
        If non-empty, write to file and return path.
    header : str
        Optional extra header comment.
    """
    lines = [
        "# Carbon surface chemistry reactions (prob style)",
        "# Generated by ctfl-sparta-tools",
    ]
    if header:
        lines.append(f"# {header}")
    lines += [
        f"# Wall temperature: {wall_temperature:.0f} K",
        "# Formula: P = gamma * exp(-E*1e3 / (R*T))  where E in kJ/mol, R=8.314 J/mol/K",
        "# Format:",
        "#   R1 --> P1 [+ P2]",
        "#   type style C1 [C2]",
        "# C1 = reaction probability, C2 = catalytic energy (optional, J, positive=exothermic)",
        "",
    ]

    for r in reactions:
        if not r.get("enabled", True):
            continue
        gamma  = r["gamma"]
        E_kJ   = r.get("E_kJ", 0.0)
        delta_E = r.get("delta_E", 0.0)
        prob   = _surf_prob(gamma, E_kJ, wall_temperature)
        label  = r.get("label", "")
        comment = r.get("comment", "")

        lines.append(
            f"# {label}: {comment}   gamma={gamma}  E={E_kJ} kJ/mol"
        )
        lines.append(f"# P({wall_temperature:.0f}K) = {prob:.5f}")
        lines.append(r["reaction"])
        if delta_E != 0.0:
            lines.append(f"{r['type']} S {prob:.5f} {delta_E:.4e}")
        else:
            lines.append(f"{r['type']} S {prob:.5f}")
        lines.append("")

    content = "\n".join(lines).rstrip() + "\n"
    if out_path:
        with open(out_path, "w") as f:
            f.write(content)
        return out_path
    return content
