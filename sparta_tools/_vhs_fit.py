"""Blottner viscosity fit → VHS/VSS collision parameters (INTERNAL).

This module is intentionally NOT part of the public API (note the leading
underscore, and its absence from ``sparta_tools/__init__.py``).  It exists so a
technically-capable user who wants to understand or extend how the collision
parameters in ``species.json`` were produced can reach it deliberately:

    from sparta_tools._vhs_fit import compute_vhs_for_species
    omega, d_ref = compute_vhs_for_species("CN")

Casual users should not touch species / collision parameters.  The generated
``species.list`` / ``collision.list`` come straight from ``species.json``, which
is the single source of truth.

Methodology
-----------
Each species' viscosity is described by a Blottner curve fit,

    mu(T) = 0.1 * exp[(A*ln T + B)*ln T + C]        [kg/m/s]

We sample mu over a hypersonic temperature range, least-squares fit ln(mu) vs
ln(T) to get the VHS viscosity exponent ``omega`` (= slope), then invert the VHS
like-species viscosity relation (Bird 1994 §2.3) to recover the reference
diameter ``d_ref`` at T_ref = 273.15 K.

Data provenance
---------------
The Blottner coefficients below are transcribed from
``sparta_tools/data/blottner_air_carbon.md`` (originally the continuum-CFD input
file ``12species_air_carbon.chem``):

  * Alba, C. R. et al., J. Spacecraft & Rockets, 2015.  DOI: 10.2514/1.A33266
  * Park, C. et al., "Chemical-Kinetic Parameters of Hyperbolic Earth Entry."
    DOI: 10.2514/2.6582
  * H. Zhang, PhD thesis, App. A Table 1 p.130.  DOI: 10.13023/etd.2015.002

Reference: Blottner et al. (1971); VHS formula from Bird (1994) §2.3.
"""

from __future__ import annotations

import math

kB   = 1.380649e-23
TREF = 273.15  # standard VHS reference temperature (K)

# Blottner coefficients (A, B, C) and molecular mass m [kg].
#   mu = 0.1 * exp[(A*ln T + B)*ln T + C]
# Source: sparta_tools/data/blottner_air_carbon.md  (see module docstring).
BLOTTNER = {
    "N2":  dict(A= 2.68142e-2,  B= 3.177838e-1,  C=-1.13155513e1, m=4.65e-26),
    "O2":  dict(A= 4.49290e-2,  B=-8.261580e-2,  C=-9.20194750e0, m=5.31e-26),
    "NO":  dict(A= 4.36378e-2,  B=-3.355110e-2,  C=-9.57674300e0, m=4.98e-26),
    "N":   dict(A= 1.15572e-2,  B= 6.031679e-1,  C=-1.24327495e1, m=2.325e-26),
    "O":   dict(A= 2.03144e-2,  B= 4.294404e-1,  C=-1.16031403e1, m=2.65e-26),
    "C":   dict(A=-0.0001,      B= 0.79280,      C=-13.4154,      m=1.994e-26),
    "C2":  dict(A=-0.00310,     B= 0.69200,      C=-12.6127,      m=3.988e-26),
    "C3":  dict(A=-0.01470,     B= 0.881100,     C=-13.50510,     m=5.983e-26),
    "CO":  dict(A=-0.01952739,  B= 1.013295,     C=-13.97873,     m=4.65e-26),
    "CO2": dict(A=-0.01952739,  B= 1.047818,     C=-14.32212,     m=7.31e-26),
    "CN":  dict(A= 0.0025,      B= 0.6810,       C=-12.4914,      m=4.31e-26),
}


def mu_blottner(sp, T: float) -> float:
    """Dynamic viscosity [kg/m/s] from the Blottner fit for species *sp* at *T* [K].

    *sp* is a key in :data:`BLOTTNER`, or an ``(A, B, C)`` tuple.
    """
    if isinstance(sp, str):
        A, B, C = BLOTTNER[sp]["A"], BLOTTNER[sp]["B"], BLOTTNER[sp]["C"]
    else:
        A, B, C = sp
    lnT = math.log(T)
    return 0.1 * math.exp((A * lnT + B) * lnT + C)


def fit_vhs(sp_or_abc, mass: float, T_fit_range=(1000, 30000), n_points=200) -> dict:
    """Fit VHS ``omega`` and ``d_ref`` from the Blottner viscosity curve.

    1. Evaluate Blottner mu over *T_fit_range* (log-spaced).
    2. Least-squares fit ln(mu) vs ln(T) → omega = slope.
    3. Invert the VHS like-species viscosity relation at T_ref for d_ref:

           mu_ref = 15*sqrt(2*pi*m_r*kB*T_ref)
                    / [2*(5-2*omega)*(7-2*omega)*pi*d_ref^2],   m_r = mass/2

    Returns a dict with ``omega``, ``d_ref``, ``mu_ref``, ``T_arr``, ``mu_arr``.
    """
    import numpy as np

    T_lo, T_hi = T_fit_range
    T_arr  = np.logspace(math.log10(T_lo), math.log10(T_hi), n_points)
    mu_arr = np.array([mu_blottner(sp_or_abc, T) for T in T_arr])

    lnT, lnmu = np.log(T_arr), np.log(mu_arr)
    coeffs = np.polyfit(lnT, lnmu, 1)
    omega  = float(coeffs[0])
    mu_ref = float(math.exp(coeffs[1] + omega * math.log(TREF)))

    mr          = mass / 2.0
    numerator   = 15.0 * math.sqrt(2.0 * math.pi * mr * kB * TREF)
    denominator = 2.0 * (5.0 - 2.0 * omega) * (7.0 - 2.0 * omega) * math.pi
    d_ref       = math.sqrt(numerator / (denominator * mu_ref))

    return dict(omega=omega, d_ref=d_ref, mu_ref=mu_ref, T_arr=T_arr, mu_arr=mu_arr)


def compute_vhs_for_species(sp: str, T_fit_range=(1000, 30000), n_points=200):
    """Look up *sp* in :data:`BLOTTNER`, fit, and return ``(omega, d_ref)``.

    Also prints a ``collision.list``-format line and species.json snippet.

    >>> omega, d_ref = compute_vhs_for_species("CN")
    CN   omega=0.7312  d_ref=3.8940e-10 m  (3.8940 Å)
    """
    if sp not in BLOTTNER:
        raise KeyError(f"'{sp}' not in BLOTTNER table. Add A, B, C, m first "
                       f"(see sparta_tools/data/blottner_air_carbon.md).")
    mass = BLOTTNER[sp]["m"]
    r = fit_vhs(sp, mass, T_fit_range=T_fit_range, n_points=n_points)
    omega, d_ref = r["omega"], r["d_ref"]
    print(f"{sp}   omega={omega:.4f}  d_ref={d_ref:.4e} m  ({d_ref*1e10:.4f} Å)")
    print(f"collision.list:  {sp:<4}  {d_ref:.3E}    {omega:.2f}  {TREF:.2f}"
          f"  1.0  0.0 0.0 0.0 0.0 0.0 0.0")
    return omega, d_ref


def vhs_params_table(species=None, T_fit_range=(1000, 30000)):
    """Print a summary table of omega and d_ref for species in :data:`BLOTTNER`."""
    if species is None:
        species = list(BLOTTNER.keys())
    print(f"\n{'Species':<6} {'omega':>8}  {'d_ref (m)':>12}  {'d_ref (Å)':>10}  {'mu_ref':>14}")
    print("-" * 58)
    results = {}
    for sp in species:
        r = fit_vhs(sp, BLOTTNER[sp]["m"], T_fit_range=T_fit_range)
        results[sp] = r
        print(f"{sp:<6} {r['omega']:>8.4f}  {r['d_ref']:>12.4e}  "
              f"{r['d_ref']*1e10:>10.4f}  {r['mu_ref']:>14.4e}")
    return results


if __name__ == "__main__":
    vhs_params_table()
