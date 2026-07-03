"""Thermochemistry pre-processing calculator.

Provides partition functions, internal energy quantities, and temperature-
dependent specific-heat properties needed for DSMC simulation setup and
validation.  All functions are pure — no side effects, no global state.

Textbook basis: Boyd & Schwartzentruber, *Nonequilibrium Gas Dynamics and
Molecular Simulation* (2017).  Section references below are to that text.

§5.1 — Partition Functions (Eqs. 3.86, 3.115, 3.123, 3.127)
§5.2 — Internal Energy and Specific Heat (Eqs. 3.126, 3.128, 3.132, D.9)
"""

from __future__ import annotations

import math
from species import Species

# ── Physical constants ────────────────────────────────────────────────────────
BOLTZ  = 1.380649e-23   # Boltzmann constant  (J / K)
PLANCK = 6.62607015e-34 # Planck constant     (J · s)
PI     = math.pi

# ── Electronic state data (§5.1, Eq. 3.115) ──────────────────────────────────
# Each entry is a list of (degeneracy g_i, characteristic temperature θ_i [K]).
# Source: Boyd & Schwartzentruber Ch. 3 §3.5; NIST Atomic Spectra Database.
# Only levels with θ_i ≲ 50,000 K are included — higher levels contribute
# negligibly below 20,000 K and are omitted for numerical stability.
#
# Neutral 5-species air
# ---------------------
# N : ground ⁴S (g=4); first excited at ~28,000 K — negligible for aerospace
# O : ground ³P₂ (g=5); two low-lying fine-structure levels at 228 K and 326 K
#     that matter even at room temperature
# N₂: ground X¹Σ⁺ᵍ (g=1); first excited at ~71,000 K → Q_el ≈ 1 always
# O₂: ground X³Σ⁻ᵍ (g=3); first excited at ~11,900 K
# NO: doublet ground state (g=2+2 at 0 and 174 K) — both levels always occupied
#
# Ions (approximate; extend when ionized-species K_e is needed)
# -------------------------------------------------------------
# Ions carry significant electronic excitation; values here are first-order
# estimates sufficient for partition-function ratios up to ~10,000 K.

EL_STATES: dict[str, list[tuple[int, float]]] = {
    # Neutral atoms
    "N":   [(4, 0.0), (10, 27664.0), (6, 41492.0)],
    "O":   [(5, 0.0), (3, 228.0), (1, 326.0), (5, 22830.0), (1, 48621.0)],
    # Neutral diatomics
    "N2":  [(1, 0.0)],
    "O2":  [(3, 0.0), (2, 11391.0), (1, 18985.0)],
    "NO":  [(2, 0.0), (2, 174.0)],
    "CO":  [(1, 0.0)],
    "CO2": [(1, 0.0)],
    # Noble gases / other
    "Ar":  [(1, 0.0)],
    "He":  [(1, 0.0)],
    # Ions — ground-state degeneracy only; extend for full K_e calculations
    "N+":  [(1, 0.0)],
    "O+":  [(4, 0.0)],
    "N2+": [(2, 0.0)],
    "O2+": [(4, 0.0)],
    "NO+": [(1, 0.0)],
    "e":   [(2, 0.0)],   # electron spin degeneracy
}


# ── §5.1 Partition Functions ──────────────────────────────────────────────────

def q_tr(m: float, T: float, V: float) -> float:
    """Translational partition function (Eq. 3.86).

    Q_tr = V · (2π m k T / h²)^(3/2)

    Parameters
    ----------
    m : float
        Molecular mass (kg).
    T : float
        Temperature (K).
    V : float
        Volume (m³).  Pass ``V=1.0`` to get the per-unit-volume form used in
        equilibrium-constant ratios for dissociation reactions.

    Returns
    -------
    float
        Translational partition function (dimensionless when V is in m³).
    """
    return V * ((2 * PI * m * BOLTZ * T) / PLANCK**2) ** 1.5


def q_rot(species: Species, T: float) -> float:
    """Rotational partition function — classical continuous limit (Eq. 3.123).

    Q_rot = T / (σ · θ_rot)

    where σ = 2 for homonuclear diatomics (N₂, O₂, N₂⁺, O₂⁺) and σ = 1
    for heteronuclear molecules (NO, CO, …).  Returns 1.0 for atoms
    (rotdof = 0) since they carry no rotational modes.

    Valid when T ≫ θ_rot (the classical limit).  For air species θ_rot is
    2–6 K, so this holds well above ~30 K.

    Parameters
    ----------
    species : Species
        Species dataclass with ``rottemp`` (θ_rot) and ``homonuclear`` set.
    T : float
        Translational/rotational temperature (K).

    Returns
    -------
    float
        Rotational partition function (dimensionless).
    """
    if species.rotdof == 0 or species.rottemp == 0.0:
        return 1.0
    sigma = 2 if species.homonuclear else 1
    return T / (sigma * species.rottemp)


def q_vib(species: Species, T: float) -> float:
    """Vibrational partition function — SHO (Eq. 3.127).

    Q_vib = 1 / (1 − exp(−θ_vib / T))

    Returns 1.0 for atoms (vibtemp = 0) since they carry no vibrational modes.

    Parameters
    ----------
    species : Species
        Species dataclass with ``vibtemp`` (θ_vib) set.
    T : float
        Vibrational temperature (K).

    Returns
    -------
    float
        Vibrational partition function (dimensionless).
    """
    if species.vibtemp == 0.0:
        return 1.0
    x = species.vibtemp / T
    # Guard against overflow for very low T (x → ∞ → Q_vib → 1)
    if x > 700:
        return 1.0
    return 1.0 / (1.0 - math.exp(-x))


def q_el(species_id: str, T: float) -> float:
    """Electronic partition function (Eq. 3.115).

    Q_el = Σᵢ gᵢ · exp(−θᵢ / T)

    Sums over all electronic levels stored in ``EL_STATES``.  The ground
    state has θ₀ = 0, so its term is always gᵢ exactly.

    Parameters
    ----------
    species_id : str
        Species identifier matching a key in ``EL_STATES`` (e.g. ``"N2"``).
    T : float
        Temperature (K).

    Returns
    -------
    float
        Electronic partition function (dimensionless).

    Raises
    ------
    KeyError
        If ``species_id`` is not found in ``EL_STATES``.
    """
    if species_id not in EL_STATES:
        raise KeyError(
            f"No electronic state data for '{species_id}'. "
            f"Available species: {sorted(EL_STATES)}"
        )
    return sum(g * math.exp(-theta / T) for g, theta in EL_STATES[species_id])


def q_int(species: Species, species_id: str, T: float) -> float:
    """Total internal partition function Q_int = Q_rot · Q_vib · Q_el.

    The translational partition function is excluded here because it cancels
    in equilibrium-constant ratios for most reactions (or must be handled
    separately for recombination — see §5.5).

    Parameters
    ----------
    species : Species
        Species dataclass.
    species_id : str
        Species identifier for ``EL_STATES`` lookup.
    T : float
        Temperature (K).  Assumes T_tr = T_rot = T_vib (equilibrium).

    Returns
    -------
    float
        Internal partition function (dimensionless).
    """
    return q_rot(species, T) * q_vib(species, T) * q_el(species_id, T)


# ── §5.2 Internal Energy and Specific Heat ────────────────────────────────────

def zeta_vib(theta_vib: float, T: float) -> float:
    """Temperature-dependent vibrational degrees of freedom — SHO (Eq. 3.132).

    ζ_vib(θ_vib, T) = 2(θ_vib/T)² · exp(θ_vib/T) / (exp(θ_vib/T) − 1)²

    Limits:
      - T → 0  :  ζ_vib → 0  (frozen, vibrational mode inactive)
      - T → ∞  :  ζ_vib → 2  (fully excited, matches classical ``vibdof=2``)

    Parameters
    ----------
    theta_vib : float
        Characteristic vibrational temperature θ_vib (K).
    T : float
        Vibrational temperature (K).

    Returns
    -------
    float
        Effective vibrational degrees of freedom (dimensionless, 0 ≤ ζ_vib ≤ 2).
    """
    if theta_vib == 0.0:
        return 0.0
    x = theta_vib / T
    if x > 700:
        return 0.0
    ex = math.exp(x)
    return 2.0 * x**2 * ex / (ex - 1.0)**2


def e_vib(theta_vib: float, T: float) -> float:
    """Mean vibrational energy per molecule — SHO (Eq. 3.128).

    ε_vib = k · θ_vib / (exp(θ_vib / T) − 1)

    Parameters
    ----------
    theta_vib : float
        Characteristic vibrational temperature θ_vib (K).
    T : float
        Vibrational temperature (K).

    Returns
    -------
    float
        Mean vibrational energy per molecule (J).
    """
    if theta_vib == 0.0:
        return 0.0
    x = theta_vib / T
    if x > 700:
        return 0.0
    return BOLTZ * theta_vib / (math.exp(x) - 1.0)


def t_vib_from_energy(theta_vib: float, e_vib_mean: float) -> float:
    """Vibrational temperature inferred from mean vibrational energy (Eq. D.9).

    Inverts the SHO relation:

        T_vib = θ_vib / ln(1 + k θ_vib / ε_vib)

    Used when post-processing SPARTA output where the sampled cell-average
    vibrational energy ``<ε_vib>`` is available.

    Parameters
    ----------
    theta_vib : float
        Characteristic vibrational temperature θ_vib (K).
    e_vib_mean : float
        Mean vibrational energy per molecule (J).

    Returns
    -------
    float
        Vibrational temperature (K).  Returns 0.0 if ``e_vib_mean`` ≤ 0.
    """
    if e_vib_mean <= 0.0:
        return 0.0
    return theta_vib / math.log(1.0 + (BOLTZ * theta_vib) / e_vib_mean)


def gamma_eff(species: Species, T_tr: float, T_vib: float | None = None) -> float:
    """Temperature-dependent ratio of specific heats γ(T) using SHO ζ_vib.

    γ = (f + 2) / f,   f = 3 + ζ_rot + ζ_vib(T_vib)

    where ζ_rot = ``species.rotdof`` (classical, always fully excited for
    T > 30 K for air species) and ζ_vib is computed from the SHO formula.

    Limiting behaviour:
      - T_vib → 0   : ζ_vib → 0, γ → classical frozen-vib value
      - T_vib → ∞   : ζ_vib → 2, γ → ``species.gamma`` (fully excited)
      - T_vib = None : defaults to T_tr (equilibrium assumption)

    Parameters
    ----------
    species : Species
        Species dataclass with ``rotdof`` and ``vibtemp`` set.
    T_tr : float
        Translational temperature (K) — used for ζ_rot (always classical).
    T_vib : float, optional
        Vibrational temperature (K).  Defaults to ``T_tr``.  Pass ``0.0``
        (or a very small value) to freeze vibrational modes entirely.

    Returns
    -------
    float
        Effective ratio of specific heats (dimensionless).
    """
    T_v = T_vib if T_vib is not None else T_tr
    zv = zeta_vib(species.vibtemp, T_v) if T_v > 0.0 else 0.0
    f = 3.0 + species.rotdof + zv
    return (f + 2.0) / f
