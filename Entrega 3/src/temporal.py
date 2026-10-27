#!/usr/bin/env python
"""
temporal.py — Alquiler tradicional contra temporal, neta contra neta.

LA PREGUNTA
-----------
Si el inversor compra una unidad, ¿le conviene alquilarla con contrato o por
noche? Es la P3 del README. Se responde por barrio x dormitorios, que es la
unidad comparable: un monoambiente en Palermo contra un monoambiente en
Palermo.

POR QUE NETA CONTRA NETA
------------------------
El ingreso bruto del temporal es mucho mayor por noche, pero carga costos que
el tradicional no tiene: comision de plataforma, gestion, desgaste,
amoblamiento, y sobre todo expensas y servicios, que en el tradicional paga
el inquilino. Comparar bruto de temporal contra neta de tradicional decide
el resultado antes de mirar los datos.

POR QUE LA OCUPACION DE EQUILIBRIO
----------------------------------
La ocupacion del temporal no se observa: Inside Airbnb la estima a partir de
resenias, y su mediana (~21%) queda muy por debajo del 53% que publica la
prensa. Con esa incertidumbre, el numero mas robusto no es "cuanto rinde"
sino "con cuanta ocupacion empata al tradicional". Ese umbral se calcula
sin necesitar la ocupacion, y despues cada uno lo compara con la que crea.

Uso:
    py src/temporal.py

Entradas:
    data/processed/dataset_analitico.csv   precio y alquiler estimado (RE/MAX)
    data/external/airbnb_barrio_dormitorios.csv   ADR y ocupacion (Airbnb)

Salidas:
    data/processed/temporal_vs_tradicional.csv
    data/processed/reporte_temporal.txt
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pandas as pd

import supuestos as S


ANALITICO = "data/processed/dataset_analitico.csv"
AIRBNB = "data/external/airbnb_barrio_dormitorios.csv"
SALIDA = "data/processed/temporal_vs_tradicional.csv"
REPORTE = "data/processed/reporte_temporal.txt"

# Mismos cortes que fuentes_externas.py usa para Airbnb (bedrooms): si no
# coinciden, se compara un 2 dormitorios contra un monoambiente.
CORTES_DORM = [-0.5, 1, 2, 99]
ETIQUETAS_DORM = ["0-1", "2", "3+"]


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


def lado_remax(ruta: str = ANALITICO) -> pd.DataFrame:
    """Precio, alquiler estimado y expensas medianas por barrio x dormitorios."""
    d = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
    # Solo departamentos: Airbnb en unidades enteras es casi todo departamento,
    # y casas y PH tienen expensas cero, lo que inflaria el temporal.
    v = d[(d["operacion"] == "venta") & (d["tipo_familia"] == "departamento")
          & (d["estimacion_confiable"] == 1) & d["rent_bruta_pct"].notna()].copy()
    v["dormitorios_grupo"] = pd.cut(v["dormitorios"], CORTES_DORM, labels=ETIQUETAS_DORM)
    return v.groupby(["barrio", "dormitorios_grupo"], observed=True).agg(
        n_ventas=("venta_usd", "size"),
        venta_mediana_usd=("venta_usd", "median"),
        alquiler_est_mediano_usd=("alquiler_est_usd_mes", "median"),
        expensas_mediana_usd=("expensas_usd", "median"),
        # El ABL de cada propiedad (kpis.py): lo paga el duenio en los dos
        # modos, asi que entra en la neta tradicional y en los fijos del temporal.
        gastos_mediana_pct=("gastos_pct", "median"),
        abl_mediano_usd_mes=("abl_ars_mes", lambda s: s.median() / S.TC_ARS_USD),
    ).reset_index()


def comparar(rep: Reporte) -> pd.DataFrame:
    r = lado_remax()
    a = pd.read_csv(AIRBNB, encoding="utf-8-sig").rename(columns={"dormitorios": "dormitorios_grupo"})
    a = a[a["dormitorios_grupo"].isin(ETIQUETAS_DORM)]
    t = r.merge(a, on=["barrio", "dormitorios_grupo"], how="inner", validate="one_to_one")
    rep(f"Celdas barrio x dormitorios con ambos lados: {len(t)}")
    t = t[(t["n_ventas"] >= S.MIN_CELDA_TEMPORAL) & (t["n_activos"] >= S.MIN_CELDA_TEMPORAL)].copy()
    rep(f"    con {S.MIN_CELDA_TEMPORAL}+ ventas y {S.MIN_CELDA_TEMPORAL}+ avisos activos: {len(t)}")

    # --- Tradicional: los mismos supuestos que el KPI 2 ---------------------
    # Los gastos son los medianos de la celda: con el ABL segmentado, cada
    # propiedad tiene los suyos.
    f_trad = (1 - S.VACANCIA_PCT / 100) * (1 - t["gastos_mediana_pct"] / 100)
    t["trad_neta_usd"] = t["alquiler_est_mediano_usd"] * 12 * f_trad
    t["trad_neta_pct"] = t["trad_neta_usd"] / t["venta_mediana_usd"] * 100

    # --- Temporal ------------------------------------------------------------
    # Margen variable: lo que queda de cada dolar de ingreso bruto.
    margen = ((1 - S.COMISION_PLATAFORMA_PCT / 100) * (1 - S.GESTION_TEMPORAL_PCT / 100)
              - S.MANTENIMIENTO_TEMPORAL_PCT / 100)
    margen_auto = (1 - S.COMISION_PLATAFORMA_PCT / 100) - S.MANTENIMIENTO_TEMPORAL_PCT / 100
    # Fijos anuales: se pagan haya o no huespedes. El ABL tambien lo paga el
    # duenio en el tradicional, pero ahi ya esta dentro de los gastos.
    t["fijos_usd"] = ((t["expensas_mediana_usd"]
                       + S.SERVICIOS_ARS_MES / S.TC_ARS_USD
                       + t["abl_mediano_usd_mes"]) * 12
                      + t["dormitorios_grupo"].map(S.AMOBLAMIENTO_USD) / S.HORIZONTE_ANIOS)
    bruto_pleno = t["adr_mediana_usd"] * 365   # ingreso con 100% de ocupacion

    def neta_temp(ocup_pct, m):
        return bruto_pleno * ocup_pct / 100 * m - t["fijos_usd"]

    t["temp_bruto_usd"] = bruto_pleno * t["ocupacion_mediana_pct"] / 100
    t["temp_neta_usd"] = neta_temp(t["ocupacion_mediana_pct"], margen)
    t["temp_neta_pct"] = t["temp_neta_usd"] / t["venta_mediana_usd"] * 100
    t["temp_neta_ref_pct"] = neta_temp(S.OCUPACION_REF_PCT, margen) / t["venta_mediana_usd"] * 100
    t["temp_neta_auto_pct"] = neta_temp(t["ocupacion_mediana_pct"], margen_auto) / t["venta_mediana_usd"] * 100

    # Ocupacion con la que el temporal empata al tradicional:
    #   bruto_pleno x o x margen - fijos = trad_neta  ->  o = (trad + fijos) / (bruto_pleno x margen)
    t["ocupacion_equilibrio_pct"] = (t["trad_neta_usd"] + t["fijos_usd"]) / (bruto_pleno * margen) * 100
    t["ocupacion_equilibrio_auto_pct"] = (t["trad_neta_usd"] + t["fijos_usd"]) / (bruto_pleno * margen_auto) * 100
    t["gana_temporal_base"] = t["temp_neta_pct"] > t["trad_neta_pct"]
    t["gana_temporal_ref"] = t["temp_neta_ref_pct"] > t["trad_neta_pct"]

    rep("")
    rep(f"Margen variable del temporal: {margen:.3f} con gestion "
        f"({S.GESTION_TEMPORAL_PCT:.0f}%), {margen_auto:.3f} autogestionado")
    rep(f"    = (1 - plataforma {S.COMISION_PLATAFORMA_PCT}%) x (1 - gestion) "
        f"- mantenimiento {S.MANTENIMIENTO_TEMPORAL_PCT}%")
    rep(f"Fijos anuales: expensas y ABL (medianas de la celda) + servicios "
        f"USD {S.SERVICIOS_ARS_MES / S.TC_ARS_USD:,.0f}/mes")
    rep(f"    + amoblamiento {S.AMOBLAMIENTO_USD} en {S.HORIZONTE_ANIOS} anios")
    return t


def main() -> int:
    for p in (ANALITICO, AIRBNB):
        if not os.path.exists(p):
            print(f"No existe {p}. Correr antes: py src/kpis.py  y  py src/fuentes_externas.py")
            return 1

    rep = Reporte()
    rep.titulo("ALQUILER TRADICIONAL CONTRA TEMPORAL — NETA CONTRA NETA")
    rep(f"Fecha: {datetime.now():%Y-%m-%d %H:%M}")
    t = comparar(rep)

    rep.titulo("POR BARRIO Y DORMITORIOS")
    cols = ["barrio", "dormitorios_grupo", "n_ventas", "n_activos", "trad_neta_pct",
            "ocupacion_mediana_pct", "temp_neta_pct", "temp_neta_ref_pct",
            "ocupacion_equilibrio_pct"]
    tab = t[cols].sort_values(["dormitorios_grupo", "ocupacion_equilibrio_pct"])
    rep(f"{'barrio':<18}{'dorm':>5}{'vtas':>6}{'abnb':>6}{'trad%':>7}{'ocup%':>7}"
        f"{'temp%':>7}{'t@ref%':>8}{'equil%':>8}")
    for _, x in tab.iterrows():
        rep(f"{x.barrio:<18}{x.dormitorios_grupo:>5}{x.n_ventas:>6}{x.n_activos:>6}"
            f"{x.trad_neta_pct:>7.2f}{x.ocupacion_mediana_pct:>7.1f}{x.temp_neta_pct:>7.2f}"
            f"{x.temp_neta_ref_pct:>8.2f}{x.ocupacion_equilibrio_pct:>8.1f}")
    rep("")
    rep("trad%  : neta del tradicional (supuestos del KPI 2)")
    rep("ocup%  : ocupacion estimada por Inside Airbnb (mediana de la celda)")
    rep("temp%  : neta del temporal con esa ocupacion y gestion tercerizada")
    rep(f"t@ref% : neta del temporal con la ocupacion de referencia ({S.OCUPACION_REF_PCT:.0f}%)")
    rep("equil% : ocupacion con la que el temporal empata al tradicional")

    rep.titulo("LECTURA")
    n = len(t)
    rep(f"Celdas comparadas: {n}")
    rep(f"    el temporal gana con la ocupacion estimada por Inside Airbnb : "
        f"{int(t['gana_temporal_base'].sum())} de {n}")
    rep(f"    el temporal gana con ocupacion de {S.OCUPACION_REF_PCT:.0f}%                        : "
        f"{int(t['gana_temporal_ref'].sum())} de {n}")
    rep(f"Ocupacion de equilibrio: mediana {t['ocupacion_equilibrio_pct'].median():.1f}% "
        f"(rango {t['ocupacion_equilibrio_pct'].min():.1f}% a {t['ocupacion_equilibrio_pct'].max():.1f}%)")
    rep(f"    autogestionado: mediana {t['ocupacion_equilibrio_auto_pct'].median():.1f}%")
    rep(f"Ocupacion estimada por Inside Airbnb en esas celdas: mediana "
        f"{t['ocupacion_mediana_pct'].median():.1f}%")
    # Robustez: los dos supuestos mas debiles del lado temporal son los
    # servicios (dato de invierno de un hogar, un techo) y el amoblamiento
    # (estimacion propia). Si la conclusion se da vuelta sin ellos, no se
    # sostiene; si no, es robusta a esos dos numeros.
    margen = ((1 - S.COMISION_PLATAFORMA_PCT / 100) * (1 - S.GESTION_TEMPORAL_PCT / 100)
              - S.MANTENIMIENTO_TEMPORAL_PCT / 100)
    fijos_min = (t["expensas_mediana_usd"] + S.SERVICIOS_ARS_MES / 2 / S.TC_ARS_USD
                 + t["abl_mediano_usd_mes"]) * 12
    eq_min = (t["trad_neta_usd"] + fijos_min) / (t["adr_mediana_usd"] * 365 * margen) * 100
    rep(f"Robustez: con servicios a la mitad y sin amoblamiento, la ocupacion de")
    rep(f"    equilibrio mediana baja a {eq_min.median():.1f}% (de "
        f"{t['ocupacion_equilibrio_pct'].median():.1f}%).")

    rep("")
    base, ref = int(t["gana_temporal_base"].sum()), int(t["gana_temporal_ref"].sum())
    rep("La conclusion depende de una variable que ningun dataset de este trabajo")
    rep(f"observa: la ocupacion. Con la que estima Inside Airbnb el temporal gana en")
    rep(f"{base} de {n} celdas; aun con la ocupacion de prensa ({S.OCUPACION_REF_PCT:.0f}%), gana en {ref}.")
    if t["ocupacion_equilibrio_pct"].median() > S.OCUPACION_REF_PCT:
        rep("Para empatar al tradicional, el temporal necesita una ocupacion mayor que")
        rep("la que publica la prensa en la mediana de las celdas. El ingreso por noche")
        rep("es alto, pero expensas, servicios, plataforma y gestion se lo comen.")
    rep("El umbral de equilibrio es lo que el inversor tiene que contrastar con la")
    rep("ocupacion que espera lograr.")
    rep("")
    rep("Costos no cuantificados (sesgan a favor del temporal): internet, seguro,")
    rep("eventuales tasas, registros o impuestos propios de la actividad.")

    t.round(3).assign(fecha=datetime.now().strftime("%Y-%m-%d")).to_csv(
        SALIDA, index=False, encoding="utf-8-sig")
    rep("")
    rep(f"Archivo: {SALIDA} ({len(t)} filas)")
    with open(REPORTE, "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
