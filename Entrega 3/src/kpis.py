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

QUE CAMBIA EN LA 3RA ENTREGA
----------------------------
- El ABL deja de ser un porcentaje plano: se calcula por propiedad con la
  Ley Tarifaria (costos.py). Los gastos del KPI 2 pasan a ser de cada una.
- Costos de entrada y refaccion, y la TIR a 5 anios que los incluye
  (tir_5a_pct): la cifra comparable con la banda de retorno minimo.
- El reporte mide el ANTES (ABL plano, sin costos de entrada) y el DESPUES.

Uso:
    py src/kpis.py                          # ABL segmentado (supuestos.py)
    py src/kpis.py --vacancia 8 --gastos 12 # gastos planos, como la 1ra entrega

Salidas (en data/processed/):
    dataset_analitico.csv   LA matriz final: 12.097 filas con KPIs y variables
    ranking_barrios.csv     rentabilidad neta mediana por barrio
    modelo_alquiler.joblib  pipeline entrenado + smearing + error por segmento
    sensibilidad_supuestos.csv  KPI 2, TIR y ranking en las grillas de sensibilidad
    antes_despues_kpis.csv  neta mediana, barrios sobre el piso y top 5, antes y despues
    reporte_kpis.txt        log completo
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.model_selection import KFold, cross_val_predict

import costos as C
import eda
import modelo_alquiler as M
import supuestos as S


# Columnas que produce este script. Se listan para poder verificar de un
# vistazo que la matriz final las tenga todas y para documentar el contrato.
COLUMNAS_KPI = [
    "alquiler_est_usd_mes", "alquiler_est_m2", "n_alq_barrio",
    "estimacion_confiable", "rent_bruta_pct", "rent_neta_pct",
    "meses_repago", "alquiler_p10_usd_mes", "alquiler_p90_usd_mes",
    "rent_bruta_min", "rent_bruta_max",
    "abl_ars_mes", "abl_pct", "gastos_pct",
    "costos_entrada_pct", "refaccion_usd", "alquiler_post_refaccion_usd_mes", "tir_5a_pct",
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

    rep("KPI 4 — Banda de incertidumbre (percentiles 10 y 90 del alquiler, calibrados)")
    ancho = ok["rent_bruta_max"] - ok["rent_bruta_min"]
    rep(f"    ancho mediano de banda : {ancho.median():.2f} puntos porcentuales")
    rep("")
    rep("    Por tramo de superficie y por evidencia del barrio (cada propiedad tiene la suya):")
    seg = pd.cut(ok["sup_total_m2"], M.BINS_SUP, labels=M.LAB_SUP)
    for s, g in ancho.groupby(seg, observed=True):
        rep(f"        superficie {str(s):<8} n={len(g):>5}   banda mediana {g.median():>5.2f} pp")
    for s, g in ancho.groupby(M.grupo_evidencia(ok["n_alq_barrio"]).values):
        rep(f"        alquileres {s:<8} n={len(g):>5}   banda mediana {g.median():>5.2f} pp")
    rep("")

    # La pregunta que el KPI 4 existe para responder.
    n_solapan = int(((ok["rent_bruta_min"] <= b.median()) &
                     (ok["rent_bruta_max"] >= b.median())).sum())
    rep(f"    {n_solapan:,} propiedades ({n_solapan / len(ok) * 100:.1f}%) tienen una banda que")
    rep(f"    contiene la mediana del mercado: su diferencia contra el promedio")
    rep(f"    no se distingue del error de estimacion.")


# ==========================================================================
# ABL SEGMENTADO, COSTOS DE ENTRADA Y TIR
# ==========================================================================

def aplicar_abl(vta: pd.DataFrame, rep: M.Reporte) -> tuple[pd.DataFrame, float]:
    """Agrega el ABL de cada venta y devuelve la proporcion VFH / mercado calibrada."""
    rep.titulo("ABL SEGMENTADO (Ley Tarifaria 6927, arts. 41 a 45)")
    proporcion = C.calibrar_proporcion(vta)
    vta = vta.join(C.abl_por_propiedad(vta, proporcion))
    ref = C.es_referencia(vta)
    rep(f"Proporcion VFH / valor de mercado calibrada : {proporcion * 100:.2f}% "
        f"(tope legal {S.VFH_TOPE_SOBRE_MERCADO * 100:.0f}%, Codigo Fiscal art. 288)")
    rep(f"    con ella, la unidad de referencia ({int(ref.sum())} ventas de 2 amb y 40-60 m2) paga "
        f"{vta.loc[ref, 'abl_pct'].median():.2f}% del alquiler, el ABL_PCT plano")
    rep("")
    a = vta["abl_pct"]
    rep(f"ABL como % del alquiler: mediana {a.median():.2f}%   p10 {a.quantile(.1):.2f}%   "
        f"p90 {a.quantile(.9):.2f}%   (plano: {S.ABL_PCT:.2f}% para todas)")
    rep(f"ABL en pesos por mes   : mediana {vta['abl_ars_mes'].median():,.0f}   "
        f"p10 {vta['abl_ars_mes'].quantile(.1):,.0f}   p90 {vta['abl_ars_mes'].quantile(.9):,.0f}")
    rep("")
    rep("Por que se mueve: el ABL sigue al valor del inmueble y el alquiler no lo sigue")
    rep("igual (H1). Por quintil de rentabilidad bruta, en la base con estimacion confiable:")
    ok = vta[vta["estimacion_confiable"] == 1]
    q = pd.qcut(ok["alquiler_est_usd_mes"] * 12 / ok["venta_usd"], 5,
                labels=["Q1 (rinde menos)", "Q2", "Q3", "Q4", "Q5 (rinde mas)"])
    for k, g in ok.groupby(q, observed=True)["abl_pct"]:
        rep(f"    {k:<18} ABL mediano {g.median():>5.2f}% del alquiler")
    return vta, proporcion


def alquiler_post_refaccion(vta: pd.DataFrame, pipe, smear: float) -> pd.Series:
    """
    Alquiler que el modelo estima para las unidades a reciclar una vez
    refaccionadas: las mismas variables, con a_reciclar = 0 y reciclado = 1.
    Sin esto, la refaccion se cobraria sin su beneficio.
    """
    rec = vta["a_reciclar"] == 1
    X = vta.loc[rec, M.NUMERICAS + M.CATEGORICAS + M.DUMMIES].copy()
    X["a_reciclar"], X["reciclado"] = 0, 1
    post = pd.Series(np.nan, index=vta.index)
    if rec.any():
        post.loc[rec] = (np.exp(pipe.predict(X)) * smear).round(2)
    return post


def neta_escenario(vta: pd.DataFrame, vacancia: float, abl: str, abl_tope: pd.Series,
                   post: bool = False) -> pd.Series:
    """
    Rentabilidad neta de cada venta bajo una definicion del ABL:
      plano            el ABL_PCT de la 2da entrega para todas
      segmentado       el de cada propiedad, con la proporcion calibrada
      segmentado_tope  el de cada propiedad, con la VFH en el tope legal
    Con post=True, las unidades a reciclar cobran el alquiler post-refaccion.
    """
    alq = vta["alquiler_est_usd_mes"]
    if post:
        alq = vta["alquiler_post_refaccion_usd_mes"].fillna(alq)
    bruta = alq * 12 / vta["venta_usd"] * 100
    if abl == "plano":
        gastos = S.GASTOS_PCT
    else:
        ars = vta["abl_ars_mes"] if abl == "segmentado" else abl_tope
        gastos = S.GASTOS_SIN_ABL_PCT + ars / (alq * S.TC_ARS_USD) * 100
    return (bruta * (1 - vacancia / 100) * (1 - gastos / 100)).round(2)


def tir_escenario(vta: pd.DataFrame, vacancia: float, abl: str, entrada: str,
                  abl_tope: pd.Series) -> pd.Series:
    """TIR a 5 anios con los costos de entrada y la refaccion del escenario."""
    if entrada == "sin":
        return neta_escenario(vta, vacancia, abl, abl_tope)
    neta = neta_escenario(vta, vacancia, abl, abl_tope, post=True)
    inicial = (C.costos_entrada_pct(vta["venta_usd"], entrada)
               + C.refaccion_usd(vta, entrada) / vta["venta_usd"] * 100)
    return pd.Series(C.tir(neta, inicial), index=vta.index).round(2)


def costos_y_tir(vta: pd.DataFrame, vacancia: float, rep: M.Reporte) -> pd.DataFrame:
    """Costos de entrada, refaccion y TIR a 5 anios del escenario base."""
    rep.titulo(f"COSTOS DE ENTRADA, REFACCION Y TIR A {S.HORIZONTE_ANIOS} ANIOS")
    vta = vta.copy()
    vta["costos_entrada_pct"] = C.costos_entrada_pct(vta["venta_usd"], "base")
    vta["refaccion_usd"] = C.refaccion_usd(vta, "base")
    neta_post = (vta["alquiler_post_refaccion_usd_mes"].fillna(vta["alquiler_est_usd_mes"])
                 * 12 / vta["venta_usd"] * 100 * (1 - vacancia / 100)
                 * (1 - vta["gastos_pct_post"] / 100))
    inicial = vta["costos_entrada_pct"] + vta["refaccion_usd"] / vta["venta_usd"] * 100
    vta["tir_5a_pct"] = pd.Series(C.tir(neta_post.round(2), inicial), index=vta.index).round(2)

    ok = vta[vta["estimacion_confiable"] == 1]
    e = ok["costos_entrada_pct"]
    rep(f"Costos de entrada (escenario base, piso de cada rango): mediana {e.median():.2f}% del precio")
    rep(f"    comision {S.COMISION_COMPRADOR_PCT[0]}% + escribano {S.ESCRIBANO_PCT[0]}% + "
        f"registrales {S.REGISTRALES_PCT[0]}% + mitad de sellos "
        f"({S.SELLOS_ALICUOTA_REDUCIDA_PCT * S.SELLOS_PARTE_COMPRADOR:.2f}% hasta ARS "
        f"{S.SELLOS_UMBRAL_ARS / 1e6:,.1f}M, {S.SELLOS_ALICUOTA_PCT * S.SELLOS_PARTE_COMPRADOR:.2f}% arriba)")
    alto = C.costos_entrada_pct(ok["venta_usd"], "alto")
    rep(f"    escenario alto (techo de cada rango): mediana {alto.median():.2f}%")
    rep("")
    t = ok["tir_5a_pct"]
    rep(f"TIR a {S.HORIZONTE_ANIOS} anios (neta + costos de entrada + refaccion, reventa al mismo precio):")
    rep(f"    mediana {t.median():.2f}%   p25 {t.quantile(.25):.2f}%   p75 {t.quantile(.75):.2f}%")
    rep(f"    contra la neta mediana {ok['rent_neta_pct'].median():.2f}%: los costos de entrada restan "
        f"{ok['rent_neta_pct'].median() - t.median():.2f} pp por anio en el horizonte.")
    rep("")

    # Refaccion contra el descuento de H3. Si una unidad a reciclar cotiza un
    # d% mas barata por m2 que sus comparables, el descuento expresado sobre
    # SU precio es d / (1 - d). La refaccion la convierte en oportunidad solo
    # si cuesta menos que eso. El descuento se calcula como en el notebook 03
    # de la 2da entrega: dentro de cada celda barrio x tramo de superficie.
    t3 = eda.efecto_estratificado(vta[vta["venta_m2_usd"].notna()], "a_reciclar", "venta_m2_usd",
                                  ["barrio", "superficie_rango"], S.MIN_GRUPO_ESTRATO)
    d = -eda.mediana_ponderada(t3["diferencia"] / t3["mediana_0"], t3["peso"])
    umbral = d / (1 - d) * 100
    rec = ok[ok["a_reciclar"] == 1]
    rep(f"Unidades a reciclar en la base: {len(rec)}")
    rep(f"    descuento del m2 contra comparables de su celda barrio x superficie (H3): "
        f"{d * 100:.1f}% en {len(t3)} celdas;")
    rep(f"    sobre el precio de la unidad a reciclar equivale a {umbral:.1f}%")
    for esc in ("base", "alto"):
        r = C.refaccion_usd(rec, esc) / rec["venta_usd"] * 100
        rep(f"    refaccion {esc:<4}: mediana {r.median():5.1f}% del precio; "
            f"la cubre el descuento en {(r < umbral).mean() * 100:5.1f}% de las unidades")
    sube = (rec["alquiler_post_refaccion_usd_mes"] / rec["alquiler_est_usd_mes"] - 1) * 100
    rep(f"    alquiler estimado tras refaccionar: {sube.median():+.1f}% (mediana)")
    rep("")
    rep("No incluye: meses de obra sin alquiler, costos de salida ni riesgo legal")
    rep("(limitacion declarada en supuestos.py, seccion 3g).")
    return vta


def antes_y_despues(vta: pd.DataFrame, abl_tope: pd.Series, rep: M.Reporte) -> pd.DataFrame:
    """
    El entregable del ajuste: cuanto se mueven la neta mediana, los barrios que
    superan el piso y el ranking, del ABL plano al segmentado y de la neta a la
    TIR con costos de entrada.
    """
    rep.titulo("ANTES Y DESPUES")
    ok = vta[vta["estimacion_confiable"] == 1]
    en_ranking = ok.groupby("barrio")["venta_usd"].transform("size") >= S.MIN_VENTAS_BARRIO
    piso = S.RETORNO_MIN_PISO_PCT
    filas = {
        "antes: neta, ABL plano": neta_escenario(ok, S.VACANCIA_PCT, "plano", abl_tope),
        "neta, ABL segmentado": ok["rent_neta_pct"],
        "TIR 5a, ABL segm. + entrada": ok["tir_5a_pct"],
    }
    salida = []
    rep(f"Base: {len(ok):,} ventas con estimacion confiable; barrios con {S.MIN_VENTAS_BARRIO}+ ventas. "
        f"Piso de la banda: {piso:.2f}%")
    rep("")
    for nombre, s in filas.items():
        b = s[en_ranking].groupby(ok.loc[en_ranking, "barrio"]).median()
        orden = (b.rename("v").reset_index().sort_values(["v", "barrio"], ascending=[False, True]))
        sobre = list(orden.loc[orden["v"] >= piso, "barrio"])
        top5 = list(orden["barrio"][:5])
        rep(f"{nombre}")
        rep(f"    mediana {s.median():.2f}%   barrios sobre el piso: {len(sobre)} {sobre}")
        rep(f"    top 5: {', '.join(top5)}")
        salida.append({"escenario": nombre, "mediana_pct": round(float(s.median()), 2),
                       "barrios_sobre_piso": len(sobre), "barrios": "; ".join(sobre),
                       "top5": "; ".join(top5)})
    plano = filas["antes: neta, ABL plano"][en_ranking].groupby(ok.loc[en_ranking, "barrio"]).median()
    segm = ok.loc[en_ranking].groupby("barrio")["rent_neta_pct"].median()
    rep("")
    rep(f"Spearman del ranking de barrios, ABL plano contra segmentado: "
        f"{plano.corr(segm, method='spearman'):.4f}")
    mov = (segm.rank(ascending=False) - plano.rank(ascending=False)).sort_values()
    rep(f"Mayores subidas: {', '.join(f'{b} {-int(x):+d}' for b, x in mov.head(3).items())}")
    rep(f"Mayores bajadas: {', '.join(f'{b} {-int(x):+d}' for b, x in mov.tail(3).items())}")
    return pd.DataFrame(salida)


def sensibilidad(vta: pd.DataFrame, abl_tope: pd.Series, rank: pd.DataFrame,
                 rep: M.Reporte) -> pd.DataFrame:
    """
    Cuanto dependen los resultados de los supuestos y de las definiciones.

    Dos grillas:
      A. vacancia x gastos planos: la de la 2da entrega, con el ABL dentro de
         un porcentaje unico. Mueve el nivel, no el orden.
      B. vacancia x definicion del ABL x costos de entrada: con el ABL
         segmentado, el orden de los barrios ya puede cambiar; con costos de
         entrada, la metrica pasa a ser la TIR a 5 anios.
    Para cada escenario: mediana, propiedades y barrios sobre el piso de la
    banda, y cuanto se parece el ranking al materializado.
    """
    rep.titulo("SENSIBILIDAD A SUPUESTOS Y DEFINICIONES")
    ok = vta[vta["estimacion_confiable"] == 1]
    barrios = rank.index
    en = ok["barrio"].isin(barrios)
    base_barrio = ok[en].groupby("barrio")["rent_neta_pct"].median()
    top_base = list(base_barrio.rename("v").reset_index()
                    .sort_values(["v", "barrio"], ascending=[False, True])["barrio"][:5])
    piso = S.RETORNO_MIN_PISO_PCT

    def fila(serie: pd.Series, **campos) -> dict:
        b = serie[en].groupby(ok.loc[en, "barrio"]).median()
        top = list(b.rename("v").reset_index().sort_values(["v", "barrio"], ascending=[False, True])["barrio"][:5])
        return {**campos,
                "mediana": round(float(serie.median()), 2),
                "p25": round(float(serie.quantile(.25)), 2),
                "p75": round(float(serie.quantile(.75)), 2),
                "pct_prop_sobre_piso": round(float((serie >= piso).mean() * 100), 1),
                "barrios_sobre_piso": int((b >= piso).sum()),
                "spearman_ranking_vs_base": round(float(b.corr(base_barrio, method="spearman")), 4),
                "top5_igual": top == top_base}

    filas = []
    # A. La grilla de la 2da entrega: gastos planos.
    for vac in S.SENSIBILIDAD_VACANCIA:
        for gas in S.SENSIBILIDAD_GASTOS:
            neta = (ok["rent_bruta_pct"] * (1 - vac / 100) * (1 - gas / 100)).round(2)
            filas.append(fila(neta, grilla="A", vacancia_pct=vac, gastos_pct=gas,
                              abl="plano", entrada="sin", metrica="neta"))
    # B. Definicion del ABL y costos de entrada.
    for vac in S.SENSIBILIDAD_VACANCIA:
        for abl in S.SENSIBILIDAD_ABL:
            for ent in S.SENSIBILIDAD_ENTRADA:
                m = tir_escenario(ok, vac, abl, ent, abl_tope.loc[ok.index])
                filas.append(fila(m, grilla="B", vacancia_pct=vac, gastos_pct=np.nan,
                                  abl=abl, entrada=ent, metrica="neta" if ent == "sin" else "tir_5a"))
    t = pd.DataFrame(filas)

    rep(f"Base: {len(ok):,} ventas con estimacion confiable; {len(barrios)} barrios del ranking "
        f"({S.MIN_VENTAS_BARRIO}+ ventas). Piso: {piso:.2f}%. El ranking base es el materializado "
        f"(neta con ABL segmentado).")
    rep("")
    a = t[t["grilla"] == "A"]
    rep("A. Gastos planos (2da entrega): neta mediana (%)")
    m = a.pivot(index="vacancia_pct", columns="gastos_pct", values="mediana")
    rep("vacancia \\ gastos".ljust(18) + "".join(f"{g:>9.0f}%" for g in m.columns))
    for v, f in m.iterrows():
        rep(f"{v:>16.0f}% " + "".join(f"{x:>10.2f}" for x in f))
    rep("")
    b = t[t["grilla"] == "B"].copy()
    b["col"] = b["abl"] + " / " + b["entrada"]
    for valor, titulo in [("mediana", "neta (sin entrada) o TIR 5a (con entrada), mediana (%)"),
                          ("barrios_sobre_piso", f"barrios con mediana >= {piso:.2f}% (de {len(barrios)})"),
                          ("spearman_ranking_vs_base", "Spearman del ranking contra el base")]:
        rep(f"B. ABL x costos de entrada: {titulo}")
        p = b.pivot(index="vacancia_pct", columns="col", values=valor)
        p = p[[f"{x} / {y}" for x in S.SENSIBILIDAD_ABL for y in S.SENSIBILIDAD_ENTRADA]]
        rep("vacancia".ljust(10) + "".join(f"{c.replace('segmentado', 'segm'):>21}" for c in p.columns))
        for v, f in p.iterrows():
            rep(f"{v:>8.0f}% " + "".join(f"{x:>21.2f}" if valor != "barrios_sobre_piso" else f"{x:>21.0f}"
                                         for x in f))
        rep("")
    # La lectura se arma con las cifras de la grilla, para que no pueda
    # afirmar algo distinto de lo que muestran las tablas de arriba.
    sin = b[b["entrada"] == "sin"]
    seg = b[b["abl"] == "segmentado"]
    rep(f"Top 5 igual al base en {int(b['top5_igual'].sum())} de {len(b)} escenarios.")
    rep(f"Lectura: la mediana va de {b['mediana'].min():.2f}% a {b['mediana'].max():.2f}% en la grilla B, "
        f"y los barrios sobre el piso, de {int(b['barrios_sobre_piso'].min())} a "
        f"{int(b['barrios_sobre_piso'].max())}.")
    rep(f"    La definicion del ABL lleva el Spearman del ranking hasta "
        f"{sin['spearman_ranking_vs_base'].min():.4f}; los costos de entrada, hasta "
        f"{seg['spearman_ranking_vs_base'].min():.4f}.")
    return t


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/processed/dataset_espacial.csv")
    p.add_argument("--outdir", default="data/processed")
    p.add_argument("--vacancia", type=float, default=S.VACANCIA_PCT)
    # Sin --gastos, el ABL se calcula por propiedad (costos.py). Con --gastos,
    # un porcentaje plano para todas, como en la 1ra y la 2da entrega.
    p.add_argument("--gastos", type=float, default=None)
    args = p.parse_args()

    if not os.path.exists(args.input):
        print(f"No existe {args.input}")
        print("Corré primero:  py src/limpieza.py --tc 1500  &&  py src/variables.py  &&  py src/espacial.py")
        return 1

    vigentes = args.vacancia == S.VACANCIA_PCT and args.gastos is None
    rep = M.Reporte()
    rep.titulo("MATERIALIZACION DE KPIs")
    rep(f"Fecha   : {datetime.now():%Y-%m-%d %H:%M}")
    rep(f"Entrada : {args.input}")
    if vigentes:
        rep(f"Supuestos: vacancia {args.vacancia:.2f}%, gastos {S.GASTOS_SIN_ABL_PCT:.2f}% + ABL de cada propiedad")
        rep("")
        rep(S.tabla())
    else:
        gastos_txt = f"{args.gastos:.2f}% planos" if args.gastos is not None else "con ABL segmentado"
        rep(f"Supuestos: vacancia {args.vacancia:.2f}%, gastos {gastos_txt}")
        rep("    (valores pasados por linea de comandos, no los de supuestos.py)")

    df = M.preparar(pd.read_csv(args.input, encoding="utf-8-sig", low_memory=False))

    alq = df[df["operacion"] == "alquiler"].dropna(
        subset=["alquiler_usd_mes", "sup_total_m2", "barrio"])
    vta = df[df["operacion"] == "venta"].dropna(
        subset=["venta_usd", "sup_total_m2", "barrio"])

    rep(f"Alquileres para entrenar : {len(alq):,}")
    rep(f"Ventas a estimar         : {len(vta):,}")

    pipe, smear, metricas = M.entrenar_y_validar(alq, rep)
    M.reportar_coeficientes(pipe, rep)
    comparar_dummies(alq, rep)

    cobertura = alq.groupby("barrio").size()
    vta = M.imputar(vta, pipe, smear, cobertura, rep)
    banda, info_banda = M.banda_cuantilica(alq, vta, rep)
    vta = vta.join(banda)
    vta["alquiler_post_refaccion_usd_mes"] = alquiler_post_refaccion(vta, pipe, smear)

    vta, proporcion = aplicar_abl(vta, rep)
    abl_tope = C.abl_por_propiedad(vta, S.VFH_TOPE_SOBRE_MERCADO)["abl_ars_mes"]
    if args.gastos is None:
        gastos = (S.GASTOS_SIN_ABL_PCT + vta["abl_pct"]).round(2)
        alq_post = vta["alquiler_post_refaccion_usd_mes"].fillna(vta["alquiler_est_usd_mes"])
        vta["gastos_pct_post"] = S.GASTOS_SIN_ABL_PCT + vta["abl_ars_mes"] / (alq_post * S.TC_ARS_USD) * 100
    else:
        gastos = args.gastos
        vta["gastos_pct_post"] = args.gastos
    vta["gastos_pct"] = gastos
    vta = M.calcular_rentabilidad(vta, args.vacancia, gastos, rep)
    vta = costos_y_tir(vta, args.vacancia, rep)
    rank = M.ranking_barrios(vta, rep)

    out = materializar(df, vta, rep)
    resumen_kpis(out, rep)
    ad = antes_y_despues(vta, abl_tope, rep)
    sens = sensibilidad(vta, abl_tope, rank, rep)

    os.makedirs(args.outdir, exist_ok=True)
    p1 = os.path.join(args.outdir, "dataset_analitico.csv")
    p2 = os.path.join(args.outdir, "ranking_barrios.csv")
    p3 = os.path.join(args.outdir, "modelo_alquiler.joblib")
    p4 = os.path.join(args.outdir, "reporte_kpis.txt")
    p5 = os.path.join(args.outdir, "sensibilidad_supuestos.csv")
    p6 = os.path.join(args.outdir, "antes_despues_kpis.csv")

    out.to_csv(p1, index=False, encoding="utf-8-sig")
    rank.to_csv(p2, encoding="utf-8-sig")
    sens.to_csv(p5, index=False, encoding="utf-8-sig")
    ad.to_csv(p6, index=False, encoding="utf-8-sig")
    # Metadata del modelo: con que se entreno, cuando, sobre que datos y
    # cuanto rinde fuera de muestra. El hash permite comprobar que el .joblib
    # corresponde a este dataset y no a una corrida vieja.
    columnas = M.NUMERICAS + M.CATEGORICAS + M.DUMMIES
    entrenamiento = alq[columnas + ["alquiler_usd_mes"]].to_csv(index=False).encode("utf-8")
    joblib.dump({
        "pipeline": pipe,
        "smearing": smear,
        "banda": info_banda,
        "metadata": {
            "sklearn": sklearn.__version__,
            "entrenado": datetime.now().isoformat(timespec="seconds"),
            "entrada": args.input,
            "hash_entrenamiento_sha256": hashlib.sha256(entrenamiento).hexdigest(),
            "n_entrenamiento": len(alq),
            "predictoras": {"numericas": M.NUMERICAS, "categoricas": M.CATEGORICAS,
                            "dummies": M.DUMMIES},
            "metricas_validacion": metricas,
            "cobertura_banda": {"objetivo": M.COBERTURA_OBJETIVO,
                                "cruda": info_banda["cobertura_cruda"],
                                "calibrada": info_banda["cobertura_calibrada"]},
        },
        "vacancia": args.vacancia,
        # None cuando el ABL es segmentado: los gastos son de cada propiedad y
        # estan en la columna gastos_pct del dataset.
        "gastos": args.gastos,
        "gastos_sin_abl": S.GASTOS_SIN_ABL_PCT if args.gastos is None else None,
        "abl": "segmentado" if args.gastos is None else "plano",
        "proporcion_vfh": proporcion,
        "columnas": columnas,
    }, p3)

    rep("")
    rep("Archivos generados:")
    rep(f"    {p1}    ({len(out):,} filas x {out.shape[1]} columnas)")
    for p_ in (p2, p3, p5, p6, p4):
        rep(f"    {p_}")
    rep.guardar(p4)
    return 0


if __name__ == "__main__":
    sys.exit(main())


