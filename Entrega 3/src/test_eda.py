#!/usr/bin/env python
"""
test_eda.py — Tests de las funciones de estadistica de eda.py. Sin red, sin datos.

El caso central reproduce la trampa que motiva comparar dentro de estratos:
un atributo que no mueve la renta dentro de ningun barrio, pero que esta
concentrado en el barrio que menos rinde. La comparacion ingenua le atribuye
un efecto negativo; la estratificada tiene que dar cero.

Uso:
    py src/test_eda.py
"""

import sys

import numpy as np
import pandas as pd

import eda


fallos = []
corridos = 0


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


# --- Confusion por barrio ---------------------------------------------------
# Barrio caro: renta 5%, 80% con amenities. Barrio barato: renta 9%, 20% con
# amenities. Dentro de cada barrio los amenities no cambian nada.
rng = np.random.default_rng(0)
filas = []
for barrio, renta, p_amen in [("caro", 5.0, 0.8), ("barato", 9.0, 0.2)]:
    for _ in range(200):
        filas.append({"barrio": barrio, "tramo": "36-55",
                      "amenities": int(rng.random() < p_amen),
                      "renta": renta + rng.normal(0, 0.01)})
sint = pd.DataFrame(filas)

ingenua = (sint.loc[sint.amenities == 1, "renta"].median()
           - sint.loc[sint.amenities == 0, "renta"].median())
t = eda.efecto_estratificado(sint, "amenities", "renta", ["barrio", "tramo"], minimo=5)
r = eda.resumir_efecto(t, len(sint))
check("NEG: la comparacion ingenua SI muestra un efecto espurio", ingenua < -3,
      f"diferencia ingenua {ingenua:.2f}")
check("dentro del estrato el efecto espurio desaparece", abs(r["mediana_ponderada"]) < 0.05,
      f"efecto estratificado {r['mediana_ponderada']:.3f}")
check("usa las dos celdas", r["celdas"] == 2, f"{r['celdas']}")
check("cubre todas las filas", abs(r["pct_filas_cubiertas"] - 100) < 1e-9)

# Efecto real: dentro de cada barrio los amenities suman 1 punto.
sint2 = sint.assign(renta=sint.renta + sint.amenities * 1.0)
r2 = eda.resumir_efecto(eda.efecto_estratificado(sint2, "amenities", "renta", ["barrio"], 5), len(sint2))
check("un efecto real dentro del estrato se recupera", abs(r2["mediana_ponderada"] - 1.0) < 0.05,
      f"{r2['mediana_ponderada']:.3f}")

# Celdas chicas: un grupo por debajo del minimo deja la celda afuera.
chica = sint[(sint.barrio == "caro")].copy()
chica = pd.concat([chica[chica.amenities == 1], chica[chica.amenities == 0].head(3)])
t3 = eda.efecto_estratificado(chica, "amenities", "renta", ["barrio"], minimo=5)
check("NEG: una celda con 3 casos en un grupo no entra", t3.empty)
check("resumen de una tabla vacia no revienta y cubre 0%",
      eda.resumir_efecto(t3, len(chica))["pct_filas_cubiertas"] == 0.0)

# --- Mediana ponderada ------------------------------------------------------
check("mediana ponderada con pesos iguales = mediana", eda.mediana_ponderada([1, 2, 3], [1, 1, 1]) == 2)
check("el peso desplaza la mediana", eda.mediana_ponderada([1, 2, 3], [1, 1, 10]) == 3)
check("NEG: sin pesos validos devuelve NaN", np.isnan(eda.mediana_ponderada([1, 2], [0, 0])))

# --- Cobertura --------------------------------------------------------------
c = eda.cobertura_estratos(sint, ["barrio", "tramo"], minimo=10)
check("cobertura: dos celdas validas, 100%", c["celdas_validas"] == 2 and c["pct_cubierto"] == 100)
c = eda.cobertura_estratos(sint, ["barrio", "tramo"], minimo=10_000)
check("NEG: con un minimo inalcanzable no cubre nada", c["celdas_validas"] == 0 and c["pct_cubierto"] == 0)

# --- Funciones de resumen con texto (pandas 3) ------------------------------
txt = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 1.0, 4.0, 3.0], "b": list("abcd")})
m = eda.matriz_correlacion(txt, ["x", "y", "b"])
check("matriz_correlacion descarta el texto en vez de reventar", list(m.columns) == ["x", "y"])
check("resumen_robusto descarta el texto", list(eda.resumen_robusto(txt, ["x", "b"]).index) == ["x"])
check("NEG: leer_asimetria(NaN) no afirma una forma", eda.leer_asimetria(np.nan).startswith("sin dato"))
check("leer_asimetria fuerte positiva", "fuerte hacia la derecha" in eda.leer_asimetria(2.0))
check("leer_asimetria simetrica", eda.leer_asimetria(0.1).startswith("practicamente"))


print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
