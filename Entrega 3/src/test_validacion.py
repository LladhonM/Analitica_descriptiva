#!/usr/bin/env python
"""
test_validacion.py — Tests de las piezas estadisticas de validacion.py, sin datos.

Cada una se compara contra un oraculo independiente:
  - el Spearman, contra scipy
  - Van Elteren con un solo estrato, contra el Mann-Whitney de scipy
  - los errores agrupados con un aviso por grupo, contra HC1 calculado aparte
  - la pendiente intra, contra la regresion con una dummy por celda
y lleva un NEGATIVO donde el metodo ingenuo se equivoca y el correcto no.

Uso:
    py src/test_validacion.py
"""

import sys

import numpy as np
import pandas as pd
from scipy import stats

import validacion as V


fallos = []
corridos = 0


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


rng = np.random.default_rng(11)

# --- Spearman por permutacion ---------------------------------------------------
x = rng.normal(size=30)
y1 = -x + rng.normal(0, 0.1, 30)
rho, p = V.permutacion_spearman(x, y1, n_perm=2_000)
check("Spearman: coincide con scipy", abs(rho - stats.spearmanr(x, y1)[0]) < 1e-12)
check("Spearman: relacion decreciente fuerte da p minimo", p <= 2 / 2_001, f"{p}")
y = rng.normal(size=30)
r0, p0 = V.permutacion_spearman(x, y, n_perm=2_000)
check("Spearman: el rho es el de scipy", abs(r0 - stats.spearmanr(x, y)[0]) < 1e-12)
check("NEG: sin relacion, el p-valor no es significativo", p0 > 0.05, f"{p0}")

# --- Holm ---------------------------------------------------------------------
h = V.holm(pd.Series([0.01, 0.04, 0.03], index=["a", "b", "c"]))
check("Holm: ejemplo de libro", np.allclose(h.values, [0.03, 0.06, 0.06]), f"{h.to_dict()}")
check("Holm: nunca supera 1", V.holm(pd.Series([0.6, 0.7])).max() <= 1)

# --- Errores agrupados ----------------------------------------------------------
n = 200
X = np.column_stack([np.ones(n), rng.normal(size=n)])
yy = X @ [1.0, 0.5] + rng.normal(size=n) * (1 + np.abs(X[:, 1]))
b, se = V.ols_agrupado(X, yy, np.arange(n))
u = yy - X @ b
xtx = np.linalg.inv(X.T @ X)
hc1 = np.sqrt(np.diag(xtx @ (X.T * u ** 2) @ X @ xtx) * n / (n - 2))
check("agrupado: coeficientes de minimos cuadrados", np.allclose(b, np.linalg.lstsq(X, yy, rcond=None)[0]))
check("agrupado: con un aviso por grupo es HC1", np.allclose(se, hc1), f"{se} contra {hc1}")
# 40 grupos que comparten un shock y un regresor de grupo: el error comun
# subestima la incertidumbre; el agrupado no.
G, m = 40, 25
g = np.repeat(np.arange(G), m)
xg = np.repeat(rng.normal(size=G), m)
yg = 0.0 * xg + np.repeat(rng.normal(size=G), m) + rng.normal(0, 0.3, G * m)
Xg = np.column_stack([np.ones(G * m), xg])
bg, seg = V.ols_agrupado(Xg, yg, g)
ug = yg - Xg @ bg
se_ingenuo = np.sqrt(np.diag(np.linalg.inv(Xg.T @ Xg)) * (ug ** 2).sum() / (G * m - 2))
check("NEG: con errores correlacionados en el grupo, el error comun es varias veces menor",
      seg[1] > 3 * se_ingenuo[1], f"agrupado {seg[1]:.4f}, ingenuo {se_ingenuo[1]:.4f}")

# --- Van Elteren ------------------------------------------------------------------
a = pd.Series(np.r_[rng.normal(0, 1, 40), rng.normal(0.6, 1, 50)].round(1))
grp = pd.Series(np.r_[np.ones(40), np.zeros(50)])
ve = V.van_elteren(a, grp, pd.Series("unico", index=a.index))
mw = stats.mannwhitneyu(a[grp == 1], a[grp == 0], alternative="less", method="asymptotic", use_continuity=False)
check("Van Elteren con un estrato = Mann-Whitney de scipy (con empates)", abs(ve["p_menor"] - mw.pvalue) < 1e-10,
      f"{ve['p_menor']} contra {mw.pvalue}")
# Simpson: el grupo 1 esta concentrado en el estrato barato, pero dentro de
# cada estrato no hay diferencia. El test sin estratos la encuentra; el
# estratificado, no.
partes = []
for nivel, n1, n0 in [(0.0, 80, 20), (5.0, 20, 80)]:
    partes.append(pd.DataFrame({"y": rng.normal(nivel, 1, n1 + n0), "g": np.r_[np.ones(n1), np.zeros(n0)],
                                "e": f"estrato {nivel}"}))
d = pd.concat(partes, ignore_index=True)
ingenuo = stats.mannwhitneyu(d.y[d.g == 1], d.y[d.g == 0], alternative="less").pvalue
estrat = V.van_elteren(d["y"], d["g"], d["e"])
check("NEG: sin estratos aparece una diferencia que no existe", ingenuo < 0.001, f"{ingenuo}")
check("Van Elteren: dentro de los estratos no la encuentra", estrat["p_bilateral"] > 0.05, f"{estrat}")
# Cada estrato tiene un grupo de 20: con minimo 20 entran los dos; con 21,
# ninguno, y el resultado es NaN en lugar de una division por cero.
check("Van Elteren: con el minimo justo entran los dos estratos",
      V.van_elteren(d["y"], d["g"], d["e"], minimo=20)["celdas"] == 2)
sin_estratos = V.van_elteren(d["y"], d["g"], d["e"], minimo=21)
check("Van Elteren: sin estratos que cumplan el minimo devuelve NaN, no un error",
      sin_estratos["celdas"] == 0 and np.isnan(sin_estratos["z"]), f"{sin_estratos}")

# --- Pendiente intra ----------------------------------------------------------------
celdas = np.repeat(np.arange(30), 20)
xc = rng.normal(size=600) + np.repeat(rng.normal(0, 3, 30), 20)
yc = -0.3 * xc + np.repeat(rng.normal(0, 5, 30), 20) + rng.normal(0, 1, 600)
beta, boot, nc = V.pendiente_intra(pd.Series(xc), pd.Series(yc), pd.Series(celdas), n_boot=500)
D = pd.get_dummies(pd.Series(celdas), dtype=float).values
b_dum = np.linalg.lstsq(np.column_stack([D, xc]), yc, rcond=None)[0][-1]
check("pendiente intra = regresion con una dummy por celda", abs(beta - b_dum) < 1e-10, f"{beta} contra {b_dum}")
check("pendiente intra: el bootstrap se centra en la estimacion", abs(np.median(boot) - beta) < 0.02)
check("pendiente intra: cuenta las celdas", nc == 30)
# Relacion solo ENTRE celdas: las celdas con x alto tienen y alto, pero dentro
# de cada celda x e y son independientes. Sin efectos fijos aparece una
# pendiente fuerte; la intra tiene que dar ~0.
media_celda = np.repeat(rng.normal(0, 3, 30), 20)
x_ent = media_celda + rng.normal(0, 1, 600)
y_ent = 2.0 * media_celda + rng.normal(0, 1, 600)
b_ent, _, _ = V.pendiente_intra(pd.Series(x_ent), pd.Series(y_ent), pd.Series(celdas), n_boot=100)
b_pool = np.polyfit(x_ent, y_ent, 1)[0]
check("NEG: sin efectos fijos aparece una pendiente que dentro de la celda no existe", b_pool > 1.5,
      f"{b_pool:.3f}")
check("pendiente intra: no la hereda", abs(b_ent) < 0.15, f"intra {b_ent:.3f}")


print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
