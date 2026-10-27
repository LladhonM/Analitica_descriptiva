#!/usr/bin/env python
"""
sesgo.py — Cuanto se aparta la cartera de RE/MAX del mercado de CABA.

Todo el analisis sale de una sola red inmobiliaria. Este script mide ese
sesgo en las dos dimensiones que se pueden contrastar con fuentes oficiales:

  1. PRECIO. El m2 publicado por RE/MAX contra el m2 publicado que calcula
     IDECBA sobre avisos de Argenprop, en la misma celda barrio x ambientes x
     estado (usado / a estrenar). Si RE/MAX publica mas barato, su
     rentabilidad bruta sale mas alta que la del mercado por construccion.
  2. REPRESENTACION. El peso de cada comuna en la cartera contra su peso en
     el stock de departamentos del Censo 2022. La comuna es el nivel mas fino
     con un universo completo y publicado.

Es comparacion descriptiva: no hay test de hipotesis (3ra entrega).

Uso:
    py src/sesgo.py            (despues de kpis.py y fuentes_externas.py)

Salidas (data/processed/):
    sesgo_precio_barrio.csv        RE/MAX contra IDECBA por celda
    sesgo_representacion_comuna.csv  peso en cartera contra peso en el censo
    reporte_sesgo.txt
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

import supuestos as S


ANALITICO = "data/processed/dataset_analitico.csv"
IDECBA = "data/external/estadistica_ciudad_m2_barrio.csv"
CENSO = "data/external/censo_departamentos_comuna.csv"
OUT = "data/processed"


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


def sesgo_precio(d: pd.DataFrame, rep: Reporte) -> pd.DataFrame:
    rep.titulo("1. PRECIO: m2 publicado por RE/MAX contra IDECBA (Argenprop)")
    e = pd.read_csv(IDECBA, encoding="utf-8-sig")
    trims = sorted(e["trimestre"].unique())
    trim, previo = trims[-1], trims[-2]
    # El scraping es de ago-2026 y la ultima referencia es un trimestre anterior.
    # Se mide cuanto se mueve IDECBA de un trimestre al otro para saber si ese
    # desfase puede explicar los desvios.
    tc = e[e["barrio"] == "_total_ciudad"].pivot_table(
        index=["ambientes", "estado"], columns="trimestre", values="usd_m2")
    var = ((tc[trim] / tc[previo] - 1) * 100).abs()
    rep(f"Referencia: IDECBA {trim}; el scraping de RE/MAX es de ago-2026.")
    rep(f"Variacion de IDECBA entre {previo} y {trim} (total ciudad): hasta "
        f"{var.max():.1f}% en valor absoluto. Un desfase de un trimestre no explica")
    rep("desvios mayores a eso.")
    e = e[(e["trimestre"] == trim) & e["usd_m2"].notna()]

    # Misma poblacion que IDECBA: departamentos en venta de 1 a 3 ambientes.
    v = d[(d["operacion"] == "venta") & (d["tipo_familia"] == "departamento")
          & d["ambientes"].isin([1, 2, 3]) & d["venta_m2_usd"].notna()].copy()
    v["estado"] = np.where(v["es_a_estrenar"] == 1, "estrenar", "usado")
    v["ambientes"] = v["ambientes"].astype(int)

    # IDECBA publica PROMEDIOS: se compara promedio contra promedio. La
    # mediana de RE/MAX se guarda al lado para ver si el desvio es de cola.
    r = v.groupby(["barrio", "ambientes", "estado"]).agg(
        n_remax=("venta_m2_usd", "size"),
        remax_media=("venta_m2_usd", "mean"),
        remax_mediana=("venta_m2_usd", "median"),
    ).reset_index()
    tot_r = v.groupby(["ambientes", "estado"]).agg(
        n_remax=("venta_m2_usd", "size"), remax_media=("venta_m2_usd", "mean"),
        remax_mediana=("venta_m2_usd", "median")).reset_index().assign(barrio="_total_ciudad")
    r = pd.concat([r, tot_r], ignore_index=True)

    t = r.merge(e[["barrio", "ambientes", "estado", "usd_m2"]].rename(columns={"usd_m2": "idecba_media"}),
                on=["barrio", "ambientes", "estado"], how="inner", validate="one_to_one")
    t["desvio_pct"] = (t["remax_media"] / t["idecba_media"] - 1) * 100
    tot = t[t["barrio"] == "_total_ciudad"]
    t = t[(t["barrio"] != "_total_ciudad") & (t["n_remax"] >= S.MIN_AVISOS_CELDA)]

    rep("")
    rep("Total ciudad (todas las celdas, sin minimo):")
    for _, x in tot.sort_values(["estado", "ambientes"]).iterrows():
        rep(f"    {x.ambientes} amb {x.estado:<9} RE/MAX USD {x.remax_media:>6,.0f}  "
            f"IDECBA USD {x.idecba_media:>6,.0f}  desvio {x.desvio_pct:+6.1f}%  (n={x.n_remax:,})")

    rep("")
    rep(f"Celdas barrio x ambientes x estado con {S.MIN_AVISOS_CELDA}+ avisos de RE/MAX "
        f"y dato de IDECBA: {len(t)}")
    rep(f"    desvio mediano               : {t['desvio_pct'].median():+.1f}%")
    rep(f"    desvio promedio ponderado por cantidad de avisos: "
        f"{np.average(t['desvio_pct'], weights=t['n_remax']):+.1f}%")
    rep(f"    celdas donde RE/MAX publica mas barato: {int((t['desvio_pct'] < 0).sum())} de {len(t)}")
    rep(f"    celdas con desvio mayor a +-10%       : {int((t['desvio_pct'].abs() > 10).sum())} de {len(t)}")

    b = (t[t["estado"] == "usado"].groupby("barrio")
         .apply(lambda g: np.average(g["desvio_pct"], weights=g["n_remax"]), include_groups=False)
         .sort_values())
    rep("")
    rep("Barrios mas por debajo y mas por encima del mercado (usados, ponderado por n):")
    for nombre, val in list(b.head(5).items()) + [("...", np.nan)] + list(b.tail(5).items()):
        rep(f"    {nombre:<20}{val:+7.1f}%" if nombre != "..." else "    ...")
    rep("")
    rep("Lectura: un desvio negativo significa que la cartera de RE/MAX publica mas")
    rep("barato que el promedio de Argenprop en la misma celda. Como el precio esta en")
    rep("el denominador del KPI 1, la rentabilidad de la cartera sale MAS ALTA que la")
    rep("que daria el mercado publicado. El alquiler estimado tambien sale de avisos de")
    rep("RE/MAX, asi que el efecto neto sobre el KPI depende de si su cartera de")
    rep("alquiler tiene el mismo sesgo, que no hay fuente oficial para medir.")
    return t.round(2)


def sesgo_representacion(d: pd.DataFrame, rep: Reporte) -> pd.DataFrame:
    rep.titulo("2. REPRESENTACION: peso de cada comuna, cartera contra Censo 2022")
    c = pd.read_csv(CENSO, encoding="utf-8-sig")
    deptos = d[d["tipo_familia"] == "departamento"]
    sin_comuna = int(deptos["comuna"].isna().sum())
    rep(f"Departamentos de la cartera sin comuna: {sin_comuna}")

    filas = []
    for op in ["venta", "alquiler"]:
        x = deptos[deptos["operacion"] == op].dropna(subset=["comuna"])
        pct = x["comuna"].astype(int).value_counts(normalize=True) * 100
        filas.append(pct.rename(f"pct_cartera_{op}"))
    t = c.set_index("comuna")[["departamentos", "pct_departamentos_ciudad"]].join(filas)
    t = t.fillna(0)
    for op in ["venta", "alquiler"]:
        t[f"indice_{op}"] = t[f"pct_cartera_{op}"] / t["pct_departamentos_ciudad"]
    t = t.round(2)

    rep(f"{'comuna':>6}{'% censo':>9}{'% venta':>9}{'indice':>8}{'% alq':>8}{'indice':>8}")
    for com, x in t.iterrows():
        rep(f"{com:>6}{x.pct_departamentos_ciudad:>9.1f}{x.pct_cartera_venta:>9.1f}"
            f"{x.indice_venta:>8.2f}{x.pct_cartera_alquiler:>8.1f}{x.indice_alquiler:>8.2f}")
    rep("")
    rep("indice = peso en la cartera / peso en el stock censado. 1 = proporcional;")
    rep("2 = la comuna pesa el doble en la cartera que en la Ciudad.")
    sobre = t[t["indice_venta"] > 1.25].index.tolist()
    sub = t[t["indice_venta"] < 0.75].index.tolist()
    rep(f"Comunas sobrerrepresentadas en ventas (indice > 1,25): {sobre}")
    rep(f"Comunas subrepresentadas en ventas (indice < 0,75)   : {sub}")
    # Distancia total entre las dos distribuciones: mitad de la suma de las
    # diferencias absolutas = % de la cartera que habria que mover de comuna
    # para que tenga la composicion del censo.
    dv = (t["pct_cartera_venta"] - t["pct_departamentos_ciudad"]).abs().sum() / 2
    rep(f"Para replicar la composicion del censo habria que reasignar el {dv:.1f}% de")
    rep("las ventas de la cartera a otras comunas.")
    rep("")
    rep("Lectura: el stock censado no es la oferta (en una comuna puede haber mucho")
    rep("stock y poca rotacion), asi que el indice mide composicion, no error. Lo que")
    rep("importa para generalizar: los promedios de ciudad del trabajo pesan de mas a")
    rep("las comunas sobrerrepresentadas. Por eso los KPIs se leen por barrio.")
    return t.reset_index()


def main() -> int:
    for p in (ANALITICO, IDECBA, CENSO):
        if not os.path.exists(p):
            print(f"No existe {p}. Correr antes: py src/kpis.py  y  py src/fuentes_externas.py")
            return 1
    rep = Reporte()
    rep.titulo("SESGO DE LA CARTERA DE RE/MAX")
    rep(f"Fecha: {datetime.now():%Y-%m-%d %H:%M}")
    d = pd.read_csv(ANALITICO, encoding="utf-8-sig", low_memory=False)

    precio = sesgo_precio(d, rep)
    repres = sesgo_representacion(d, rep)

    p1 = os.path.join(OUT, "sesgo_precio_barrio.csv")
    p2 = os.path.join(OUT, "sesgo_representacion_comuna.csv")
    precio.to_csv(p1, index=False, encoding="utf-8-sig")
    repres.to_csv(p2, index=False, encoding="utf-8-sig")
    rep("")
    rep(f"Archivos: {p1} ({len(precio)} filas), {p2} ({len(repres)} filas)")
    with open(os.path.join(OUT, "reporte_sesgo.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
