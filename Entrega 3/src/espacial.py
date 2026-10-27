#!/usr/bin/env python
"""
espacial.py — Fusion espacial: distancia de cada aviso al transporte masivo
(subte, tren y Metrobus) y a plazas y parques, y una medida de accesibilidad
que combina los tres modos.

DE DONDE VIENE
--------------
El calculo de distancias (BallTree con metrica haversine, y la distancia a un
espacio verde medida contra los vertices de su poligono) se adapta de
enriquecimiento.py, del repositorio de trabajo del grupo
(LladhonM/Analitica-Descriptiva, commit 2f407b2). Sobre eso se agregan el
Metrobus, la medida combinada, las capas versionadas y los controles.

LA MEDIDA: METROS HASTA LA RED MASIVA MAS CERCANA
-------------------------------------------------
dist_transporte_m = distancia a la estacion mas cercana de CUALQUIERA de las
tres redes masivas de la Ciudad: subte, tren o Metrobus.

Es el minimo de las tres distancias, sin pesos. Lo que un inquilino paga
todos los dias es la caminata hasta la red: una vez adentro, cualquiera de
las tres lo conecta con el resto de la Ciudad. Un indice ponderado exigiria
pesar cada modo por su frecuencia, y no hay un dato de frecuencia por
estacion que se pueda unir: los pesos serian inventados. Contar cuantos
modos hay cerca tampoco sirve: un conteo no es una tasa, y tener tres redes
a 300 m no da el triple de acceso que tener una.

Las tres distancias por modo quedan como columnas, para medir que agrega la
combinacion frente a cada una por separado.

QUE NO MIDE
-----------
Es distancia en linea recta sobre la esfera, no accesibilidad real. No ve
barreras (vias, autopistas, el Riachuelo), no ve la frecuencia (una estacion
con un tren por hora no equivale a un subte cada cuatro minutos) ni hacia
donde lleva cada linea. Es una cota inferior del esfuerzo de llegar a la red,
no una medida de cuan bien conectado esta el inmueble.

NIVEL TERRITORIAL
-----------------
La medida es por aviso, no por barrio. El reporte muestra cuanto varia dentro
de cada barrio: un promedio barrial esconde avisos a 200 m y a 1.500 m de la
red en el mismo barrio.

Uso:
    py src/espacial.py              # usa las capas versionadas de data/external/
    py src/espacial.py --descargar  # vuelve a bajar los crudos y rehace las capas

Salidas:
    data/external/transporte_estaciones.csv     bocas de subte, estaciones de tren
                                                y paradas de Metrobus
    data/external/espacios_verdes.csv           plazas y parques, uno por fila
    data/external/espacios_verdes_vertices.csv  vertices de esos poligonos
    data/processed/dataset_espacial.csv         dataset_variables + columnas espaciales
    data/processed/reporte_espacial.txt         log
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

import fuentes_externas as F
import supuestos as S


ENTRADA = "data/processed/dataset_variables.csv"
SALIDA = "data/processed/dataset_espacial.csv"
REPORTE = "data/processed/reporte_espacial.txt"
OUT = F.OUT

CAPA_PUNTOS = os.path.join(OUT, "transporte_estaciones.csv")
CAPA_VERDES = os.path.join(OUT, "espacios_verdes.csv")
CAPA_VERTICES = os.path.join(OUT, "espacios_verdes_vertices.csv")

RADIO_TIERRA_M = 6_371_000

# --------------------------------------------------------------------------
# Fuentes: Buenos Aires Data (GCBA), licencia CC-BY-2.5-AR
# --------------------------------------------------------------------------
_BASE = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets"
URL_SUBTE_BOCAS = f"{_BASE}/sbase/bocas-de-subte/bocas-de-subte.csv"
# Solo se usa como control: que cada estacion vigente tenga una boca cerca.
# La capa de bocas es de 2019 y esta, de 2024.
URL_SUBTE_ESTACIONES = f"{_BASE}/sbase/subte-estaciones/estaciones-de-subte.csv"
URL_TREN = f"{_BASE}/transporte-y-obras-publicas/estaciones-ferrocarril/estaciones_ferroviarias.csv"
# Hay versiones viejas del mismo archivo en otras rutas del portal (2019 y
# 2020, con menos paradas): esta es la vigente.
URL_METROBUS = f"{_BASE}/transporte-y-obras-publicas/metrobus/estaciones-de-metrobus.csv"
URL_VERDES = f"{_BASE}/secretaria-de-desarrollo-urbano/espacios-verdes/espacio_verde_publico.csv"

MODOS = ["subte", "tren", "metrobus"]

# Que cuenta como espacio verde. Los canteros centrales (el pasto del medio
# de una avenida) se excluyen siempre: con ellos casi todo aviso queda a
# menos de 300 m de un "espacio verde" y la variable no discrimina. Una plaza
# es usable desde 1.000 m2; un parque, desde una hectarea.
CLASIFICACION_EXCLUIDA = "CANTERO CENTRAL"
AREA_MIN_PLAZA_M2 = 1_000
AREA_MIN_PARQUE_M2 = 10_000

# Los vertices se guardan en una grilla de 4 decimales (unos 11 x 9 m): el
# error sobre la distancia a una plaza queda por debajo de 7 m, y la capa
# versionada pasa de 7 MB a 1,6 MB.
DECIMALES_VERTICES = 4

# Control de la capa de bocas: una estacion vigente sin boca a menos de esta
# distancia indicaria que la capa de 2019 no cubre la red actual.
MAX_ESTACION_A_BOCA_M = 200

COLUMNAS_NUEVAS = [
    "dist_subte_m", "dist_tren_m", "dist_metrobus_m",
    "dist_transporte_m", "modo_cercano", "estacion_cercana",
    "dist_plaza_m", "dist_parque_m",
]


# ==========================================================================
# LECTURA DE LOS CRUDOS
# ==========================================================================

def punto_wkt(serie: pd.Series) -> pd.DataFrame:
    """
    Extrae lat y lon de un WKT "POINT (lon lat)".

    Ojo con el orden: WKT escribe primero la longitud y despues la latitud,
    al reves de como se suele nombrar el par "lat/long".
    """
    return serie.str.extract(
        r"POINT\s*\(\s*(?P<lon>-?\d+\.?\d*)\s+(?P<lat>-?\d+\.?\d*)\s*\)").astype(float)


def vertices_de_poligonos(df: pd.DataFrame, col: str = "geometry",
                          id_col: str = "id") -> pd.DataFrame:
    """
    Extrae los vertices de geometrias POLYGON / MULTIPOLYGON en WKT.

    Un espacio verde es un area, no un punto. Medir contra el centroide haria
    que un inmueble pegado al borde de un parque grande quede a cientos de
    metros. La distancia al vertice mas cercano aproxima la distancia al borde.
    """
    patron = re.compile(r"(-?\d+\.\d+)\s+(-?\d+\.\d+)")
    filas = [(i, float(lat), float(lon))
             for i, geom in zip(df[id_col], df[col]) if isinstance(geom, str)
             for lon, lat in patron.findall(geom)]
    return pd.DataFrame(filas, columns=[id_col, "lat", "lon"])


def leer_subte_bocas(path: str) -> pd.DataFrame:
    d = pd.read_csv(path, encoding="utf-8-sig").dropna(subset=["lat", "long"])
    return pd.DataFrame({"capa": "subte_bocas", "modo": "subte", "linea": d["linea"],
                         "nombre": d["estacion"], "lat": d["lat"], "lon": d["long"]})


def leer_subte_estaciones(path: str) -> pd.DataFrame:
    # Separador ";" y coma decimal, a diferencia de las otras capas.
    d = pd.read_csv(path, sep=";", decimal=",", encoding="utf-8-sig").dropna(subset=["lat", "long"])
    return pd.DataFrame({"capa": "subte_estaciones", "modo": "subte", "linea": d["linea"],
                         "nombre": d["estacion"], "lat": d["lat"], "lon": d["long"]})


def leer_tren(path: str) -> pd.DataFrame:
    # Incluye estaciones del conurbano: es correcto, un aviso sobre la General
    # Paz puede tener la estacion mas cercana del otro lado.
    d = pd.read_csv(path, encoding="utf-8-sig")
    d = pd.concat([d, punto_wkt(d["geometry"])], axis=1).dropna(subset=["lat", "lon"])
    linea = d["linea"].str.split(",").str[0].str.strip()
    return pd.DataFrame({"capa": "tren", "modo": "tren", "linea": linea,
                         "nombre": d["nombre"], "lat": d["lat"], "lon": d["lon"]})


def leer_metrobus(path: str) -> pd.DataFrame:
    # Una fila por parada y sentido. No trae el nombre del corredor: la avenida
    # (CALLE) lo identifica.
    d = pd.read_csv(path, encoding="utf-8-sig").dropna(subset=["X", "Y"])
    return pd.DataFrame({"capa": "metrobus", "modo": "metrobus", "linea": d["CALLE"],
                         "nombre": d["NOMBRE PAR"], "lat": d["Y"], "lon": d["X"]})


def leer_verdes(path: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Plazas y parques (sin canteros, desde 1.000 m2) y sus vertices."""
    d = pd.read_csv(path, encoding="utf-8-sig")
    d = d[(d["clasificac"] != CLASIFICACION_EXCLUIDA) & (d["area"] >= AREA_MIN_PLAZA_M2)
          & d["geometry"].notna()]
    verdes = pd.DataFrame({
        "id": d["id"], "nombre": d["nombre"], "clasificacion": d["clasificac"],
        "area_m2": d["area"].round(0), "barrio": d["barrio"], "comuna": d["comuna"],
        "es_parque": (d["area"] >= AREA_MIN_PARQUE_M2).astype(int),
    })
    v = vertices_de_poligonos(d)
    v["lat"] = v["lat"].round(DECIMALES_VERTICES)
    v["lon"] = v["lon"].round(DECIMALES_VERTICES)
    return verdes, v.drop_duplicates()


# ==========================================================================
# CAPAS VERSIONADAS
# ==========================================================================

def construir_capas(forzar: bool, rep: F.Reporte):
    """Baja los crudos (si faltan o se fuerza) y escribe las capas versionadas."""
    rep.titulo("CAPAS: descarga y normalizacion")
    os.makedirs(F.RAW, exist_ok=True)
    partes = []
    for url, lector in [(URL_SUBTE_BOCAS, leer_subte_bocas),
                        (URL_SUBTE_ESTACIONES, leer_subte_estaciones),
                        (URL_TREN, leer_tren), (URL_METROBUS, leer_metrobus)]:
        destino = os.path.join(F.RAW, os.path.basename(url))
        fecha = F.descargar(url, destino, forzar, rep)
        partes.append(lector(destino).assign(fuente=url, fecha_descarga=fecha))
    puntos = pd.concat(partes, ignore_index=True)

    destino = os.path.join(F.RAW, os.path.basename(URL_VERDES))
    fecha = F.descargar(URL_VERDES, destino, forzar, rep)
    verdes, vertices = leer_verdes(destino)
    verdes = verdes.assign(fuente=URL_VERDES, fecha_descarga=fecha)

    puntos.to_csv(CAPA_PUNTOS, index=False, encoding="utf-8-sig")
    verdes.to_csv(CAPA_VERDES, index=False, encoding="utf-8-sig")
    vertices.to_csv(CAPA_VERTICES, index=False, encoding="utf-8-sig")
    for p in (CAPA_PUNTOS, CAPA_VERDES, CAPA_VERTICES):
        rep(f"    {p:<48} {os.path.getsize(p) / 1e3:>8.1f} KB")
    return puntos, verdes, vertices


def cargar_capas():
    puntos = pd.read_csv(CAPA_PUNTOS, encoding="utf-8-sig")
    verdes = pd.read_csv(CAPA_VERDES, encoding="utf-8-sig")
    vertices = pd.read_csv(CAPA_VERTICES, encoding="utf-8-sig")
    return puntos, verdes, vertices


# ==========================================================================
# DISTANCIAS
# ==========================================================================

def distancia_al_mas_cercano(props: pd.DataFrame, puntos: pd.DataFrame):
    """
    Para cada aviso, distancia en metros al punto mas cercano y posicion de
    ese punto en `puntos`.

    El BallTree indexa los puntos una sola vez y resuelve todas las consultas
    juntas. La haversine mide sobre la esfera: la euclidiana sobre grados
    daria mal, porque un grado de longitud mide distinto segun la latitud.
    Los avisos sin coordenadas quedan en NaN, nunca en cero. Si la capa
    viene vacia, todos quedan en NaN.
    """
    validas = props[["latitud", "longitud"]].notna().all(axis=1).values
    dist = np.full(len(props), np.nan)
    pos = np.full(len(props), -1)
    if validas.any() and len(puntos):
        arbol = BallTree(np.radians(puntos[["lat", "lon"]].values), metric="haversine")
        d, idx = arbol.query(np.radians(props.loc[validas, ["latitud", "longitud"]].values), k=1)
        dist[validas] = d[:, 0] * RADIO_TIERRA_M
        pos[validas] = idx[:, 0]
    return dist, pos


def agregar_columnas(df: pd.DataFrame, puntos: pd.DataFrame,
                     verdes: pd.DataFrame, vertices: pd.DataFrame) -> pd.DataFrame:
    """Devuelve `df` con las columnas espaciales, sin agregar ni quitar filas."""
    n = len(df)
    out = df.copy()

    nombres = {}
    for modo in MODOS:
        capa = puntos[(puntos["modo"] == modo) & (puntos["capa"] != "subte_estaciones")]
        capa = capa.reset_index(drop=True)
        dist, pos = distancia_al_mas_cercano(out, capa)
        out[f"dist_{modo}_m"] = np.round(dist, 0)
        nombres[modo] = np.where(pos >= 0, capa["nombre"].values[np.maximum(pos, 0)], None)

    dist_modos = out[[f"dist_{m}_m" for m in MODOS]]
    out["dist_transporte_m"] = dist_modos.min(axis=1)
    con_dato = out["dist_transporte_m"].notna().values
    gana = np.argmin(dist_modos.fillna(np.inf).values, axis=1)
    out["modo_cercano"] = np.where(con_dato, np.array(MODOS)[gana], None)
    out["estacion_cercana"] = np.where(
        con_dato, np.choose(gana, [nombres[m] for m in MODOS]), None)

    plazas = vertices.merge(verdes[["id", "es_parque"]], on="id", how="left", validate="many_to_one")
    for col, sub in [("dist_plaza_m", plazas), ("dist_parque_m", plazas[plazas["es_parque"] == 1])]:
        dist, _ = distancia_al_mas_cercano(out, sub.reset_index(drop=True))
        out[col] = np.round(dist, 0)

    if len(out) != n:
        raise RuntimeError(f"la fusion espacial cambio las filas: {n} -> {len(out)}")
    return out


# ==========================================================================
# REPORTES
# ==========================================================================

def reportar_capas(puntos: pd.DataFrame, verdes: pd.DataFrame,
                   vertices: pd.DataFrame, rep: F.Reporte) -> None:
    rep.titulo("CAPAS")
    for capa, g in puntos.groupby("capa", sort=False):
        rep(f"    {capa:<18} {len(g):>5} puntos   {g['linea'].nunique():>3} lineas/corredores   "
            f"descarga {g['fecha_descarga'].iloc[0]}")
    rep(f"    {'espacios verdes':<18} {len(verdes):>5} poligonos ({int(verdes['es_parque'].sum())} "
        f"parques de 1 ha o mas), {len(vertices):,} vertices")

    # La capa de bocas es de 2019: si alguna estacion vigente no tiene boca
    # cerca, falta red y las distancias al subte quedan infladas.
    bocas = puntos[puntos["capa"] == "subte_bocas"].reset_index(drop=True)
    est = puntos[puntos["capa"] == "subte_estaciones"].rename(columns={"lat": "latitud", "lon": "longitud"})
    d, _ = distancia_al_mas_cercano(est, bocas)
    rep("")
    rep(f"Control: de {len(est)} estaciones de subte vigentes, {int((d > MAX_ESTACION_A_BOCA_M).sum())} "
        f"no tienen una boca a menos de {MAX_ESTACION_A_BOCA_M} m (maximo {np.nanmax(d):.0f} m).")


def reportar_cobertura_dato(df: pd.DataFrame, rep: F.Reporte) -> None:
    """Donde estan los avisos sin coordenadas: si se concentran, sesgan la medida."""
    rep.titulo("COBERTURA DEL DATO: avisos sin coordenadas")
    sin = df[df[["latitud", "longitud"]].isna().any(axis=1)]
    rep(f"Avisos                 : {len(df):,}")
    rep(f"Sin coordenadas        : {len(sin):,} ({len(sin) / len(df) * 100:.2f}%)")
    if sin.empty:
        return
    rep("")
    rep(f"    {'barrio':<20}{'comuna':>7}{'venta':>7}{'alquiler':>10}")
    for (b, c), g in sin.groupby(["barrio", "comuna"]):
        rep(f"    {b:<20}{c:>7}{int((g['operacion'] == 'venta').sum()):>7}"
            f"{int((g['operacion'] == 'alquiler').sum()):>10}")
    # Tasa y no conteo: una comuna con mucha oferta junta mas faltantes sin
    # que su dato sea peor.
    tasa = (df[["latitud", "longitud"]].isna().any(axis=1)
            .groupby(df["comuna"]).mean() * 100).sort_values(ascending=False)
    rep("")
    rep("Tasa de faltantes por comuna (% de los avisos de la comuna):")
    rep("    " + ", ".join(f"comuna {c} {t:.2f}%" for c, t in tasa[tasa > 0].items())
        + f"; las otras {int((tasa == 0).sum())}, 0%.")


def reportar_distancias(out: pd.DataFrame, rep: F.Reporte) -> None:
    rep.titulo("DISTANCIAS (m), avisos con coordenadas")
    rep(f"    {'':<22}{'p10':>8}{'p25':>8}{'mediana':>9}{'p75':>8}{'p90':>8}{'max':>8}")
    for c in ["dist_subte_m", "dist_tren_m", "dist_metrobus_m", "dist_transporte_m",
              "dist_plaza_m", "dist_parque_m"]:
        s = out[c].dropna()
        rep(f"    {c:<22}" + "".join(f"{s.quantile(q):>8,.0f}" for q in (.1, .25)) +
            f"{s.median():>9,.0f}" + "".join(f"{s.quantile(q):>8,.0f}" for q in (.75, .9)) +
            f"{s.max():>8,.0f}")
    rep("")
    m = out["modo_cercano"].value_counts(normalize=True) * 100
    rep("Modo de la red mas cercana: " + ", ".join(f"{k} {v:.1f}%" for k, v in m.items()))


def reportar_por_comuna(out: pd.DataFrame, rep: F.Reporte) -> pd.DataFrame:
    """
    Que agrega la combinacion frente al subte solo, por comuna.

    Se informan tasas (porcentaje de los avisos de la comuna), no conteos: la
    cartera de RE/MAX no pesa lo mismo en cada comuna.
    """
    r = S.RADIO_CAMINATA_M
    rep.titulo(f"ACCESO A MENOS DE {r} m ({S.MINUTOS_CAMINATA} minutos a pie), por comuna")
    c = out[out["dist_transporte_m"].notna()]
    t = c.groupby("comuna").agg(
        avisos=("dist_transporte_m", "size"),
        subte=("dist_subte_m", lambda s: (s <= r).mean() * 100),
        tren=("dist_tren_m", lambda s: (s <= r).mean() * 100),
        metrobus=("dist_metrobus_m", lambda s: (s <= r).mean() * 100),
        combinada=("dist_transporte_m", lambda s: (s <= r).mean() * 100),
        mediana_subte_m=("dist_subte_m", "median"),
        mediana_combinada_m=("dist_transporte_m", "median"),
    )
    t["no_subte_pct"] = c.groupby("comuna")["modo_cercano"].apply(lambda s: (s != "subte").mean() * 100)

    rep(f"    {'comuna':>6}{'avisos':>8}{'subte':>8}{'tren':>8}{'metrob.':>9}{'combin.':>9}"
        f"{'med. subte':>12}{'med. comb.':>12}{'red mas cercana no es subte':>30}")
    for k, f in t.iterrows():
        rep(f"    {k:>6}{int(f['avisos']):>8}{f['subte']:>7.1f}%{f['tren']:>7.1f}%{f['metrobus']:>8.1f}%"
            f"{f['combinada']:>8.1f}%{f['mediana_subte_m']:>10,.0f} m{f['mediana_combinada_m']:>10,.0f} m"
            f"{f['no_subte_pct']:>29.1f}%")
    tot_s, tot_c = (c["dist_subte_m"] <= r).mean() * 100, (c["dist_transporte_m"] <= r).mean() * 100
    rep(f"    {'total':>6}{len(c):>8}{tot_s:>7.1f}%{'':>17}{tot_c:>8.1f}%")
    rep("")
    gan = c[(c["dist_subte_m"] > r) & (c["dist_transporte_m"] <= r)]
    rep(f"Avisos fuera del radio del subte que la combinacion pone dentro: {len(gan):,} "
        f"({len(gan) / len(c) * 100:.1f}% del total).")
    return t


def reportar_heterogeneidad(out: pd.DataFrame, rep: F.Reporte) -> None:
    """Cuanto esconde un promedio barrial: dispersion de la medida dentro de cada barrio."""
    r = S.RADIO_CAMINATA_M
    rep.titulo("HETEROGENEIDAD DENTRO DEL BARRIO (dist_transporte_m)")
    c = out[out["dist_transporte_m"].notna()]
    g = c.groupby("barrio")["dist_transporte_m"]
    t = pd.DataFrame({
        "avisos": g.size(),
        "p10": g.quantile(.1), "mediana": g.median(), "p90": g.quantile(.9),
        "dentro_pct": g.apply(lambda s: (s <= r).mean() * 100),
    })
    t = t[t["avisos"] >= S.MIN_VENTAS_BARRIO]
    mixtos = t[(t["dentro_pct"] >= 10) & (t["dentro_pct"] <= 90)]
    rep(f"Barrios con {S.MIN_VENTAS_BARRIO}+ avisos: {len(t)}. En {len(mixtos)} conviven avisos "
        f"dentro y fuera de los {r} m (entre 10% y 90% dentro):")
    rep(f"un promedio barrial les asignaria a todos el mismo acceso.")
    rep("")
    rep(f"    {'barrio':<22}{'avisos':>7}{'p10':>8}{'mediana':>9}{'p90':>8}{'dentro':>9}")
    for b, f in mixtos.sort_values("p90", ascending=False).iterrows():
        rep(f"    {b:<22}{int(f['avisos']):>7}{f['p10']:>8,.0f}{f['mediana']:>9,.0f}"
            f"{f['p90']:>8,.0f}{f['dentro_pct']:>8.1f}%")


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--descargar", action="store_true",
                   help="vuelve a bajar los crudos de BA Data y rehace las capas")
    args = p.parse_args()

    if not os.path.exists(ENTRADA):
        print(f"No existe {ENTRADA}")
        print("Corré primero:  py src/limpieza.py --tc 1500  &&  py src/variables.py")
        return 1

    rep = F.Reporte()
    rep.titulo("FUSION ESPACIAL")
    rep(f"Fecha   : {datetime.now():%Y-%m-%d %H:%M}")
    rep(f"Entrada : {ENTRADA}")

    capas = (CAPA_PUNTOS, CAPA_VERDES, CAPA_VERTICES)
    if args.descargar or not all(os.path.exists(c) for c in capas):
        puntos, verdes, vertices = construir_capas(args.descargar, rep)
    else:
        puntos, verdes, vertices = cargar_capas()
    reportar_capas(puntos, verdes, vertices, rep)

    df = pd.read_csv(ENTRADA, encoding="utf-8-sig", low_memory=False)
    reportar_cobertura_dato(df, rep)

    out = agregar_columnas(df, puntos, verdes, vertices)
    reportar_distancias(out, rep)
    reportar_por_comuna(out, rep)
    reportar_heterogeneidad(out, rep)

    out.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    rep("")
    rep(f"Archivo: {SALIDA}  ({len(out):,} filas x {out.shape[1]} columnas, "
        f"{len(COLUMNAS_NUEVAS)} nuevas)")
    with open(REPORTE, "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
