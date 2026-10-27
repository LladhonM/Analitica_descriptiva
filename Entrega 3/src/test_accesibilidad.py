#!/usr/bin/env python
"""
test_accesibilidad.py — Tests del metodo de H2 (accesibilidad.py).

El metodo tiene que hacer dos cosas, y se prueban sobre datos sinteticos
donde la respuesta correcta se conoce:
  1. Separar centralidad de accesibilidad: si el precio depende solo del
     barrio y los barrios caros estan cerca de la red, la pendiente con
     barrio fijo tiene que dar cero. Sin barrio fijo, da negativa: es el
     NEGATIVO que muestra por que el control es el punto.
  2. Encontrar un efecto que existe: con una penalidad plantada mas alla de
     1 km, el perfil por tramos tiene que recuperarla.

Despues, sobre los datos, que la salida tenga la forma esperada.

Uso:
    py src/test_accesibilidad.py
"""

import os
import sys

import numpy as np
import pandas as pd

import accesibilidad as A


fallos = []
corridos = 0

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


rng = np.random.default_rng(7)


def sintetico(penalidad_lejos: float) -> pd.DataFrame:
    """
    20 barrios. Los caros estan cerca de la red (centralidad). Dentro de cada
    barrio la distancia varia, y el precio solo cae si se pide una penalidad
    para los avisos a mas de 1 km.
    """
    filas = []
    for b in range(20):
        nivel = 8.0 - 0.03 * b             # barrio 0 el mas caro
        centro = 200 + 60 * b               # y el mas cerca de la red
        dist = np.clip(rng.normal(centro, 400, 300), 10, None)
        y = nivel + rng.normal(0, 0.05, 300) + np.where(dist > 1000, np.log1p(penalidad_lejos), 0)
        filas.append(pd.DataFrame({"barrio": f"b{b:02d}", "dist_transporte_m": dist, "y": y}))
    return pd.concat(filas, ignore_index=True)


# --- 1. Centralidad pura: con barrio fijo, cero ------------------------------
v = sintetico(0.0)
uno = np.ones((len(v), 1))
km = v[["dist_transporte_m"]].values / 1000
b_sin, _ = A.ols(np.hstack([uno, km]), v["y"].values)
b_con, _ = A.ols(np.hstack([A.matriz_base(v, controles=False), km]), v["y"].values)
check("centralidad pura: con barrio fijo la pendiente es ~0", abs(A.efecto_pct(b_con[-1])) < 0.5,
      f"{A.efecto_pct(b_con[-1]):+.2f}%/km")
check("NEG: sin barrio fijo aparece un efecto que no existe", A.efecto_pct(b_sin[-1]) < -5,
      f"{A.efecto_pct(b_sin[-1]):+.2f}%/km")

# --- 2. Penalidad plantada de -8% mas alla de 1 km ---------------------------
v = sintetico(-0.08)
t = A.tramos(v["dist_transporte_m"])
D = pd.get_dummies(t, dtype=float)
b, _ = A.ols(np.hstack([A.matriz_base(v, controles=False), D.drop(columns=D.columns[0]).values]),
             v["y"].values)
efectos = dict(zip(D.columns[1:], [A.efecto_pct(x) for x in b[-(D.shape[1] - 1):]]))
lejos = [k for k in efectos if k.startswith(("1,000", "1,500"))]
cerca = [k for k in efectos if k not in lejos]
check("perfil: recupera la penalidad de -8% en los tramos de mas de 1 km",
      all(abs(efectos[k] + 8) < 1.5 for k in lejos), f"{efectos}")
check("perfil: sin efecto en los tramos de hasta 1 km", all(abs(efectos[k]) < 1.5 for k in cerca),
      f"{efectos}")
check("tramos: el primero arranca en 0 y el ultimo es abierto",
      str(t.cat.categories[0]).startswith("0-") and str(t.cat.categories[-1]).endswith("+"))


# --- 3. Sobre los datos ------------------------------------------------------
p = os.path.join(RAIZ, "data/processed/h2_perfil_distancia.csv")
if not os.path.exists(p):
    print(f"Falta {p}. Correr: py src/accesibilidad.py")
    sys.exit(1)
h = pd.read_csv(p, encoding="utf-8-sig")
check("salida: 4 medidas x 3 especificaciones x 5 tramos", len(h) == 60, f"{len(h)} filas")
check("salida: el tramo de referencia vale 0 en todas",
      (h.loc[h["tramo_m"].str.startswith("0-"), "efecto_pct"] == 0).all())
n = h[h["especificacion"] == "barrio"].groupby("medida")["n"].sum()
check("salida: cada medida cubre la misma base de avisos", n.nunique() == 1, f"{n.to_dict()}")


print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
