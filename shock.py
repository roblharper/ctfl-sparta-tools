from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow import Flow


def normal_shock(flow_upstream: "Flow") -> dict:
    """
    Rankine-Hugoniot normal shock relations with frozen composition.

    Real-gas effects enter through gamma_mix, which is computed from the
    mixture-averaged species gamma (fully-excited rotational and vibrational
    modes assumed via classical equipartition).

    Returns a flow_quantities dict suitable for constructing a downstream Flow.
    """
    gamma = flow_upstream.gamma_mix
    M1 = flow_upstream.M

    if M1 <= 1.0:
        raise ValueError(f"Upstream Mach number must be supersonic (M1={M1:.3f})")

    rho_ratio = (gamma + 1) * M1**2 / ((gamma - 1) * M1**2 + 2)
    P_ratio = (2 * gamma * M1**2 - (gamma - 1)) / (gamma + 1)
    T_ratio = P_ratio / rho_ratio      # ideal gas: T2/T1 = (P2/P1) * (rho1/rho2)

    return {
        "T": flow_upstream.T_tr * T_ratio,
        "P": flow_upstream.P * P_ratio,
        "u": flow_upstream.u / rho_ratio,  # mass conservation: rho1*u1 = rho2*u2
    }
