from mixture import Mixture
from itertools import combinations_with_replacement
import math
from dataclasses import dataclass

PI = math.pi
BOLTZ = 1.380649e-23


@dataclass
class _CollisionPair:
    species_a: str
    species_b: str
    dref: float
    mreduced: float
    tref: float
    omega: float
    nu: float = 0.0

    def __post_init__(self):
        self.nu = self.omega - 0.5


class Flow:
    def __init__(self, mixture: Mixture, flow_quantities: dict):
        self.mixture = mixture
        self.flow_quantities = flow_quantities
        self._validate()
        self.mass_mix = sum(
            self.mixture.species[s].mol_frac * self.mixture.species[s].molmass
            for s in self.mixture.species_ids
        )
        self.u = flow_quantities['u']
        self.T_tr, self.P, self.rho, self.n = self._resolve_thermo(flow_quantities)
        self._compute_mixture_properties()
        self._build_combinations()

    def _validate(self):
        thermo_present = {'T', 'P', 'rho'} & self.flow_quantities.keys()
        if 'u' not in self.flow_quantities:
            raise ValueError("Missing required key 'u'")
        if len(thermo_present) < 2:
            raise ValueError("At least two of T, P, rho must be provided")

    def _resolve_thermo(self, fq: dict) -> tuple:
        """Resolve the full thermodynamic state from any two of T, P, rho."""
        T = fq.get('T')
        P = fq.get('P')
        rho = fq.get('rho')
        if rho is not None:
            n = rho / self.mass_mix
            if T is None:
                T = P / (n * BOLTZ)
            elif P is None:
                P = n * BOLTZ * T
        else:
            n = P / (BOLTZ * T)
            rho = n * self.mass_mix
        return T, P, rho, n

    def _build_combinations(self):
        self.pairs = {}
        for species_a, species_b in combinations_with_replacement(self.mixture.species_ids, 2):
            sp_a = self.mixture.species[species_a]
            sp_b = self.mixture.species[species_b]
            # tref taken from species A (SPARTA VSS convention — flag if cross-species pairs differ)
            self.pairs[f"{species_a}-{species_b}"] = _CollisionPair(
                species_a=species_a,
                species_b=species_b,
                dref=(sp_a.diameter + sp_b.diameter) / 2,
                mreduced=(sp_a.molmass * sp_b.molmass) / (sp_a.molmass + sp_b.molmass),
                tref=sp_a.tref,
                omega=(sp_a.omega + sp_b.omega) / 2,
            )

    def _get_pair(self, s: str, q: str) -> _CollisionPair:
        key = f"{s}-{q}"
        return self.pairs.get(key) or self.pairs[f"{q}-{s}"]

    def mean_free_path(self) -> float:
        lambda_mix = 0.0
        for s in self.mixture.species_ids:
            sp_s = self.mixture.species[s]
            inverse_lambda = 0.0
            for q in self.mixture.species_ids:
                pair = self._get_pair(s, q)
                sp_q = self.mixture.species[q]
                temp_term = (pair.tref / self.T_tr) ** pair.nu
                sqrt_term = 1 + (sp_s.molmass / sp_q.molmass)
                inverse_lambda += (
                    temp_term * sp_q.mol_frac * self.n * PI * pair.dref**2 * math.sqrt(sqrt_term)
                )
            lambda_mix += sp_s.mol_frac / inverse_lambda
        return lambda_mix

    def mean_collision_time(self) -> float:
        tau_mix = 0.0
        for s in self.mixture.species_ids:
            sp_s = self.mixture.species[s]
            inverse_tau = 0.0
            for q in self.mixture.species_ids:
                pair = self._get_pair(s, q)
                sp_q = self.mixture.species[q]
                temp_term = (self.T_tr / pair.tref) ** (0.5 - pair.nu)
                sqrt_term = (2 * PI * BOLTZ * pair.tref) / pair.mreduced
                inverse_tau += (
                    temp_term * 2 * sp_q.mol_frac * self.n * pair.dref**2 * math.sqrt(sqrt_term)
                )
            tau_mix += sp_s.mol_frac / inverse_tau
        return tau_mix

    def _compute_mixture_properties(self):
        self.gamma_mix = sum(
            self.mixture.species[s].mol_frac * self.mixture.species[s].gamma
            for s in self.mixture.species_ids
        )
        self.a = math.sqrt(self.gamma_mix * BOLTZ * self.T_tr / self.mass_mix)
        self.M = self.u / self.a
