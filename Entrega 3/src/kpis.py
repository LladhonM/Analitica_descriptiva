#!/usr/bin/env python
"""
kpis.py — Materializa los cuatro KPIs de la 1ra entrega como columnas.

QUE SIGNIFICA "MATERIALIZAR"
----------------------------
En la 1ra entrega los KPIs eran definiciones en el informe. Aca dejan de ser
formulas escritas y pasan a ser columnas del dataset, una por propiedad:

  KPI 1  rent_bruta_pct    (alquiler estimado x 12) / precio de venta x 100
  KPI 2  rent_neta_pct     bruta x (1 - vacancia) x (1 - gastos)
  KPI 3  meses_repago      precio de venta / alquiler estimado
  KPI 4  rent_bruta_min    banda de incertidumbre: bruta x (1 +- error del
         rent_bruta_max    segmento de superficie al que pertenece la unidad)

EL RODEO NECESARIO
------------------
Ninguno de los cuatro se puede calcular directamente: hay 8 propiedades en
venta por cada una en alquiler, y una propiedad publicada en venta no tiene
precio de alquiler observado. El alquiler se estima con el modelo Ridge sobre
log(alquiler) de la 1ra entrega, que se importa entero desde `modelo_alquiler`
en vez de reimplementarse.

QUE LE APORTO LA 2DA ENTREGA AL MODELO
--------------------------------------
Las 14 dummies que el modelo usa como predictoras ahora vienen del motor RegEx
de `variables.py` y no de la busqueda por subcadena. Este script mide si esa
correccion mejora la estimacion, entrenando las dos versiones sobre los mismos
folds. Si limpiar las variables no cambiara nada, convendria saberlo.

Uso:
    py src/kpis.py
    py src/kpis.py --vacancia 10 --gastos 15

Salidas (en data/processed/):
    dataset_analitico.csv   LA matriz final: 12.097 filas con KPIs y variables
    ranking_barrios.csv     rentabilidad mediana por barrio
    modelo_alquiler.joblib  pipeline entrenado + smearing + error por segmento
    sensibilidad_supuestos.csv  KPI 2 y ranking en la grilla de vacancia x gastos
    reporte_kpis.txt        log completo
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_val_predict

import modelo_alquiler as M
import supuestos as S


# Columnas que produce este script. Se listan para poder verificar de un
# vistazo que la matriz final las tenga todas y para documentar el contrato.
COLUMNAS_KPI = [
    "alquiler_est_usd_mes", "alquiler_est_m2", "n_alq_barrio",
    "estimacion_confiable", "rent_bruta_pct", "rent_neta_pct",
    "meses_repago", "error_estimacion", "rent_bruta_min", "rent_bruta_max",
]


def comparar_dummies(alq: pd.DataFrame, rep: M.Reporte) -> None:
    """
    Mide si las dummies corregidas por RegEx mejoran el modelo de alquiler.

    Entrena dos veces sobre los MISMOS folds: una con las dummies tal como
    quedaron despues de `variables.py` y otra con las dummies barajadas al
    azar. La comparacion contra el azar responde la pregunta que importa —
    si estas variables aportan senal o solo dimensiones— sin necesidad de
    reconstruir la version vieja del dataset, que ya no existe en disco.
    """
    rep.titulo("CONTROL: LAS DUMMIES DE REGEX, CONTRA RUIDO")

    X = alq[M.NUMERICAS + M.CATEGORICAS + M.DUMMIES]
    y = np.log(alq["alquiler_usd_mes"])
    kf = KFold(5, shuffle=True, random_state=42)

    def r2(Xd: pd.DataFrame) -> float:
        pred = cross_val_predict(M.construir_pipeline(), Xd, y, cv=kf)
        return 1 - float(((y - pred) ** 2).sum()) / float(((y - y.mean()) ** 2).sum())

    r2_real = r2(X)

    # Mismas columnas, mismas prevalencias, valores mezclados entre filas: se
    # destruye la relacion con el precio pero se conserva la dimensionalidad.
    # Si el R2 no bajara, las dummies estarian aportando solo grados de
    # libertad y el modelo estaria inflado.
    X_ruido = X.copy()
    rng = np.random.default_rng(42)
    for c in M.DUMMIES:
        X_ruido[c] = rng.permutation(X_ruido[c].values)
    r2_ruido = r2(X_ruido)

    # Sin las dummies: cuanto del R2 depende efectivamente del texto.
    r2_sin = r2(X.drop(columns=M.DUMMIES).assign(**{c: 0 for c in M.DUMMIES}))

    rep(f"{'configuracion':<44}{'R2 fuera de muestra':>20}")
    rep("-" * 64)
    rep(f"{'dummies de RegEx (las que se usan)':<44}{r2_real:>20.4f}")
    rep(f"{'mismas dummies con los valores permutados':<44}{r2_ruido:>20.4f}")
    rep(f"{'sin dummies (todas en cero)':<44}{r2_sin:>20.4f}")
    rep("")
    rep(f"Aporte real de las variables de texto : {r2_real - r2_sin:+.4f} de R2")
    rep(f"Aporte de las mismas columnas al azar : {r2_ruido - r2_sin:+.4f} de R2")
    rep("")
    if r2_real - r2_sin > 2 * abs(r2_ruido - r2_sin):
        rep("Lectura: el aporte de las dummies es varias veces mayor que el de")
        rep("las mismas columnas sin informacion. La mejora viene del contenido")
        rep("del texto, no de haber agregado columnas.")
    else:
        rep("Lectura: el aporte de las dummies no se despega del que dan las")
        rep("mismas columnas al azar. Conviene revisarlas antes de confiar en ellas.")


def materializar(df: pd.DataFrame, vta: pd.DataFrame, rep: M.Reporte) -> pd.DataFrame:
    """
    Devuelve el dataset COMPLETO con las columnas de KPI incorporadas.

    La decision de fondo: el entregable es una sola matriz con las 12.097
    filas, no un archivo de ventas y otro de alquileres. Los KPIs quedan
    vacios en las filas de alquiler, y eso es correcto —un inmueble publicado
    en alquiler no tiene precio de venta, asi que su rentabilidad no esta
    definida—. Partir el dataset obligaria a re-unirlo para cualquier
    comparacion entre los dos mercados, que es justamente lo que el EDA hace.
    """
    rep.titulo("MATERIALIZACION DE LOS KPIs SOBRE LA MATRIZ COMPLETA")

    kpi = vta[COLUMNAS_KPI]
    out = df.join(kpi, how="left")

    n_con = int(out["rent_bruta_pct"].notna().sum())
    rep(f"Filas totales                  : {len(out):,}")
    rep(f"Filas con KPI calculado        : {n_con:,} "
        f"({n_con / len(out) * 100:.1f}%)")
    rep(f"Filas sin KPI                  : {len(out) - n_con:,}")
    rep("")
    rep("Por que quedan filas sin KPI:")
    sin = out[out["rent_bruta_pct"].isna()]
    rep(f"    publicadas en alquiler (no tienen precio de venta) : "
        f"{int((sin['operacion'] == 'alquiler').sum()):,}")
    rep(f"    en venta pero sin superficie o barrio utilizable   : "
        f"{int((sin['operacion'] == 'venta').sum()):,}")
    rep("")
    rep("No se imputan: una rentabilidad inventada para una propiedad en")
    rep("alquiler no significa nada. El nulo es la respuesta correcta.")

    rep("")
    rep("Columnas de KPI incorporadas:")
    for c in COLUMNAS_KPI:
        s = out[c]
        if s.notna().sum() == 0:
            rep(f"    {c:<24} VACIA — revisar")
            continue
        rep(f"    {c:<24} mediana {s.median():>10,.2f}   "
            f"p5 {s.quantile(.05):>9,.2f}   p95 {s.quantile(.95):>9,.2f}")
    return out


def resumen_kpis(out: pd.DataFrame, rep: M.Reporte) -> None:
    """Lectura de negocio de los cuatro KPIs, en las unidades del inversor."""
    rep.titulo("LOS CUATRO KPIs, LEIDOS")

    ok = out[(out["estimacion_confiable"] == 1) & out["rent_bruta_pct"].notna()]
    rep(f"Base: {len(ok):,} propiedades en venta con estimacion confiable")
    rep("")

    b = ok["rent_bruta_pct"]
    rep("KPI 1 — Rentabilidad bruta anual")
    rep(f"    mediana {b.median():.2f}%   |   p25 {b.quantile(.25):.2f}%   "
        f"p75 {b.quantile(.75):.2f}%   |   rango p5-p95 "
        f"{b.quantile(.05):.2f}% a {b.quantile(.95):.2f}%")
    rep(f"    Cribado: por debajo de {b.quantile(.25):.2f}% la unidad rinde menos")
    rep(f"    que tres cuartos de la oferta comparable.")
    rep("")

    n = ok["rent_neta_pct"]
    rep("KPI 2 — Rentabilidad neta anual")
    rep(f"    mediana {n.median():.2f}%   |   p25 {n.quantile(.25):.2f}%   "
        f"p75 {n.quantile(.75):.2f}%")
    rep(f"    La vacancia y los gastos se llevan "
        f"{(1 - n.median() / b.median()) * 100:.1f}% del rendimiento bruto.")
    rep("")

    m = ok["meses_repago"]
    rep("KPI 3 — Meses de repago")
    rep(f"    mediana {m.median():,.0f} meses ({m.median() / 12:.1f} años)   |   "
        f"p25 {m.quantile(.25):,.0f}   p75 {m.quantile(.75):,.0f}")
    sospechosas = int((m < 120).sum())
    rep(f"    Control de sanidad: {sospechosas:,} unidades repagan en menos de 10 años "
        f"({sospechosas / len(ok) * 100:.1f}%).")
    rep(f"    En este mercado eso es inusual y amerita revisar el aviso.")
    rep("")

    rep("KPI 4 — Banda de incertidumbre")
    rep(f"    error mediano aplicado : {ok['error_estimacion'].median() * 100:.1f}%")
    rep(f"    ancho mediano de banda : "
        f"{(ok['rent_bruta_max'] - ok['rent_bruta_min']).median():.2f} puntos porcentuales")
    rep("")
    rep("    Error por tramo de superficie (por que la banda no es unica):")
    seg = pd.cut(ok["sup_total_m2"], M.BINS_SUP, labels=M.LAB_SUP)
    for s, g in ok.groupby(seg, observed=True):
        rep(f"        {str(s):<8} n={len(g):>5}   error {g['error_estimacion'].median() * 100:>5.1f}%   "
            f"banda mediana {(g['rent_bruta_max'] - g['rent_bruta_min']).median():>5.2f} pp")
    rep("")

    # La pregunta que el KPI 4 existe para responder.
    n_solapan = int(((ok["rent_bruta_min"] <= b.median()) &
                     (ok["rent_bruta_max"] >= b.median())).sum())
    rep(f"    {n_solapan:,} propiedades ({n_solapan / len(ok) * 100:.1f}%) tienen una banda que")
    rep(f"    contiene la mediana del mercado: su diferencia contra el promedio")
    rep(f"    no se distingue del error de estimacion.")


def sensibilidad(out: pd.DataFrame, rank: pd.DataFrame, rep: M.Reporte) -> pd.DataFrame:
    """
    Cuanto dependen los resultados de la vacancia y los gastos.

    Recorre la grilla de supuestos.py y, para cada par, recalcula la neta de
    cada propiedad desde la bruta. Reporta tres cosas: el nivel (mediana
    neta), el ranking de barrios y cuantas propiedades y barrios superan el
    piso del retorno minimo.

    El ranking no puede moverse, y se calcula igual para mostrarlo en vez de
    afirmarlo: vacancia y gastos entran como un factor unico para todas las
    propiedades, y multiplicar todo por la misma constante no cambia ningun
    orden. Lo que si depende de los supuestos es el nivel, y con el nivel,
    cuantas unidades cruzan el umbral contra el que se las compara.
    """
    rep.titulo("SENSIBILIDAD A LOS SUPUESTOS DE VACANCIA Y GASTOS")

    ok = out[(out["estimacion_confiable"] == 1) & out["rent_bruta_pct"].notna()]
    barrios = rank.index
    base_barrio = ok[ok["barrio"].isin(barrios)].groupby("barrio")["rent_bruta_pct"].median()
    piso = S.RETORNO_MIN_PISO_PCT
    top_base = list(base_barrio.sort_values(ascending=False).index[:5])

    filas = []
    for vac in S.SENSIBILIDAD_VACANCIA:
        for gas in S.SENSIBILIDAD_GASTOS:
            f = (1 - vac / 100) * (1 - gas / 100)
            # Mismo redondeo que la columna materializada: si no, un escenario
            # identico al vigente daria una proporcion distinta a la del dataset.
            neta = (ok["rent_bruta_pct"] * f).round(2)
            neta_barrio = base_barrio * f
            filas.append({
                "vacancia_pct": vac,
                "gastos_pct": gas,
                "factor_neto": round(f, 4),
                "neta_mediana": round(float(neta.median()), 2),
                "neta_p25": round(float(neta.quantile(.25)), 2),
                "neta_p75": round(float(neta.quantile(.75)), 2),
                "pct_prop_sobre_piso": round(float((neta >= piso).mean() * 100), 1),
                "barrios_sobre_piso": int((neta_barrio >= piso).sum()),
                "spearman_ranking_vs_base": round(float(
                    neta_barrio.corr(base_barrio, method="spearman")), 4),
                "top5_igual": list(neta_barrio.sort_values(ascending=False).index[:5]) == top_base,
            })
    t = pd.DataFrame(filas)

    def matriz(col: str, fmt: str) -> None:
        m = t.pivot(index="vacancia_pct", columns="gastos_pct", values=col)
        rep("vacancia \\ gastos".ljust(18) + "".join(f"{g:>9.0f}%" for g in m.columns))
        for v, fila in m.iterrows():
            rep(f"{v:>16.0f}% " + "".join(f"{x:>10{fmt}}" for x in fila))

    rep(f"Base: {len(ok):,} ventas con estimacion confiable; "
        f"{len(barrios)} barrios del ranking ({S.MIN_VENTAS_BARRIO}+ ventas)")
    rep(f"Piso del retorno minimo: {piso:.2f}% (supuestos.RETORNO_MIN_PISO_PCT)")
    rep("")
    rep("Rentabilidad neta mediana (%):")
    matriz("neta_mediana", ".2f")
    rep("")
    rep(f"Propiedades con neta >= {piso:.2f}% (% de la base):")
    matriz("pct_prop_sobre_piso", ".1f")
    rep("")
    rep(f"Barrios con neta mediana >= {piso:.2f}% (de {len(barrios)}):")
    matriz("barrios_sobre_piso", ".0f")
    rep("")

    # El escenario vigente (5,88 / 14,04) no cae sobre la grilla redonda:
    # se reporta aparte para poder ubicarlo entre las celdas.
    f0 = (1 - S.VACANCIA_PCT / 100) * (1 - S.GASTOS_PCT / 100)
    neta0 = (ok["rent_bruta_pct"] * f0).round(2)
    rep(f"Escenario de supuestos.py (vacancia {S.VACANCIA_PCT:.2f}%, gastos {S.GASTOS_PCT:.2f}%): "
        f"neta mediana {neta0.median():.2f}%, "
        f"{(neta0 >= piso).mean() * 100:.1f}% de las propiedades y "
        f"{int(((base_barrio * f0) >= piso).sum())} barrios sobre el piso.")
    rep("")

    ext = t.iloc[[0, -1]]
    rep(f"Del escenario mas favorable al mas adverso de la grilla, la neta mediana va de "
        f"{ext['neta_mediana'].iloc[0]:.2f}% a {ext['neta_mediana'].iloc[1]:.2f}% "
        f"({ext['neta_mediana'].iloc[0] - ext['neta_mediana'].iloc[1]:.2f} pp).")
    rep(f"Spearman minimo del ranking contra el base: {t['spearman_ranking_vs_base'].min():.4f}; "
        f"top 5 identico en {int(t['top5_igual'].sum())} de {len(t)} escenarios.")
    rep("Lectura: los supuestos mueven el NIVEL de la rentabilidad y, con el,")
    rep("cuantas unidades superan el retorno minimo; no mueven QUE barrio rinde")
    rep("mas. El ranking es robusto a estos supuestos porque se aplican iguales")
    rep("a todos. Dejaria de serlo con una vacancia distinta por barrio, que")
    rep("este trabajo no mide.")
    return t


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/processed/dataset_variables.csv")
    p.add_argument("--outdir", default="data/processed")
    # Los defaults salen de supuestos.py y no de las constantes del modelo:
    # ahi estan con fuente y desagregados. El modelo sigue recibiendo un solo
    # numero de gastos, que es la suma de los cuatro componentes.
    p.add_argument("--vacancia", type=float, default=S.VACANCIA_PCT)
    p.add_argument("--gastos", type=float, default=S.GASTOS_PCT)
    args = p.parse_args()

    if not os.path.exists(args.input):
        print(f"No existe {args.input}")
        print("Corré primero:  py src/limpieza.py  &&  py src/variables.py")
        return 1

    rep = M.Reporte()
    rep.titulo("MATERIALIZACION DE KPIs")
    rep(f"Fecha   : {datetime.now():%Y-%m-%d %H:%M}")
    rep(f"Entrada : {args.input}")
    rep(f"Supuestos: vacancia {args.vacancia:.2f}%, gastos {args.gastos:.2f}%")
    # Si se pasaron por linea de comandos, la desagregacion de supuestos.py ya
    # no describe lo que se esta usando y mostrarla confundiria.
    if (args.vacancia, args.gastos) == (S.VACANCIA_PCT, S.GASTOS_PCT):
        rep("")
        rep(S.tabla())
    else:
        rep("    (valores pasados por linea de comandos, no los de supuestos.py)")

    df = M.preparar(pd.read_csv(args.input, encoding="utf-8-sig", low_memory=False))

    alq = df[df["operacion"] == "alquiler"].dropna(
        subset=["alquiler_usd_mes", "sup_total_m2", "barrio"])
    vta = df[df["operacion"] == "venta"].dropna(
        subset=["venta_usd", "sup_total_m2", "barrio"])

    rep(f"Alquileres para entrenar : {len(alq):,}")
    rep(f"Ventas a estimar         : {len(vta):,}")

    pipe, smear, err_seg = M.entrenar_y_validar(alq, rep)
    M.reportar_coeficientes(pipe, rep)
    comparar_dummies(alq, rep)

    cobertura = alq.groupby("barrio").size()
    vta = M.imputar(vta, pipe, smear, cobertura, rep)
    vta = M.calcular_rentabilidad(vta, args.vacancia, args.gastos, err_seg, rep)
    rank = M.ranking_barrios(vta, rep)

    out = materializar(df, vta, rep)
    resumen_kpis(out, rep)
    sens = sensibilidad(out, rank, rep)

    os.makedirs(args.outdir, exist_ok=True)
    p1 = os.path.join(args.outdir, "dataset_analitico.csv")
    p2 = os.path.join(args.outdir, "ranking_barrios.csv")
    p3 = os.path.join(args.outdir, "modelo_alquiler.joblib")
    p4 = os.path.join(args.outdir, "reporte_kpis.txt")
    p5 = os.path.join(args.outdir, "sensibilidad_supuestos.csv")

    out.to_csv(p1, index=False, encoding="utf-8-sig")
    rank.to_csv(p2, encoding="utf-8-sig")
    sens.to_csv(p5, index=False, encoding="utf-8-sig")
    joblib.dump({
        "pipeline": pipe,
        "smearing": smear,
        "error_por_segmento": err_seg,
        "vacancia": args.vacancia,
        "gastos": args.gastos,
        # Solo si el total usado es el de supuestos.py: con --gastos manual
        # los componentes no suman lo que se aplico.
        "gastos_componentes": (S.GASTOS_COMPONENTES
                               if args.gastos == S.GASTOS_PCT else None),
        "columnas": M.NUMERICAS + M.CATEGORICAS + M.DUMMIES,
    }, p3)

    rep("")
    rep("Archivos generados:")
    rep(f"    {p1}    ({len(out):,} filas x {out.shape[1]} columnas)")
    rep(f"    {p2}")
    rep(f"    {p3}")
    rep(f"    {p5}")
    rep(f"    {p4}")
    rep.guardar(p4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
