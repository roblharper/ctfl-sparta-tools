"""Stagnation-line profiles (temperature, density+velocity, air/carbon species)
from the newest grid dump. Run after the SPARTA case finishes."""
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

RUN = Path(__file__).parent / "reentry_1d"
DUMP = max((RUN / "data").glob("grid.*.dat"),
           key=lambda p: int(p.stem.split(".")[1]))   # newest timestep
OUT = RUN / "plots"; OUT.mkdir(exist_ok=True)
XCROP = (-2.5, 0.15)                       # focus on shock + wall, less freestream

lines = DUMP.read_text().splitlines()
h = next(i for i, l in enumerate(lines) if l.startswith("ITEM: CELLS"))
cols = lines[h].split()[2:]
d = np.array([[float(v) for v in l.split()] for l in lines[h + 1:] if l.strip()])
C = {n: d[:, i] for i, n in enumerate(cols)}
xc = 1000.0 * 0.5 * (C["xlo"] + C["xhi"])
ax = C["ylo"] < C["ylo"].min() + 1e-9
o = np.argsort(xc[ax]); x = xc[ax][o]
def col(name): return C[name][ax][o]
nrho, u = col("f_gridprops[2]"), col("f_gridprops[3]")
Tt, Tr, Tv = col("f_Tt"), col("f_Tr"), col("f_Tv")
SP = ["N2", "O2", "NO", "N", "O", "CO", "CN", "C", "C2", "C3", "CO2"]
sp = {s: col(f"f_nrho_sp[{i+1}]") for i, s in enumerate(SP)}
keep = (nrho > 0.02 * nrho.max()) & (x >= XCROP[0]) & (x <= XCROP[1])
x, nrho, u, Tt, Tr, Tv = (v[keep] for v in (x, nrho, u, Tt, Tr, Tv))
sp = {s: v[keep] for s, v in sp.items()}

plt.rcParams.update({"font.size": 11, "axes.linewidth": 0.8, "savefig.bbox": "tight"})
def strip(a): a.spines["top"].set_visible(False); a.spines["right"].set_visible(False)
def end(a, x, y, t, c, i=None):
    i = len(x)-1 if i is None else i
    a.annotate(t, (x[i], y[i]), color=c, fontsize=10, va="center",
               xytext=(4, 0), textcoords="offset points")
XL = "distance along stagnation line  $x$ [mm]"

# ---- Temperatures ----
fig, a = plt.subplots(figsize=(6.4, 4.0))
ct, cr, cv = "#c1121f", "#e07a00", "#0a6bb5"
a.plot(x, Tt, ct, lw=1.8); a.plot(x, Tr, cr, lw=1.8); a.plot(x, Tv, cv, lw=1.8)
a.annotate(r"$T_{\rm tr}$", (x[np.argmax(Tt)], Tt.max()), color=ct, ha="center", va="bottom", xytext=(0, 3), textcoords="offset points", fontsize=10)
a.annotate(r"$T_{\rm rot}$", (x[np.argmax(Tr)], Tr.max()), color=cr, ha="right", va="bottom", xytext=(-4, 2), textcoords="offset points", fontsize=10)
a.annotate(r"$T_{\rm vib}$", (x[np.argmax(Tv)], Tv.max()), color=cv, ha="left", va="top", xytext=(3, -2), textcoords="offset points", fontsize=10)
a.axvline(0, color="0.6", lw=0.8, ls="--")
a.set_xlabel(XL); a.set_ylabel("temperature [K]"); strip(a); a.margins(x=0.06)
fig.savefig(OUT / "temperature.png", dpi=600); fig.savefig(OUT / "temperature.pdf")

# ---- Density + velocity ----
fig, a = plt.subplots(figsize=(6.4, 4.0))
cn, cu = "#2a2a2a", "#0a6bb5"
a.plot(x, nrho/1e22, cn, lw=1.8)
a.set_xlabel(XL); a.set_ylabel(r"number density $n$  [$\times10^{22}\,{\rm m^{-3}}$]"); strip(a)
a2 = a.twinx(); a2.plot(x, u, cu, lw=1.8)
a2.set_ylabel("velocity $u$  [m/s]", color=cu); a2.tick_params(axis="y", colors=cu)
a2.spines["top"].set_visible(False); a2.spines["right"].set_color(cu)
# label each curve on its flat freestream shoulder (left), well clear of each other
a.annotate(r"$n$", (x[3], nrho[3]/1e22), color=cn, fontsize=11, va="bottom",
           xytext=(0, 4), textcoords="offset points")
a2.annotate(r"$u$", (x[3], u[3]), color=cu, fontsize=11, va="top",
            xytext=(0, -4), textcoords="offset points")
a.axvline(0, color="0.6", lw=0.8, ls="--"); a.margins(x=0.06)
fig.savefig(OUT / "density_velocity.png", dpi=600); fig.savefig(OUT / "density_velocity.pdf")

def species_panel(names, colors, fname, floor):
    """Log-scale species number density; direct end-labels."""
    fig, a = plt.subplots(figsize=(6.4, 4.0))
    for s in names:
        y = sp[s]
        if y.max() < floor:
            continue
        yc = np.maximum(y, floor)
        a.semilogy(x, yc, color=colors[s], lw=1.7)
        # label at the wall side (rightmost real value), nudged to avoid overlap
        a.annotate(s, (x[-1], yc[-1]), color=colors[s], fontsize=10, va="center",
                   xytext=(5, 0), textcoords="offset points")
    a.axvline(0, color="0.6", lw=0.8, ls="--")
    a.set_xlabel(XL); a.set_ylabel(r"number density  [m$^{-3}$]")
    a.set_ylim(bottom=floor)
    strip(a); a.margins(x=0.10)
    fig.savefig(OUT / f"{fname}.png", dpi=600); fig.savefig(OUT / f"{fname}.pdf")

# ---- Air species (log) ----
species_panel(["N2", "O2", "NO", "N", "O"],
              {"N2": "#1f4e79", "O2": "#c1121f", "NO": "#e07a00", "N": "#2a9d8f", "O": "#8a5a44"},
              "species_air", floor=1e20)
# ---- Carbon ablation species (log) ----
species_panel(["CO", "CN", "CO2", "C"],
              {"CO": "#7b2cbf", "CN": "#e07a00", "CO2": "#2a9d8f", "C": "#c1121f"},
              "species_carbon", floor=1e17)

print("wrote:", *[p.name for p in sorted(OUT.glob("*.png"))])
print(f"crop x={XCROP}, {keep.sum()} points; CO peak={sp['CO'].max():.2e}")
