#!/usr/bin/env python
"""
test_fuentes.py — Tests de las fuentes externas y de sus joins con RE/MAX.

El error que cubre es el mas caro e invisible de esta etapa: unir por
`barrio` una tabla que tiene una fila por barrio x ambientes. pandas hace el
producto, cada propiedad se copia varias veces, el dataset crece sin error ni
warning y todas las medianas quedan mal. Cada join lleva su test de "la
cantidad de filas no cambia", y un NEGATIVO que provoca la trampa a proposito
para comprobar que el test la detecta.

Tambien prueba la normalizacion de barrios: un nombre mal mapeado contamina
la mediana de otro barrio sin avisar.

No toca la red. Necesita data/processed/ y data/external/ generados.

Las rutas se resuelven desde la ubicacion de este archivo, asi que corre
igual desde cualquier directorio.

Uso:
    py src/test_fuentes.py
"""

import os
import sys

import numpy as np
import pandas as pd

import fuentes_externas as F
import supuestos as S
import temporal as T


fallos = []
corridos = 0


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


def filas_tras_join(izq: pd.DataFrame, der: pd.DataFrame, claves: list) -> int:
    return len(izq.merge(der, on=claves, how="left"))


# ==========================================================================
# 1. NORMALIZACION DE BARRIOS (sin datos)
# ==========================================================================

POSITIVOS = {
    "Núñez": "nunez",
    "Nuñez": "nunez",
    "Boca": "la boca",
    "Paternal": "la paternal",
    "Montserrat": "monserrat",
    "Villa General Mitre": "villa gral. mitre",
    "Villa Gral. Mitre": "villa gral. mitre",
    "VILLA  DEL  PARQUE": "villa del parque",
    "Constitución": "constitucion",
    "Villa Ortúzar": "villa ortuzar",
    "  Palermo ": "palermo",
}
for entrada, esperado in POSITIVOS.items():
    obtenido = F.normalizar_barrio(entrada)
    check(f"normaliza {entrada!r}", obtenido == esperado, f"esperado {esperado!r}, obtenido {obtenido!r}")

# Negativos: lo que NO es un barrio tiene que dar None, no el barrio "mas
# parecido". Un None se cuenta en el reporte; un barrio equivocado, no.
NEGATIVOS = ["Escollera Exterior", "Total", "Palermo Soho", "Parque", "Villa",
             "", "   ", None, np.nan, 14, "Capital Federal"]
for entrada in NEGATIVOS:
    obtenido = F.normalizar_barrio(entrada)
    check(f"NEG: {entrada!r} no es un barrio oficial", obtenido is None, f"obtenido {obtenido!r}")

check("hay 48 barrios oficiales, sin repetidos",
      len(F.BARRIOS_CABA) == 48 and len(set(F.BARRIOS_CABA)) == 48)
check("todo alias apunta a un barrio oficial",
      all(v in F.BARRIOS_CABA for v in F.ALIAS.values()), f"{F.ALIAS}")

# Los grupos de dormitorios tienen que caer igual de los dos lados de la
# comparacion del temporal: si no, se compara un 2 dormitorios con un mono.
vals = pd.Series([0, 1, 2, 3, 5])
lado_airbnb = pd.cut(vals, [-2, -0.5, 1, 2, 99], labels=["s/d", "0-1", "2", "3+"]).astype(str)
lado_remax = pd.cut(vals, T.CORTES_DORM, labels=T.ETIQUETAS_DORM).astype(str)
check("dormitorios: mismos grupos en Airbnb y en RE/MAX",
      list(lado_airbnb) == list(lado_remax), f"{list(lado_airbnb)} contra {list(lado_remax)}")
check("amoblamiento definido para cada grupo de dormitorios",
      set(S.AMOBLAMIENTO_USD) == set(T.ETIQUETAS_DORM))


# ==========================================================================
# 2. JOINS SOBRE LOS DATOS REALES
# ==========================================================================

# Raiz de la entrega: la carpeta que contiene src/.
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ruta(relativa: str) -> str:
    return os.path.join(RAIZ, relativa)


RUTAS = {
    "analitico": ruta("data/processed/dataset_analitico.csv"),
    "idecba": ruta("data/external/estadistica_ciudad_m2_barrio.csv"),
    "airbnb": ruta("data/external/airbnb_barrio.csv"),
    "airbnb_dorm": ruta("data/external/airbnb_barrio_dormitorios.csv"),
    "censo": ruta("data/external/censo_departamentos_comuna.csv"),
    "colegio": ruta("data/external/colegio_escribanos_mensual.csv"),
}
faltan = [p for p in RUTAS.values() if not os.path.exists(p)]
if faltan:
    print(f"Faltan archivos: {faltan}")
    print("Correr: py src/limpieza.py --tc 1500 && py src/variables.py && py src/kpis.py && py src/fuentes_externas.py")
    sys.exit(1)

D = {k: pd.read_csv(p, encoding="utf-8-sig", low_memory=False) for k, p in RUTAS.items()}
df = D["analitico"]
n = len(df)

# --- IDECBA: barrio x ambientes x estado ------------------------------------
e = D["idecba"]
ult = sorted(e["trimestre"].unique())[-1]
e_ult = e[e["trimestre"] == ult][["barrio", "ambientes", "estado", "usd_m2"]]
izq = df.assign(estado=np.where(df["es_a_estrenar"] == 1, "estrenar", "usado"))
check("IDECBA: una fila por barrio x ambientes x estado x trimestre",
      not e.duplicated(["barrio", "ambientes", "estado", "trimestre"]).any())
m = filas_tras_join(izq, e_ult, ["barrio", "ambientes", "estado"])
check("join IDECBA por barrio x ambientes x estado no cambia las filas", m == n, f"{n} -> {m}")
m = filas_tras_join(izq, e_ult, ["barrio"])
check("NEG: join IDECBA solo por barrio SI cambia las filas (la trampa se detecta)", m != n,
      f"{n} -> {m}")
m = filas_tras_join(izq, e, ["barrio", "ambientes", "estado"])
check("NEG: join IDECBA sin fijar trimestre SI cambia las filas", m != n, f"{n} -> {m}")

# --- Airbnb por barrio ------------------------------------------------------
a = D["airbnb"]
check("Airbnb: una fila por barrio", not a["barrio"].duplicated().any())
m = filas_tras_join(df, a[["barrio", "adr_mediana_usd"]], ["barrio"])
check("join Airbnb por barrio no cambia las filas", m == n, f"{n} -> {m}")

ad = D["airbnb_dorm"]
check("Airbnb por dormitorios: una fila por barrio x dormitorios",
      not ad.duplicated(["barrio", "dormitorios"]).any())
m = filas_tras_join(df, ad[["barrio", "adr_mediana_usd"]], ["barrio"])
check("NEG: join Airbnb por dormitorios solo por barrio SI cambia las filas", m != n,
      f"{n} -> {m}")

# --- Censo por comuna -------------------------------------------------------
c = D["censo"]
check("Censo: 15 comunas, una fila cada una", sorted(c["comuna"]) == list(range(1, 16)))
check("Censo: los porcentajes suman 100", abs(c["pct_departamentos_ciudad"].sum() - 100) < 0.1,
      f"{c['pct_departamentos_ciudad'].sum()}")
m = filas_tras_join(df, c[["comuna", "departamentos"]], ["comuna"])
check("join Censo por comuna no cambia las filas", m == n, f"{n} -> {m}")

# --- Comparacion temporal: la que efectivamente usa temporal.py -------------
r = T.lado_remax(RUTAS["analitico"])
check("temporal: lado RE/MAX con una fila por barrio x dormitorios",
      not r.duplicated(["barrio", "dormitorios_grupo"]).any())
ad2 = ad.rename(columns={"dormitorios": "dormitorios_grupo"})
ad2 = ad2[ad2["dormitorios_grupo"].isin(T.ETIQUETAS_DORM)]
try:
    j = r.merge(ad2, on=["barrio", "dormitorios_grupo"], how="left", validate="one_to_one")
    check("join temporal no cambia las filas del lado RE/MAX", len(j) == len(r), f"{len(r)} -> {len(j)}")
except pd.errors.MergeError as err:
    check("join temporal es uno a uno", False, str(err))


# ==========================================================================
# 3. COBERTURA Y COHERENCIA DE LAS FUENTES
# ==========================================================================

check("todos los barrios del dataset son oficiales",
      set(df["barrio"].dropna()) <= set(F.BARRIOS_CABA),
      f"{sorted(set(df['barrio'].dropna()) - set(F.BARRIOS_CABA))}")
check("IDECBA cubre los 48 barrios", set(e["barrio"]) - {"_total_ciudad"} == set(F.BARRIOS_CABA),
      f"faltan {sorted(set(F.BARRIOS_CABA) - set(e['barrio']))}")
check("Airbnb: todo barrio es oficial", set(a["barrio"]) <= set(F.BARRIOS_CABA))

serie = pd.read_csv(ruta("data/external/estadistica_ciudad_m2_serie.csv"), encoding="utf-8-sig")
check("serie IDECBA: una fila por ambientes x estado x trimestre",
      not serie.duplicated(["ambientes", "estado", "trimestre"]).any())
check("serie IDECBA: arranca en 2017 y llega al ultimo trimestre del agregado por barrio",
      serie["trimestre"].min() == F.IDECBA_SERIE_DESDE and serie["trimestre"].max() == ult,
      f"{serie['trimestre'].min()} a {serie['trimestre'].max()} (barrio: {ult})")
ult_serie = serie[serie["trimestre"] == ult].set_index(["ambientes", "estado"])["usd_m2"]
ult_barrio = e[(e["barrio"] == "_total_ciudad") & (e["trimestre"] == ult)].set_index(["ambientes", "estado"])["usd_m2"]
check("serie IDECBA: el ultimo trimestre coincide con el total del agregado por barrio",
      np.allclose(ult_serie.sort_index(), ult_barrio.sort_index()))

tp = pd.read_csv(ruta("data/external/estadistica_ciudad_tiempo_publicacion.csv"), encoding="utf-8-sig")
check("tiempo de publicacion: una fila por trimestre x categoria",
      not tp.duplicated(["trimestre", "ambientes"]).any())
check("tiempo de publicacion: trae el total y las categorias por ambientes",
      {"Total", "1 ambiente", "2 ambientes", "3 ambientes"} <= set(tp["ambientes"]),
      f"{sorted(set(tp['ambientes']))}")
check("tiempo de publicacion: llega al mismo trimestre que los precios",
      tp["trimestre"].max() == ult, f"{tp['trimestre'].max()} contra {ult}")
# Dias entre una semana y tres anios: fuera de eso es un error de lectura del
# cuadro (una columna corrida, un porcentaje leido como dias).
check("tiempo de publicacion: valores plausibles en dias", tp["dias"].between(7, 1100).all(),
      f"rango {tp['dias'].min()} a {tp['dias'].max()}")

col = D["colegio"]
check("Colegio: sin meses repetidos", not col["mes"].duplicated().any())
check("Colegio: no usa los meses de 2026 del cuadro de IDECBA (inconsistentes)",
      not ((col["mes"].str[:4].astype(int) > F.COLEGIO_ULTIMO_ANIO_CUADRO)
           & col["fuente"].str.startswith("IDECBA")).any())
check("Colegio: hipotecas <= compraventas en todo mes",
      (col["hipotecas"] <= col["compraventas"]).all())
ago = col[col["mes"] == "2026-08"]
check("Colegio: agosto 2026 = 6.055 compraventas (informe del Colegio)",
      len(ago) == 1 and int(ago["compraventas"].iloc[0]) == 6055)

# Airbnb: la ocupacion es un porcentaje y el ADR es positivo.
check("Airbnb: ocupacion entre 0 y 100", a["ocupacion_mediana_pct"].between(0, 100).all())
check("Airbnb: ADR positivo", (a["adr_mediana_usd"] > 0).all())


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
