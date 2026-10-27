#!/usr/bin/env python
"""
test_espacial.py — Tests de la fusion espacial (espacial.py).

Lo que cubre:
  1. La geometria, sin datos: el orden lon/lat del WKT, los vertices de un
     poligono, la distancia haversine contra un valor conocido, y que un aviso
     sin coordenadas quede en NaN y no en cero.
  2. Sobre los datos: que la fusion no cambie la cantidad ni el orden de las
     filas, que las distancias sean plausibles para una ciudad de 200 km2, y
     que la medida combinada sea lo que dice ser.

Cada control lleva un NEGATIVO que provoca el error a proposito para
comprobar que el test lo detecta.

No toca la red. El bloque 2 necesita data/processed/dataset_espacial.csv y
las capas de data/external/. Las rutas se resuelven desde la ubicacion de
este archivo.

Uso:
    py src/test_espacial.py
"""

import os
import sys

import numpy as np
import pandas as pd

import espacial as E


fallos = []
corridos = 0

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ruta(relativa: str) -> str:
    return os.path.join(RAIZ, relativa)


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


# Cota de plausibilidad: la diagonal de la caja que contiene a CABA (unos
# 19 km de norte a sur y 18 km de este a oeste). Ninguna distancia desde un
# aviso de la Ciudad a una red de la Ciudad puede superarla.
COTA_M = 26_000


# ==========================================================================
# 1. GEOMETRIA (sin datos)
# ==========================================================================

p = E.punto_wkt(pd.Series(["POINT (-58.3816 -34.6037)", "POINT(-58.5 -34.7)", "no es un punto"]))
check("WKT: la primera coordenada es la longitud", p.loc[0, "lon"] == -58.3816 and p.loc[0, "lat"] == -34.6037,
      f"{p.loc[0].to_dict()}")
check("WKT: acepta POINT sin espacio", p.loc[1, "lat"] == -34.7)
check("NEG: un texto que no es POINT da NaN", p.loc[2].isna().all())

poligonos = pd.DataFrame({
    "id": [1, 2, 3],
    "geometry": [
        "POLYGON ((-58.40 -34.60, -58.39 -34.60, -58.39 -34.59, -58.40 -34.60))",
        "MULTIPOLYGON (((-58.30 -34.50, -58.29 -34.50, -58.30 -34.50)), "
        "((-58.20 -34.40, -58.19 -34.40, -58.20 -34.40)))",
        None,
    ],
})
v = E.vertices_de_poligonos(poligonos)
check("vertices: 4 del POLYGON y 6 del MULTIPOLYGON", (v["id"] == 1).sum() == 4 and (v["id"] == 2).sum() == 6,
      f"{v['id'].value_counts().to_dict()}")
check("vertices: geometria nula no aporta vertices", not (v["id"] == 3).any())
check("vertices: lat y lon en su lugar", v["lat"].between(-35, -34).all() and v["lon"].between(-59, -58).all())

# 0,01 grados de latitud son 1.112 m sobre la esfera de radio 6.371 km.
ref = pd.DataFrame({"lat": [-34.60], "lon": [-58.40]})
props = pd.DataFrame({"latitud": [-34.60, -34.61, np.nan], "longitud": [-58.40, -58.40, -58.40]})
d, pos = E.distancia_al_mas_cercano(props, ref)
check("haversine: un punto contra si mismo da 0 m", abs(d[0]) < 1e-6, f"{d[0]}")
check("haversine: 0,01 grados de latitud son 1.112 m", abs(d[1] - 1111.95) < 1, f"{d[1]:.2f}")
check("sin coordenadas: la distancia queda en NaN", np.isnan(d[2]) and pos[2] == -1, f"{d[2]}, {pos[2]}")
d0, _ = E.distancia_al_mas_cercano(props.fillna(0), ref)
check("NEG: rellenar con 0 la coordenada faltante da una distancia absurda (por eso no se rellena)",
      d0[2] > COTA_M, f"{d0[2]:,.0f} m")
inv = props.rename(columns={"latitud": "longitud", "longitud": "latitud"})
d_inv, _ = E.distancia_al_mas_cercano(inv, ref)
check("NEG: latitud y longitud invertidas superan la cota de plausibilidad", d_inv[0] > COTA_M,
      f"{d_inv[0]:,.0f} m")

# Medida combinada sobre un caso armado a mano: tres avisos, uno por modo
# ganador, y uno sin coordenadas.
puntos = pd.DataFrame({
    "capa": ["subte_bocas", "tren", "metrobus", "subte_estaciones"],
    "modo": ["subte", "tren", "metrobus", "subte"],
    "nombre": ["S", "T", "M", "ESTACION DE CONTROL"],
    "lat": [-34.60, -34.62, -34.64, -34.661],
    "lon": [-58.40, -58.40, -58.40, -58.40],
})
verdes = pd.DataFrame({"id": [1], "es_parque": [0]})
vert = pd.DataFrame({"id": [1], "lat": [-34.60], "lon": [-58.40]})
df = pd.DataFrame({"latitud": [-34.601, -34.621, -34.66, np.nan],
                   "longitud": [-58.40, -58.40, -58.40, -58.40]})
out = E.agregar_columnas(df, puntos, verdes, vert)
check("combinada: no cambia las filas", len(out) == len(df))
check("combinada: el modo ganador es el del punto mas cercano",
      list(out["modo_cercano"][:3]) == ["subte", "tren", "metrobus"], f"{list(out['modo_cercano'])}")
check("combinada: es el minimo de las tres distancias",
      np.allclose(out["dist_transporte_m"][:3],
                  out[["dist_subte_m", "dist_tren_m", "dist_metrobus_m"]][:3].min(axis=1)))
check("combinada: la estacion de control no cuenta como boca de subte",
      out.loc[2, "estacion_cercana"] == "M", f"{out.loc[2, 'estacion_cercana']}")
check("combinada: aviso sin coordenadas sin modo ni estacion",
      out.loc[3, ["dist_transporte_m", "modo_cercano", "estacion_cercana"]].isna().all())
check("sin parques en la capa: dist_parque_m vacia", out["dist_parque_m"].isna().all())


# ==========================================================================
# 2. SOBRE LOS DATOS
# ==========================================================================

RUTAS = {
    "espacial": ruta("data/processed/dataset_espacial.csv"),
    "variables": ruta("data/processed/dataset_variables.csv"),
    "puntos": ruta("data/external/transporte_estaciones.csv"),
    "verdes": ruta("data/external/espacios_verdes.csv"),
    "vertices": ruta("data/external/espacios_verdes_vertices.csv"),
}
faltan = [p for p in RUTAS.values() if not os.path.exists(p)]
if faltan:
    print(f"Faltan archivos: {faltan}")
    print("Correr: py src/limpieza.py --tc 1500 && py src/variables.py && py src/espacial.py")
    sys.exit(1)

D = {k: pd.read_csv(p, encoding="utf-8-sig", low_memory=False) for k, p in RUTAS.items()}
esp, var = D["espacial"], D["variables"]

# --- la fusion no cambia las filas ------------------------------------------
n = len(var)
check("fusion: misma cantidad de filas que la entrada", len(esp) == n, f"{n} -> {len(esp)}")
check("fusion: mismo orden de avisos", list(esp["id_aviso"]) == list(var["id_aviso"]))
check("fusion: sin avisos repetidos", not esp["id_aviso"].duplicated().any())
check("fusion: agrega exactamente las columnas declaradas",
      [c for c in esp.columns if c not in var.columns] == E.COLUMNAS_NUEVAS,
      f"{[c for c in esp.columns if c not in var.columns]}")
check("fusion: no toca las columnas que ya estaban",
      esp[var.columns].equals(var), "alguna columna de entrada cambio")
# La trampa realista: asignarle a cada aviso "los espacios verdes de su
# barrio". Es un join uno a muchos y multiplica las filas sin error.
vb = D["verdes"].assign(barrio=D["verdes"]["barrio"].str.lower())[["barrio", "area_m2"]]
m = var.merge(vb, on="barrio", how="left")
check("NEG: unir los espacios verdes por barrio en vez de por coordenadas SI cambia las filas",
      len(m) != n, f"{n} -> {len(m)}")

# --- distancias con sentido -------------------------------------------------
DIST = ["dist_subte_m", "dist_tren_m", "dist_metrobus_m", "dist_transporte_m",
        "dist_plaza_m", "dist_parque_m"]
con = esp[["latitud", "longitud"]].notna().all(axis=1)
for c in DIST:
    s = esp[c]
    check(f"{c}: ninguna negativa", (s.dropna() >= 0).all(), f"min {s.min()}")
    check(f"{c}: ninguna por encima de {COTA_M:,} m", (s.dropna() <= COTA_M).all(), f"max {s.max():,.0f}")
    check(f"{c}: NaN exactamente en los avisos sin coordenadas", s.isna().equals(~con),
          f"{int(s.isna().sum())} NaN contra {int((~con).sum())} sin coordenadas")

modos = esp[["dist_subte_m", "dist_tren_m", "dist_metrobus_m"]]
check("dist_transporte_m es el minimo de las tres", np.allclose(esp["dist_transporte_m"].dropna(),
      modos[con].min(axis=1)))
gana = esp.loc[con].apply(lambda f: f[f"dist_{f['modo_cercano']}_m"], axis=1)
check("modo_cercano coincide con la distancia minima", np.allclose(gana, esp.loc[con, "dist_transporte_m"]))
check("un parque es una plaza grande: nunca mas cerca que la plaza mas cercana",
      (esp.loc[con, "dist_parque_m"] >= esp.loc[con, "dist_plaza_m"]).all())

# --- capas --------------------------------------------------------------------
pt = D["puntos"]
check("capas: las cuatro presentes", set(pt["capa"]) == {"subte_bocas", "subte_estaciones", "tren", "metrobus"},
      f"{sorted(set(pt['capa']))}")
check("capas: subte con las seis lineas A a H", set(pt.loc[pt["capa"] == "subte_bocas", "linea"])
      == {"A", "B", "C", "D", "E", "H"})
check("capas: cada fila con fecha de descarga y fuente", pt[["fecha_descarga", "fuente"]].notna().all().all())
mb = pt[pt["capa"] == "metrobus"]
check("capas: Metrobus dentro de CABA", mb["lat"].between(-34.71, -34.52).all()
      and mb["lon"].between(-58.54, -58.33).all())
bocas = pt[pt["capa"] == "subte_bocas"].reset_index(drop=True)
est = pt[pt["capa"] == "subte_estaciones"].rename(columns={"lat": "latitud", "lon": "longitud"})
d, _ = E.distancia_al_mas_cercano(est, bocas)
check(f"capas: toda estacion vigente tiene una boca a menos de {E.MAX_ESTACION_A_BOCA_M} m",
      (d <= E.MAX_ESTACION_A_BOCA_M).all(), f"max {d.max():.0f} m")
vd = D["verdes"]
check("capas: sin canteros centrales", not (vd["clasificacion"] == E.CLASIFICACION_EXCLUIDA).any())
check("capas: todo espacio verde desde 1.000 m2", (vd["area_m2"] >= E.AREA_MIN_PLAZA_M2 - 0.5).all())
check("capas: todo vertice pertenece a un espacio verde de la capa", D["vertices"]["id"].isin(vd["id"]).all())


# ==========================================================================
# RESULTADO
# ==========================================================================

print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
