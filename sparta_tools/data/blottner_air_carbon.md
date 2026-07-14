# Blottner viscosity coefficients & thermochemical data — 12-species air+carbon

This is the **primary-source reference data** from which the VSS/VHS collision
parameters (`omega`, `d_ref`) for the carbon-ablation species in `species.json`
were derived.  See `sparta_tools/_vhs_fit.py` for the Blottner→VHS fitting code
that turns the coefficients below into collision parameters.

**Do not casually edit `species.json` collision parameters by hand.**  If you
need to add or revise a species, add its Blottner coefficients here, re-run the
fit (`_vhs_fit.compute_vhs_for_species`), and paste the result into
`species.json`.  That keeps the database traceable to a citable source.

## Provenance

This table originates from a continuum (CFD) chemistry input file,
`12species_air_carbon.chem` ("kat's chemistry input file, based off Alba's X2
simulation"), and was reused here for the DSMC pre-processor.

- **Alba, C. R. et al.**, "Numerical Modeling of Earth Reentry Flow with Surface
  Ablation," *Journal of Spacecraft and Rockets*, 2015.
  DOI: [10.2514/1.A33266](https://doi.org/10.2514/1.A33266)
- Original chemistry model: **Park, C. et al.**, "Chemical-Kinetic Parameters of
  Hyperbolic Earth Entry."  DOI: [10.2514/2.6582](https://doi.org/10.2514/2.6582)
- Blottner constants tabulated in **Huaibao (Paul) Zhang**, PhD thesis, Appendix
  A, Table 1, p. 130.  DOI: [10.13023/etd.2015.002](https://doi.org/10.13023/etd.2015.002)

> Note: the source file explicitly excludes electron and charge-exchange
> reactions.

## Species properties

Blottner viscosity fit:  `mu = 0.1 * exp[(A·ln T + B)·ln T + C]`  [kg/m/s]

Molecular weight in amu; enthalpy of formation Δh_f in J/kg; dissociation
potential in J/kg; θ_vib is the characteristic vibrational temperature (K).
Polyatomic species (C3, CO2) list multiple vibrational modes, one per row in the
original file; they are collapsed to a representative mode here for the DSMC
single-mode model.

| Species | Mol. wt | Δh_f (J/kg) | Blottner A | Blottner B | Blottner C | θ_vib (K) | Diss. pot. (J/kg) | Charge |
|---------|--------:|------------:|-----------:|-----------:|-----------:|----------:|------------------:|:------:|
| Ar  | 39.997 |  0.0        |  8.53823671e-03 |  5.58637312e-01 | -1.17875114e+01 | 0.0    | 0.0      | 0 |
| N2  | 28.000 |  0.0        |  2.68142e-02    |  3.177838e-01   | -1.13155513e+01 | 3395.0 | 3.363e7  | 0 |
| O2  | 32.000 |  0.0        |  4.49290e-02    | -8.261580e-02   | -9.20194750e+00 | 2239.0 | 1.542e7  | 0 |
| NO  | 30.000 |  2.996123e6 |  4.36378e-02    | -3.355110e-02   | -9.57674300e+00 | 2817.0 | 2.090e7  | 0 |
| N   | 14.000 |  3.362161e7 |  1.15572e-02    |  6.031679e-01   | -1.24327495e+01 | 0.0    | 0.0      | 0 |
| O   | 16.000 |  1.543119e7 |  2.03144e-02    |  4.294404e-01   | -1.16031403e+01 | 0.0    | 0.0      | 0 |
| C   | 12.000 |  5.921100e7 | -0.0001         |  0.79280        | -13.4154000     | 0.0    | 0.000e0  | 0 |
| C2  | 24.000 |  3.483900e7 | -0.31000e-02    |  0.6920000      | -1.261270e+01   | 2668.5 | 2.457e7  | 0 |
| C3  | 36.000 |  2.306219e7 | -1.47000e-02    |  0.881100       | -1.350510e+01   | 1769.5 | 2.020e7  | 0 |
| CO2 | 44.000 | -8.932880e6 | -0.01952739     |  1.047818       | -14.32212       | 1930.0 | 6.963e6  | 0 |
| CO  | 28.000 | -4.063080e6 | -0.01952739     |  1.013295       | -13.97873       | 3121.2 | 3.831e7  | 0 |
| CN  | 26.000 |  1.679542e7 |  0.25000e-02    |  6.810000e-01   | -1.249140e+01   | 2975.3 | 2.270e7  | 0 |

### Additional vibrational modes (polyatomics)

The original file lists these extra θ_vib rows for the polyatomic species; kept
here for completeness / future multi-mode work:

- **C3**:  1769.5, 90.6, 2934.9, 90.6 K
- **CO2**: 1930.0, 960.1, 960.1, 3379.6 K

## Gas-phase reactions (Park two-temperature, Arrhenius)

Rate form:  `k = A · T^n · exp(−E_a / T_p)`, with Park two-temperature
`T_p = T^a · Tv^b`.  Units: A in cm³/mol, E_a in K.

| Reaction | A | n | E_a (K) | fwd a | fwd b | bwd a | bwd b | T_p,min (K) |
|----------|---|---|---------|-------|-------|-------|-------|-------------|
| CO2+M = CO+O+M  | 16.9e21 | -1.50 | 6.328e4 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| CO+M  = C+O+M   | 2.30e20 | -1.00 | 1.290e5 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| N2+M  = N+N+M   | 7.00e21 | -1.60 | 1.132e5 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| O2+M  = O+O+M   | 2.00e21 | -1.50 | 5.950e4 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| NO+M  = N+O+M   | 5.00e15 |  0.00 | 7.550e4 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| C2+M  = C+C+M   | 3.70e14 |  0.00 | 6.990e4 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| CN+M  = C+N+M   | 2.50e14 |  0.00 | 8.774e4 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| C3+M  = C2+C+M  | 3.70e14 |  0.00 | 6.990e4 | 0.5 | 0.5 | 1.0 | 0.0 | 800 |
| NO+O  = O2+N    | 8.40e12 |  0.00 | 1.940e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| N2+O  = NO+N    | 6.40e17 | -1.00 | 3.840e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| CO+O  = O2+C    | 3.90e13 | -0.18 | 6.920e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| CO+C  = C2+O    | 2.00e17 | -1.00 | 5.800e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| CO+N  = CN+O    | 1.00e14 |  0.00 | 3.860e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| N2+C  = CN+N    | 1.10e14 | -0.11 | 2.320e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| CN+O  = NO+C    | 1.60e13 |  0.10 | 1.460e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| CN+C  = C2+N    | 2.00e17 |  0.00 | 1.300e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| CO2+O = O2+CO   | 2.10e13 |  0.00 | 2.780e4 | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| C2+C2 = C3+C    | 3.00e22 |  0.00 | 0.0     | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| O+C3  = CO+C2   | 3.00e13 |  0.00 | 0.0     | 1.0 | 0.0 | 1.0 | 0.0 | 800 |
| N+C3  = C2+CN   | 3.00e12 |  0.00 | 0.0     | 1.0 | 0.0 | 1.0 | 0.0 | 800 |

## Third-body dissociation enhancement factors

Multipliers on the dissociation rate by third-body species M.  Column order:
`Ar  N2  NO  O2  N  O  C  C2  C3  CO2  CO  CN`.

| Reaction | Ar | N2 | NO | O2 | N | O | C | C2 | C3 | CO2 | CO | CN |
|----------|----|----|----|----|---|---|---|----|----|----|----|----|
| CO2+M=CO+O+M | 0.1 | 1.0 | 1.0 | 1.0 | 2.02898550725 | 2.02898550725 | 2.02898550725 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| CO+M=C+O+M   | 0.1 | 1.0 | 1.0 | 1.0 | 1.47826086957 | 1.47826086957 | 1.47826086957 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| N2+M=N+N+M   | 1.0 | 1.0 | 1.0 | 1.0 | 4.28571428571 | 4.28571428571 | 4.28571428571 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| O2+M=O+O+M   | 1.0 | 1.0 | 1.0 | 1.0 | 5.0 | 5.0 | 5.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| NO+M=N+O+M   | 1.0 | 1.0 | 1.0 | 22.0 | 22.0 | 22.0 | 22.0 | 1.0 | 1.0 | 22.0 | 1.0 | 1.0 |
| C2+M=C+C+M   | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| CN+M=C+N+M   | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
| C3+M=C2+C+M  | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |
