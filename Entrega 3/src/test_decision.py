#!/usr/bin/env python
"""
test_decision.py — Tests de la funcion de decision (decision.py).

Oraculos independientes:
  - la frontera y los pares distinguibles de P2, contra la comparacion de
    todos los pares uno por uno (fuerza bruta)
  - la neta central, contra rent_neta_pct del dataset (la calcula kpis.py)
  - la ocupacion de equilibrio, contra la columna de temporal.py, y la
    identidad que la define: con esa ocupacion el temporal empata
  - la TIR sin costos de entrada, contra la neta (sin costo inicial y
    revendiendo al mismo precio, la TIR es la renta anual)
con NEGATIVOS donde ordenar por la neta central se equivoca y la dominancia
de bandas no.

Uso:
    py src/test_decision.py      # los tests con datos necesitan el pipeline corrido
"""

import os
import sys

import numpy as np
import pandas as pd

import costos as C
import decision as D
import supuestos as S


fallos = []
corridos = 0


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


rng = np.random.default_rng(3)

# --- P2 contra fuerza bruta -------------------------------------------------------
for n in (2, 7, 60):
    centro = rng.normal(6, 1.5, n)
    ancho = rng.uniform(0.5, 4, n)
    lo, hi = centro - ancho / 2, centro + ancho / 2
    domina = lo[:, None] > hi[None, :]           # domina[a, b]: a supera a b con claridad
    front_bf = ~domina.any(axis=0)
    check(f"frontera = las que nadie domina, fuerza bruta (n={n})",
          np.array_equal(D.no_dominadas(lo, hi), front_bf))
    pares_bf = domina.sum() / (n * (n - 1) / 2)
    check(f"pares distinguibles, fuerza bruta (n={n})", abs(D.pares_distinguibles(lo, hi) - pares_bf) < 1e-12,
          f"{D.pares_distinguibles(lo, hi)} contra {pares_bf}")

# Dentro de la frontera ninguna domina a otra.
lo, hi = rng.normal(6, 1, 200) - 1, rng.normal(6, 1, 200) + 1
f = D.no_dominadas(lo, hi)
check("dentro de la frontera ninguna domina a otra", not (lo[f][:, None] > hi[f][None, :]).any())

# Por grupo: solo cuenta pares dentro del grupo.
lo_s, hi_s = pd.Series([1.0, 5.0, 1.0, 5.0]), pd.Series([2.0, 6.0, 2.0, 6.0])
g = pd.Series(["a", "a", "b", "b"])
check("pares por grupo: cuenta los dos pares internos", D.pares_distinguibles_por_grupo(lo_s, hi_s, g) == 1.0)
check("pares por grupo: si cada grupo junta bandas iguales, no hay pares distinguibles",
      D.pares_distinguibles_por_grupo(lo_s, hi_s, pd.Series(["a", "b", "a", "b"])) == 0.0)

# NEG: la de mayor neta central no domina si su banda es ancha. Ordenar por la
# central la pondria primera; la dominancia dice que no se distingue.
lo = np.array([3.0, 6.0, 6.5])
hi = np.array([14.0, 7.0, 7.4])   # centros 8,5 / 6,5 / 6,95
check("NEG: la de mayor neta central no domina con banda ancha", D.no_dominadas(lo, hi).all())
check("NEG: ningun par se distingue", D.pares_distinguibles(lo, hi) == 0.0)

# --- Neta -------------------------------------------------------------------------
alq, venta = pd.Series([500.0]), pd.Series([100_000.0])
check("neta plana = bruta x (1 - vacancia) x (1 - gastos)",
      abs(D.neta(alq, venta, None, 5.0, 10.0).iloc[0]
          - 6.0 * 0.95 * (1 - (10.0 + S.ABL_PCT) / 100)) < 1e-12)
abl_ars = pd.Series([0.05 * 500 * S.TC_ARS_USD])   # un ABL de 5% del alquiler, en pesos
check("neta segmentada: el ABL en pesos entra como % del alquiler",
      abs(D.neta(alq, venta, abl_ars, 5.0, 10.0).iloc[0] - 6.0 * 0.95 * 0.85) < 1e-12)
check("neta: con el mismo ABL en pesos, un alquiler mas bajo paga mas % de ABL",
      D.neta(alq * 0.8, venta, abl_ars, 5.0, 10.0).iloc[0] < 0.8 * D.neta(alq, venta, abl_ars, 5.0, 10.0).iloc[0])

# --- TIR ------------------------------------------------------------------------------
tir0 = C.tir(np.array([5.0, 7.5]), np.array([0.0, 0.0]))
check("TIR sin costos de entrada = neta", np.allclose(tir0, [5.0, 7.5], atol=1e-6), f"{tir0}")

# --- P3 -------------------------------------------------------------------------------
t = pd.DataFrame({"alquiler_est_mediano_usd": [600.0], "gastos_mediana_pct": [14.0],
                  "fijos_usd": [3000.0], "adr_mediana_usd": [60.0]})
o = D.ocupacion_equilibrio(t, 6.0).iloc[0]
trad = 600 * 12 * 0.94 * 0.86
temp = 60 * 365 * o / 100 * D.margen_temporal(False) - 3000
check("P3: con la ocupacion de equilibrio, el temporal empata al tradicional", abs(temp - trad) < 1e-6,
      f"{temp} contra {trad}")
check("P3: autogestionado necesita menos ocupacion", D.ocupacion_equilibrio(t, 6.0, True).iloc[0] < o)

# --- Con los datos del pipeline -----------------------------------------------------------
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if os.path.exists(D.ANALITICO) and os.path.exists(D.TEMPORAL):
    df = pd.read_csv(D.ANALITICO, encoding="utf-8-sig", low_memory=False)
    v = D.universo(df)
    b = D.bandas(v, S.VACANCIA_PCT, S.GASTOS_SIN_ABL_PCT, v["abl_ars_mes"])
    dif = (b["neta"] - v["rent_neta_pct"]).abs().max()
    check("datos: la neta central reproduce rent_neta_pct de kpis.py", dif < 0.011, f"diferencia maxima {dif:.4f}")
    # La banda sale de una regresion cuantilica aparte del Ridge, asi que en
    # algun caso aislado la central puede quedar afuera (hoy, 1 PH de menos de
    # 35 m2, fuera del soporte). Dentro del universo de la decision, nunca.
    adentro = (b["neta_min"] <= b["neta"] + 1e-9) & (b["neta"] <= b["neta_max"] + 1e-9)
    check("datos: en el universo de la decision, la banda contiene a la central",
          adentro[v["universo_decision"]].all(), f"{int((~adentro[v['universo_decision']]).sum())} afuera")
    check("datos: fuera del universo, la central queda afuera de la banda en casos aislados",
          (~adentro).mean() < 0.001, f"{int((~adentro).sum())} de {len(v)}")
    tir_sin = D.tir_pesimista(v, S.VACANCIA_PCT, S.GASTOS_SIN_ABL_PCT, v["abl_ars_mes"], "sin")
    nr = ~(v["a_reciclar"] == 1)
    check("datos: sin costos de entrada, la TIR pesimista es la neta pesimista (no reciclar)",
          np.allclose(tir_sin[nr], b.loc[nr, "neta_min"], atol=1e-4))
    tt = pd.read_csv(D.TEMPORAL, encoding="utf-8-sig")
    check("datos: la ocupacion de equilibrio reproduce temporal.py",
          np.allclose(D.ocupacion_equilibrio(tt, S.VACANCIA_PCT), tt["ocupacion_equilibrio_pct"], atol=1e-6))
    check("datos: el universo cumple presupuesto y soporte",
          v.loc[v["universo_decision"], "venta_usd"].between(*S.PRESUPUESTO_USD).all()
          and (v.loc[v["universo_decision"], "n_alq_celda_tipo"] >= S.MIN_ALQ_SOPORTE).all())
    if "p1_comprar" in df.columns:
        check("datos: P1 solo recomienda dentro del universo",
              not (df["p1_comprar"].fillna(False).astype(bool) & ~df["universo_decision"].fillna(False).astype(bool)).any())
        f = df[df["p2_no_dominada"].fillna(False).astype(bool)]
        u = df[df["universo_decision"].fillna(False).astype(bool)]
        check("datos: la frontera guardada es la que nadie domina",
              (f["neta_max_pct"] >= u["neta_min_pct"].max()).all() and len(f) > 0)
else:
    print("(sin datos del pipeline: se saltean los tests con datos)")


print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
