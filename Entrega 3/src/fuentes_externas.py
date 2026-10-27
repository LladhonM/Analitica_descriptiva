#!/usr/bin/env python
"""
fuentes_externas.py — Lee tres fuentes externas y las deja agregadas por
barrio (o por mes, a nivel ciudad) en data/external/.

POR QUE EXISTE
--------------
Todo el analisis dependia de la cartera de RE/MAX. Estas tres fuentes dan
un marco externo contra el cual leerla:

  1. Estadistica Ciudad (IDECBA): precio publicado del m2 en USD por barrio,
     ambientes y estado (usado / a estrenar), trimestral, sobre avisos de
     Argenprop. Permite medir el sesgo de la cartera de RE/MAX.
  2. Colegio de Escribanos: escrituras de compraventa e hipotecas por mes,
     a nivel ciudad. Da liquidez del mercado y el monto de cierre.
  3. Inside Airbnb: el alquiler temporal, que es la alternativa de
     explotacion del inmueble que el inversor tiene que poder comparar.
  4. Censo 2022 (via IDECBA): departamentos habitados por comuna. Es el
     universo contra el que se mide si RE/MAX sobre o subrepresenta zonas.

QUE SE VERSIONA Y QUE NO
------------------------
Los crudos van a data/external/raw/, que esta en .gitignore: se vuelven a
bajar con este script. Lo que se versiona son las tablas agregadas, que
pesan kilobytes y llevan su fecha de descarga. Inside Airbnb reemplaza sus
archivos cada trimestre, asi que un script que solo descarga deja de ser
reproducible en pocos meses; el agregado fechado congela la evidencia.

NINGUN JOIN ESPACIAL
--------------------
Las tres fuentes se unen con RE/MAX por NOMBRE de barrio o a nivel ciudad.
La fusion por coordenadas es materia de la 3ra entrega.

Uso:
    py src/fuentes_externas.py              # usa los crudos si ya estan bajados
    py src/fuentes_externas.py --descargar  # fuerza la descarga

Salidas (en data/external/):
    estadistica_ciudad_m2_barrio.csv  USD/m2 publicado, barrio x ambientes x estado
    estadistica_ciudad_m2_serie.csv   total ciudad, serie trimestral desde 2017
    colegio_escribanos_mensual.csv    compraventas e hipotecas por mes
    airbnb_barrio.csv                 ADR, ocupacion e ingreso por barrio
    airbnb_barrio_dormitorios.csv     idem, abierto por dormitorios
    censo_departamentos_comuna.csv    stock de departamentos habitados por comuna
    estadistica_ciudad_tiempo_publicacion.csv  dias publicados, por ambientes y trimestre
    reporte_fuentes.txt               log, incluidas las filas que no se unieron
"""

from __future__ import annotations

import argparse
import json
import warnings
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime

import numpy as np
import pandas as pd

import supuestos as S


# openpyxl avisa por un area de impresion de la hoja "Ficha Tecnica" que no
# se lee: no afecta los datos y taparia el reporte.
warnings.filterwarnings("ignore", module="openpyxl")

RAW = "data/external/raw"
OUT = "data/external"

# --------------------------------------------------------------------------
# Fuentes
# --------------------------------------------------------------------------

_BASE_IDECBA = "https://www.estadisticaciudad.gob.ar/eyc/wp-content/uploads"
# Un cuadro por combinacion ambientes x estado. Los nombres de archivo no
# siguen un orden legible (AX09 es 1 ambiente, AX01 es 2): se listan a mano,
# y leer_idecba() verifica contra el titulo del cuadro que cada uno sea el
# que se dice.
IDECBA = {
    (1, "usado"):    f"{_BASE_IDECBA}/2025/01/MI_DVP_AX10.xlsx",
    (1, "estrenar"): f"{_BASE_IDECBA}/2025/01/MI_DVP_AX09.xlsx",
    (2, "usado"):    f"{_BASE_IDECBA}/2026/01/MI_DVP_AX03.xlsx",
    (2, "estrenar"): f"{_BASE_IDECBA}/2026/01/MI_DVP_AX01.xlsx",
    (3, "usado"):    f"{_BASE_IDECBA}/2026/01/MI_DVP_AX04.xlsx",
    (3, "estrenar"): f"{_BASE_IDECBA}/2026/01/MI_DVP_AX02.xlsx",
}
# Trimestres que se conservan en el agregado: los ultimos 8 alcanzan para
# comparar contra el scraping de ago-2026 y ver la tendencia reciente, sin
# versionar 20 anios de serie que el analisis no usa.
IDECBA_TRIMESTRES = 8

COLEGIO_URL = f"{_BASE_IDECBA}/2026/06/EE_IS_MI_AN_M07.xlsx"
# El cuadro de IDECBA trae 2026 con valores que no corresponden: julio 2026
# figura con 1.159 compraventas y el Colegio informa 6.051 (acumulado ene-jul
# 35.528 contra 6.771 del cuadro). Hasta 2025 coincide con el Colegio (ago-2025:
# 6.372 contra 6.370). Se usa el cuadro hasta 2025 y, para 2026, los informes
# mensuales del Colegio, cargados a mano con su URL. No se scrapea el sitio.
COLEGIO_ULTIMO_ANIO_CUADRO = 2025
COLEGIO_2026 = [
    # (mes, compraventas, hipotecas, monto_promedio_usd, url)
    ("2026-07", 6051, 959, 116_967,
     "https://www.colegio-escribanos.org.ar/2026/08/24/cantidad-de-escrituras-de-compraventa-realizadas-en-julio-2026/"),
    ("2026-08", 6055, 1059, 119_270,
     "https://www.colegio-escribanos.org.ar/2026/09/22/cantidad-de-escrituras-de-compraventa-realizadas-en-agosto-2026/"),
]
# Acumulados que publica el Colegio: sirven de control de los meses sueltos.
COLEGIO_ACUM_ENE_AGO_2026 = {"compraventas": 41_583, "hipotecas": 6_170}

# Censo 2022: viviendas particulares habitadas por tipo, segun comuna. IDECBA
# no publica stock ni oferta por barrio con fecha reciente; la comuna es el
# nivel mas fino con un universo completo.
CENSO_URL = f"{_BASE_IDECBA}/2010/01/V2-P_caba.xlsx"

# Tiempo medio de publicacion de departamentos en venta (Argenprop). Es la
# unica medida publica de liquidez: el scraping es una foto y no ve cuanto
# tarda un aviso en bajarse. Es tiempo publicado, no tiempo de venta.
TIEMPO_PUB_URL = f"{_BASE_IDECBA}/2026/01/MI_DVT.xlsx"

AIRBNB_SNAPSHOT = "2026-06-29"
_BASE_AIRBNB = ("https://data.insideairbnb.com/argentina/"
                + urllib.parse.quote("ciudad-autónoma-de-buenos-aires")
                + f"/buenos-aires/{AIRBNB_SNAPSHOT}")
AIRBNB = {
    "listings": f"{_BASE_AIRBNB}/data/listings.csv.gz",
    "barrios": f"{_BASE_AIRBNB}/visualisations/neighbourhoods.csv",
}

# --------------------------------------------------------------------------
# Barrios
# --------------------------------------------------------------------------

# Los 48 barrios oficiales, en la grafia que usa dataset_analitico.csv.
BARRIOS_CABA = [
    "agronomia", "almagro", "balvanera", "barracas", "belgrano", "boedo",
    "caballito", "chacarita", "coghlan", "colegiales", "constitucion", "flores",
    "floresta", "la boca", "la paternal", "liniers", "mataderos", "monserrat",
    "monte castro", "nueva pompeya", "nunez", "palermo", "parque avellaneda",
    "parque chacabuco", "parque chas", "parque patricios", "puerto madero",
    "recoleta", "retiro", "saavedra", "san cristobal", "san nicolas",
    "san telmo", "velez sarsfield", "versalles", "villa crespo",
    "villa del parque", "villa devoto", "villa gral. mitre", "villa lugano",
    "villa luro", "villa ortuzar", "villa pueyrredon", "villa real",
    "villa riachuelo", "villa santa rita", "villa soldati", "villa urquiza",
]
# Grafias oficiales alternativas que usan las fuentes externas. Son pocas
# porque las tres usan nombres oficiales; los alias de portal ("palermo soho")
# no aparecen aca y por eso no se copio el normalizador de la 1ra entrega.
ALIAS = {
    "boca": "la boca",
    "paternal": "la paternal",
    "montserrat": "monserrat",
    "villa general mitre": "villa gral. mitre",
}


def normalizar_barrio(texto) -> str | None:
    """
    Nombre de barrio -> grafia oficial de dataset_analitico, o None.

    Devuelve None en vez de adivinar: un barrio mal asignado contamina la
    mediana de otro sin que nada lo advierta, mientras que un None se cuenta
    y se reporta.
    """
    if not isinstance(texto, str):
        return None
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"\s+", " ", t.lower()).strip()
    t = ALIAS.get(t, t)
    return t if t in BARRIOS_CABA else None


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

class Reporte:
    def __init__(self):
        self.lineas: list[str] = []

    def __call__(self, t: str = "") -> None:
        print(t)
        self.lineas.append(t)

    def titulo(self, t: str) -> None:
        self("")
        self("=" * 76)
        self(t)
        self("=" * 76)


def descargar(url: str, destino: str, forzar: bool, rep: Reporte) -> str:
    """Baja `url` a `destino` si no esta o si se fuerza. Devuelve la fecha de descarga."""
    manifiesto = os.path.join(RAW, "_descargas.json")
    fechas = json.load(open(manifiesto, encoding="utf-8")) if os.path.exists(manifiesto) else {}
    nombre = os.path.basename(destino)
    if forzar or not os.path.exists(destino):
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=300) as r, open(destino, "wb") as f:
            f.write(r.read())
        fechas[nombre] = date.today().isoformat()
        json.dump(fechas, open(manifiesto, "w", encoding="utf-8"), indent=1)
        rep(f"    descargado {nombre} ({os.path.getsize(destino) / 1e6:.1f} MB)")
    # Si el crudo se bajo a mano, la mejor aproximacion es la fecha del archivo.
    return fechas.get(nombre) or datetime.fromtimestamp(os.path.getmtime(destino)).date().isoformat()


# --------------------------------------------------------------------------
# 1. Estadistica Ciudad
# --------------------------------------------------------------------------

def leer_cuadro_idecba(path: str) -> tuple[str, pd.DataFrame]:
    """
    Pasa un cuadro trimestral de IDECBA (ancho, con anios en una fila y
    trimestres en otra) a formato largo: barrio, trimestre, usd_m2.
    """
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    titulo = filas[0][0]

    # El anio aparece solo en la primera columna de cada bloque: se arrastra.
    anio, cols = None, []
    for j, (a, t) in enumerate(zip(filas[1], filas[2])):
        if isinstance(a, (int, float)):
            anio = int(a)
        if j == 0 or t is None:
            continue
        q = re.match(r"\s*(\d)", str(t))
        cols.append((j, f"{anio}-T{q.group(1)}", "*" in str(t)))

    registros = []
    for f in filas[3:]:
        nombre = f[0]
        # Las notas al pie empiezan con simbolos o palabras clave; los barrios no.
        if not isinstance(nombre, str) or nombre.startswith(("*", "///", "Nota", "Hasta",
                                                             "Los datos", "La info", "Fuente")):
            continue
        for j, trim, provisorio in cols:
            v = f[j] if j < len(f) else None
            registros.append({"barrio_fuente": nombre.strip(), "trimestre": trim,
                              "usd_m2": v if isinstance(v, (int, float)) else np.nan,
                              "provisorio": provisorio})
    return titulo, pd.DataFrame(registros)


def estadistica_ciudad(forzar: bool, rep: Reporte) -> pd.DataFrame:
    rep.titulo("1. ESTADISTICA CIUDAD — USD/m2 publicado por barrio")
    partes, fechas = [], set()
    for (amb, estado), url in IDECBA.items():
        destino = os.path.join(RAW, os.path.basename(url))
        fechas.add(descargar(url, destino, forzar, rep))
        titulo, d = leer_cuadro_idecba(destino)
        # Verificacion contra el titulo: el nombre del archivo no dice que
        # contiene, y un cuadro cruzado mezclaria 2 y 3 ambientes en silencio.
        esperado_amb = f"{amb} ambiente"
        esperado_est = "usados" if estado == "usado" else "a estrenar"
        if esperado_amb not in titulo or esperado_est not in titulo or "por barrio" not in titulo:
            raise ValueError(f"{os.path.basename(url)} no es {amb} amb {estado}: {titulo[:120]}")
        partes.append(d.assign(ambientes=amb, estado=estado))

    d = pd.concat(partes, ignore_index=True)
    trimestres = sorted(d["trimestre"].unique())[-IDECBA_TRIMESTRES:]
    d = d[d["trimestre"].isin(trimestres)]

    total = d[d["barrio_fuente"] == "Total"]
    d = d[d["barrio_fuente"] != "Total"].copy()
    d["barrio"] = d["barrio_fuente"].map(normalizar_barrio)
    sin = sorted(d.loc[d["barrio"].isna(), "barrio_fuente"].unique())
    rep(f"Cuadros leidos: {len(IDECBA)} (1, 2 y 3 ambientes x usado / a estrenar)")
    rep(f"Trimestres conservados: {trimestres[0]} a {trimestres[-1]}")
    rep(f"Barrios de la fuente sin equivalente oficial: {sin if sin else 'ninguno'}")
    faltan = sorted(set(BARRIOS_CABA) - set(d["barrio"].dropna()))
    rep(f"Barrios oficiales ausentes de la fuente     : {faltan if faltan else 'ninguno'}")

    d = d.dropna(subset=["barrio"])
    ult = trimestres[-1]
    con = d[(d["trimestre"] == ult) & d["usd_m2"].notna()]
    rep("")
    rep(f"Cobertura en {ult} (celdas con dato; IDECBA suprime las de pocos avisos):")
    for (amb, est), g in con.groupby(["ambientes", "estado"]):
        tot = total[(total["trimestre"] == ult) & (total["ambientes"] == amb)
                    & (total["estado"] == est)]["usd_m2"]
        rep(f"    {amb} amb {est:<9}: {len(g):>2} barrios   total ciudad "
            f"USD {float(tot.iloc[0]):,.0f}/m2" if len(tot) else "")

    # El total de ciudad se conserva como fila propia: es la referencia
    # agregada contra la que se compara la cartera entera.
    total = total.assign(barrio="_total_ciudad")
    out = pd.concat([d, total], ignore_index=True)
    out["fecha_descarga"] = max(fechas)
    out["fuente"] = "IDECBA sobre avisos de Argenprop"
    return out[["barrio", "barrio_fuente", "ambientes", "estado", "trimestre",
                "usd_m2", "provisorio", "fuente", "fecha_descarga"]]


def tiempo_publicacion(forzar: bool, rep: Reporte) -> pd.DataFrame:
    rep.titulo("5. ESTADISTICA CIUDAD — tiempo medio de publicacion")
    import openpyxl
    destino = os.path.join(RAW, os.path.basename(TIEMPO_PUB_URL))
    fecha = descargar(TIEMPO_PUB_URL, destino, forzar, rep)
    ws = openpyxl.load_workbook(destino, read_only=True, data_only=True).worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    titulo = filas[0][0]
    if "Tiempo medio de publicaci" not in titulo or "en venta" not in titulo:
        raise ValueError(f"MI_DVT no es el cuadro esperado: {titulo[:100]}")
    # Encabezado: Periodo | (trimestre) | Total | 1 ambiente | ... Se leen los
    # nombres de columna para no depender de su posicion.
    encabezado = filas[1]
    cols = {j: str(c).strip() for j, c in enumerate(encabezado) if j >= 2 and c}
    registros, anio = [], None
    for f in filas[2:]:
        if isinstance(f[0], (int, float)):
            anio = int(f[0])
        q = re.match(r"\s*(\d)", str(f[1])) if f[1] else None
        if not q or anio is None:
            continue
        for j, nombre in cols.items():
            v = f[j]
            if isinstance(v, (int, float)):
                registros.append({"trimestre": f"{anio}-T{q.group(1)}", "ambientes": nombre,
                                  "dias": round(float(v), 1), "provisorio": "*" in str(f[1])})
    d = pd.DataFrame(registros)
    ult = d["trimestre"].max()
    tot = d[(d["trimestre"] == ult) & (d["ambientes"] == "Total")]["dias"].iloc[0]
    rep(f"Trimestres: {d['trimestre'].min()} a {ult}; categorias: {', '.join(cols.values())}")
    rep(f"Ultimo trimestre, total: {tot:.0f} dias publicados en promedio")
    d["fuente"] = "IDECBA sobre avisos de Argenprop"
    d["fecha_descarga"] = fecha
    return d


# Serie larga solo para el total de la Ciudad: es la que da el contexto
# historico (el scraping es una sola foto) y pesa poco. Desde 2017 porque es
# desde cuando existen los seis cuadros, incluido el de 1 ambiente.
IDECBA_SERIE_DESDE = "2017-T1"


def estadistica_ciudad_serie(forzar: bool, rep: Reporte) -> pd.DataFrame:
    rep.titulo("1b. ESTADISTICA CIUDAD — serie del total de la Ciudad")
    partes, fechas = [], set()
    for (amb, estado), url in IDECBA.items():
        destino = os.path.join(RAW, os.path.basename(url))
        fechas.add(descargar(url, destino, forzar, rep))
        _, d = leer_cuadro_idecba(destino)
        partes.append(d[d["barrio_fuente"] == "Total"].assign(ambientes=amb, estado=estado))
    d = pd.concat(partes, ignore_index=True)
    d = d[d["trimestre"] >= IDECBA_SERIE_DESDE].dropna(subset=["usd_m2"])
    rep(f"Trimestres: {d['trimestre'].min()} a {d['trimestre'].max()}, "
        f"{d['trimestre'].nunique()} por serie como maximo; {len(d)} filas")
    d["fecha_descarga"] = max(fechas)
    d["fuente"] = "IDECBA sobre avisos de Argenprop"
    return d[["ambientes", "estado", "trimestre", "usd_m2", "provisorio", "fuente", "fecha_descarga"]]


# --------------------------------------------------------------------------
# 2. Colegio de Escribanos
# --------------------------------------------------------------------------

MESES = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
     "septiembre", "octubre", "noviembre", "diciembre"], 1)}


def colegio(forzar: bool, rep: Reporte) -> pd.DataFrame:
    rep.titulo("2. COLEGIO DE ESCRIBANOS — compraventas e hipotecas por mes")
    import openpyxl
    destino = os.path.join(RAW, os.path.basename(COLEGIO_URL))
    fecha = descargar(COLEGIO_URL, destino, forzar, rep)
    ws = openpyxl.load_workbook(destino, read_only=True, data_only=True).worksheets[0]

    registros, anio = [], None
    for f in ws.iter_rows(min_row=3, values_only=True):
        c0 = f[0]
        if isinstance(c0, (int, float)):
            anio = int(c0)
            continue
        if isinstance(c0, str) and c0.strip().lower() in MESES and anio:
            registros.append({"mes": f"{anio}-{MESES[c0.strip().lower()]:02d}",
                              "compraventas": f[1], "hipotecas": f[3],
                              "monto_compraventas_ars": f[2]})
    d = pd.DataFrame(registros)
    descartados = d[d["mes"].str[:4].astype(int) > COLEGIO_ULTIMO_ANIO_CUADRO]
    d = d[d["mes"].str[:4].astype(int) <= COLEGIO_ULTIMO_ANIO_CUADRO].copy()
    rep(f"Cuadro IDECBA: {len(d)} meses usados ({d['mes'].min()} a {d['mes'].max()})")
    rep(f"Descartados del cuadro por inconsistentes con el Colegio: {len(descartados)} meses de 2026")
    rep(f"    (el cuadro suma {int(descartados['compraventas'].sum()):,} compraventas ene-jul 2026; "
        f"el Colegio informa 35.528)")
    d["fuente"] = "IDECBA sobre datos del Colegio de Escribanos"
    d["url"] = COLEGIO_URL

    extra = pd.DataFrame(COLEGIO_2026, columns=["mes", "compraventas", "hipotecas",
                                                "monto_promedio_usd", "url"])
    extra["fuente"] = "Colegio de Escribanos, informe mensual"
    d = pd.concat([d, extra], ignore_index=True)
    d["pct_con_hipoteca"] = (d["hipotecas"] / d["compraventas"] * 100).round(1)
    d["fecha_descarga"] = fecha

    rep(f"Informes del Colegio cargados para 2026: {', '.join(m for m, *_ in COLEGIO_2026)}")
    for m, cv, h, usd, _ in COLEGIO_2026:
        rep(f"    {m}: {cv:,} compraventas, {h:,} con hipoteca ({h / cv * 100:.1f}%), "
            f"promedio USD {usd:,}")
    rep(f"Control: el acumulado ene-ago 2026 que publica el Colegio es "
        f"{COLEGIO_ACUM_ENE_AGO_2026['compraventas']:,} compraventas y "
        f"{COLEGIO_ACUM_ENE_AGO_2026['hipotecas']:,} hipotecas.")
    ult12 = d[d["mes"].between("2025-01", "2025-12")]
    rep(f"Año 2025 completo: {int(ult12['compraventas'].sum()):,} compraventas, "
        f"{ult12['hipotecas'].sum() / ult12['compraventas'].sum() * 100:.1f}% con hipoteca")
    return d[["mes", "compraventas", "hipotecas", "pct_con_hipoteca",
              "monto_compraventas_ars", "monto_promedio_usd", "fuente", "url", "fecha_descarga"]]


# --------------------------------------------------------------------------
# 3. Inside Airbnb
# --------------------------------------------------------------------------

def airbnb(forzar: bool, rep: Reporte) -> tuple[pd.DataFrame, pd.DataFrame]:
    rep.titulo(f"3. INSIDE AIRBNB — snapshot {AIRBNB_SNAPSHOT}")
    destino = os.path.join(RAW, f"airbnb_listings_{AIRBNB_SNAPSHOT}.csv.gz")
    fecha = descargar(AIRBNB["listings"], destino, forzar, rep)
    a = pd.read_csv(destino, low_memory=False)
    rep(f"Avisos en el snapshot: {len(a):,}")

    # Solo unidades enteras: es lo comparable con comprar un departamento
    # para alquilarlo. Una habitacion privada es otro negocio.
    a = a[a["room_type"] == "Entire home/apt"].copy()
    rep(f"    unidades enteras (Entire home/apt): {len(a):,}")

    a["precio_ars"] = pd.to_numeric(a["price"].astype(str).str.replace(r"[$,]", "", regex=True),
                                    errors="coerce")
    # Activos: con al menos una resenia en los ultimos 12 meses. Un aviso sin
    # actividad reciente no informa sobre lo que rinde el temporal hoy, y la
    # ocupacion de Inside Airbnb se estima justamente a partir de resenias.
    a["activo"] = a["number_of_reviews_ltm"] > 0
    rep(f"    activos (reseña en los ultimos 12 meses): {int(a['activo'].sum()):,}")

    a["barrio"] = a["neighbourhood_cleansed"].map(normalizar_barrio)
    sin = a.loc[a["barrio"].isna(), "neighbourhood_cleansed"].value_counts()
    rep(f"Sin barrio oficial: {int(sin.sum())} avisos {dict(sin)}")
    faltan = sorted(set(BARRIOS_CABA) - set(a["barrio"].dropna()))
    rep(f"Barrios oficiales sin avisos: {faltan if faltan else 'ninguno'}")
    a = a.dropna(subset=["barrio"])

    act = a[a["activo"] & a["precio_ars"].gt(0)].copy()
    act["ocupacion_pct"] = act["estimated_occupancy_l365d"] / 365 * 100
    act["dormitorios"] = pd.cut(act["bedrooms"].fillna(-1), [-2, -0.5, 1, 2, 99],
                                labels=["s/d", "0-1", "2", "3+"])

    def agregar(g: pd.core.groupby.DataFrameGroupBy) -> pd.DataFrame:
        return g.agg(
            n_activos=("id", "size"),
            adr_mediana_ars=("precio_ars", "median"),
            ocupacion_mediana_pct=("ocupacion_pct", "median"),
            noches_mediana=("estimated_occupancy_l365d", "median"),
            ingreso_anual_mediano_ars=("estimated_revenue_l365d", "median"),
        ).round(1)

    por_barrio = agregar(act.groupby("barrio"))
    por_barrio["n_unidades_enteras"] = a.groupby("barrio").size()
    por_dorm = agregar(act.groupby(["barrio", "dormitorios"], observed=True)).reset_index()

    for t in (por_barrio, por_dorm):
        # A USD con el mismo tipo de cambio que el resto del pipeline, para
        # que la comparacion contra el alquiler tradicional no mezcle TC.
        t["adr_mediana_usd"] = (t["adr_mediana_ars"] / S.TC_ARS_USD).round(1)
        t["ingreso_anual_mediano_usd"] = (t["ingreso_anual_mediano_ars"] / S.TC_ARS_USD).round(0)
        t["tc_ars_usd"] = S.TC_ARS_USD
        t["snapshot"] = AIRBNB_SNAPSHOT
        t["fecha_descarga"] = fecha

    rep("")
    rep(f"Ciudad (activos, unidades enteras): ADR mediano ARS {act['precio_ars'].median():,.0f} "
        f"(USD {act['precio_ars'].median() / S.TC_ARS_USD:,.0f}), "
        f"ocupacion estimada mediana {act['ocupacion_pct'].median():.1f}%")
    rep(f"Barrios con 30 o mas activos: {int((por_barrio['n_activos'] >= 30).sum())} de {len(por_barrio)}")
    rep("La ocupacion y el ingreso son ESTIMACIONES de Inside Airbnb a partir de")
    rep("reseñas, no datos observados de reservas.")
    return por_barrio.reset_index(), por_dorm


# --------------------------------------------------------------------------

def censo(forzar: bool, rep: Reporte) -> pd.DataFrame:
    rep.titulo("4. CENSO 2022 — departamentos habitados por comuna")
    import openpyxl
    destino = os.path.join(RAW, os.path.basename(CENSO_URL))
    fecha = descargar(CENSO_URL, destino, forzar, rep)
    ws = openpyxl.load_workbook(destino, read_only=True, data_only=True)["2022"]
    filas = list(ws.iter_rows(values_only=True))
    # Encabezado en dos filas: la columna "Departamento" se busca por nombre
    # para no depender de su posicion.
    col = next(j for j, c in enumerate(filas[2]) if isinstance(c, str) and c.strip() == "Departamento")
    registros, comuna = [], None
    for f in filas[3:]:
        if isinstance(f[0], (int, float)):
            comuna = int(f[0])
        elif f[0] == "Viviendas" and comuna is not None:
            registros.append({"comuna": comuna, "viviendas": f[1], "departamentos": f[col]})
    d = pd.DataFrame(registros)
    if sorted(d["comuna"]) != list(range(1, 16)):
        raise ValueError(f"se esperaban las 15 comunas, se leyeron {sorted(d['comuna'])}")
    d["pct_departamentos_ciudad"] = (d["departamentos"] / d["departamentos"].sum() * 100).round(2)
    d["fuente"] = "INDEC, Censo 2022, via IDECBA"
    d["fecha_descarga"] = fecha
    rep(f"Comunas: {len(d)}; departamentos habitados en la Ciudad: {int(d['departamentos'].sum()):,}")
    rep("Es stock censado, no oferta: sirve para ver que zonas pesan mas o menos")
    rep("en la cartera de lo que pesan en la Ciudad, no para medir la oferta.")
    return d


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--descargar", action="store_true", help="fuerza la descarga de los crudos")
    args = p.parse_args()

    os.makedirs(RAW, exist_ok=True)
    rep = Reporte()
    rep.titulo("FUENTES EXTERNAS")
    rep(f"Fecha: {datetime.now():%Y-%m-%d %H:%M}")

    errores = []
    salidas = {}
    for nombre, fn in [("estadistica_ciudad_m2_barrio", estadistica_ciudad),
                       ("estadistica_ciudad_m2_serie", estadistica_ciudad_serie),
                       ("colegio_escribanos_mensual", colegio),
                       ("censo_departamentos_comuna", censo),
                       ("estadistica_ciudad_tiempo_publicacion", tiempo_publicacion)]:
        try:
            salidas[nombre] = fn(args.descargar, rep)
        except Exception as e:  # una fuente caida no debe tirar las otras dos
            errores.append(f"{nombre}: {type(e).__name__}: {e}")
            rep(f"ERROR en {nombre}: {e}")
    try:
        b, bd = airbnb(args.descargar, rep)
        salidas["airbnb_barrio"], salidas["airbnb_barrio_dormitorios"] = b, bd
    except Exception as e:
        errores.append(f"airbnb: {type(e).__name__}: {e}")
        rep(f"ERROR en airbnb: {e}")

    rep.titulo("ARCHIVOS")
    for nombre, t in salidas.items():
        path = os.path.join(OUT, f"{nombre}.csv")
        t.to_csv(path, index=False, encoding="utf-8-sig")
        rep(f"    {path:<48} {len(t):>6,} filas  {os.path.getsize(path) / 1e3:>6.1f} KB")
    if errores:
        rep("")
        rep(f"{len(errores)} fuente(s) con error:")
        for e in errores:
            rep(f"    {e}")
    with open(os.path.join(OUT, "reporte_fuentes.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lineas))
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
