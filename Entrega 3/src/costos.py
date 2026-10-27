"""
costos.py — Los costos del propietario que dependen de cada propiedad: el ABL
segmentado, los costos de entrada, la refaccion de las unidades a reciclar y
la tasa interna de retorno a 5 anios que los junta.

Los numeros (alicuotas, tramos, coeficientes, rangos de costos) estan en
supuestos.py con su fuente. Aca solo estan las formulas.

ABL SEGMENTADO
--------------
El ABL de CABA es un tributo sobre la Valuacion Fiscal Homogenea (VFH), no un
porcentaje del alquiler (Ley 6927, arts. 41 a 45). Para cada venta:

  1. VFH = proporcion x m2 de mercado mediano de su barrio y tipo x superficie
  2. ABL anual = Impuesto Inmobiliario (progresivo) + Tasa (con el
     coeficiente geografico del barrio), con recargo, minimo y tope
  3. abl_pct = ABL mensual / alquiler estimado, en el mismo tipo de cambio

La proporcion VFH / mercado no se publica: se calibra para que la unidad de
referencia pague el ABL_PCT de supuestos.py (ver calibrar_proporcion).

TIR A 5 ANIOS
-------------
La tasa anual que iguala lo que se pone al comprar (precio + costos de
entrada + refaccion) con lo que se recibe: el alquiler neto de cada anio
durante el horizonte y, al final, la reventa al mismo precio en dolares. Es
comparable con la TIR de una ON al mismo plazo, que es la vara de la banda de
retorno minimo. Sin costos de entrada, la TIR es igual a la neta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import supuestos as S


# ==========================================================================
# ABL SEGMENTADO
# ==========================================================================

def coef_geografico(barrio: pd.Series) -> pd.Series:
    """Coeficiente geografico de la Ley 6927, art. 42: promedio de las subzonas del barrio."""
    cg = {b: float(np.mean(v)) for b, v in S.ABL_COEF_GEOGRAFICO.items()}
    return barrio.map(cg)


def impuesto_inmobiliario(vfh: np.ndarray) -> np.ndarray:
    """Ley 6927, art. 41: cuota fija del tramo + alicuota sobre el excedente."""
    vfh = np.asarray(vfh, dtype=float)
    desde = np.array([t[0] for t in S.INMOBILIARIO_TRAMOS], dtype=float)
    i = np.clip(np.searchsorted(desde, vfh, side="right") - 1, 0, len(desde) - 1)
    cf = np.array([t[1] for t in S.INMOBILIARIO_TRAMOS], dtype=float)[i]
    al = np.array([t[2] for t in S.INMOBILIARIO_TRAMOS])[i]
    return (cf + (vfh - desde[i]) * al) * S.ABL_USC


def abl_anual_ars(vfh, cg, valor_mercado_ars) -> np.ndarray:
    """
    Impuesto Inmobiliario + Tasa ABL de un anio, en pesos (Ley 6927, arts. 41-45).

    No modela la bonificacion del art. 44, que limita la suba de cada cuota
    contra la cuota anterior: hace falta la boleta del anio previo. La boleta
    real puede ser menor que esta.
    """
    vfh = np.asarray(vfh, dtype=float)
    tasa = vfh * S.ABL_ALICUOTA_BASE * (1 + np.asarray(cg, dtype=float) * S.ABL_PONDERACION_CG) * S.ABL_USC
    tasa = np.where(vfh > S.ABL_UMBRAL_RECARGO_VFH, tasa * (1 + S.ABL_RECARGO), tasa)
    total = np.maximum(impuesto_inmobiliario(vfh) + tasa, S.ABL_MINIMO_ANUAL_ARS)
    return np.minimum(total, np.asarray(valor_mercado_ars, dtype=float) * S.ABL_TOPE_SOBRE_MERCADO)


def m2_de_mercado(ventas: pd.DataFrame) -> pd.Series:
    """
    USD/m2 mediano de la celda barrio x tipo de cada venta: el "valor de
    mercado por m2 de la zona" del que parte la VFH (Codigo Fiscal, art. 288).
    Si la celda tiene menos de MIN_AVISOS_CELDA ventas, el del barrio.
    """
    g = ventas.groupby(["barrio", "tipo_familia"])["venta_m2_usd"]
    celda = g.transform("median").where(g.transform("count") >= S.MIN_AVISOS_CELDA)
    return celda.fillna(ventas.groupby("barrio")["venta_m2_usd"].transform("median"))


def abl_por_propiedad(vta: pd.DataFrame, proporcion: float) -> pd.DataFrame:
    """
    ABL de cada venta, en pesos por mes y como % del alquiler estimado.

    `vta` necesita barrio, tipo_familia, venta_m2_usd, sup_total_m2, venta_usd
    y alquiler_est_usd_mes.
    """
    vfh = proporcion * m2_de_mercado(vta) * vta["sup_total_m2"] * S.TC_ARS_USD
    anual = abl_anual_ars(vfh, coef_geografico(vta["barrio"]), vta["venta_usd"] * S.TC_ARS_USD)
    mes = pd.Series(anual / 12, index=vta.index)
    pct = mes / (vta["alquiler_est_usd_mes"] * S.TC_ARS_USD) * 100
    return pd.DataFrame({"abl_ars_mes": mes.round(0), "abl_pct": pct.round(2)})


def es_referencia(vta: pd.DataFrame) -> pd.Series:
    """La unidad de referencia del ABL plano: 2 ambientes de 40 a 60 m2."""
    return (vta["ambientes"] == 2) & vta["sup_total_m2"].between(40, 60)


def calibrar_proporcion(vta: pd.DataFrame) -> float:
    """
    Proporcion VFH / mercado con la que la unidad de referencia mediana paga
    el ABL_PCT de supuestos.py. Biseccion: el ABL crece con la VFH.

    Calibrar asi aisla el efecto de la segmentacion: cambia QUIEN paga mas,
    no CUANTO se paga en la unidad de referencia.

    El ABL se calcula sobre todas las ventas y recien despues se toma la
    mediana de la referencia: el m2 de mercado de cada celda tiene que salir
    de todas las ventas, no solo de las de 2 ambientes.
    """
    ref = es_referencia(vta)

    def mediana_ref(proporcion: float) -> float:
        return abl_por_propiedad(vta, proporcion).loc[ref, "abl_pct"].median()

    lo, hi = 0.001, S.VFH_TOPE_SOBRE_MERCADO
    if mediana_ref(hi) < S.ABL_PCT:
        return hi
    for _ in range(40):
        mid = (lo + hi) / 2
        if mediana_ref(mid) < S.ABL_PCT:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ==========================================================================
# COSTOS DE ENTRADA Y REFACCION
# ==========================================================================

def _nivel(rango: tuple, escenario: str) -> float:
    return {"sin": 0.0, "base": rango[0], "alto": rango[1]}[escenario]


def costos_entrada_pct(venta_usd: pd.Series, escenario: str = "base") -> pd.Series:
    """
    Costos de entrada del comprador como % del precio: comision, escribano,
    registrales y su mitad del Impuesto de Sellos. `escenario`: sin, base, alto.
    """
    if escenario == "sin":
        return pd.Series(0.0, index=venta_usd.index)
    sellos = np.where(venta_usd * S.TC_ARS_USD <= S.SELLOS_UMBRAL_ARS,
                      S.SELLOS_ALICUOTA_REDUCIDA_PCT, S.SELLOS_ALICUOTA_PCT) * S.SELLOS_PARTE_COMPRADOR
    fijos = (_nivel(S.COMISION_COMPRADOR_PCT, escenario) + _nivel(S.ESCRIBANO_PCT, escenario)
             + _nivel(S.REGISTRALES_PCT, escenario))
    return pd.Series(fijos + sellos, index=venta_usd.index).round(2)


def refaccion_usd(vta: pd.DataFrame, escenario: str = "base") -> pd.Series:
    """
    Costo de refaccion en USD; 0 si la unidad no es a reciclar.

    base: un bano por cada bano de la unidad, una cocina y pintura por m2.
    alto: refaccion integral por m2, con IVA.
    """
    reciclar = vta["a_reciclar"].fillna(0) == 1
    if escenario == "sin":
        return pd.Series(0.0, index=vta.index)
    if escenario == "base":
        costo = (vta["banos"].fillna(1).clip(lower=1) * S.REFACCION_BANO_USD + S.REFACCION_COCINA_USD
                 + S.PINTURA_ARS_POR_M2 / S.TC_ARS_USD * vta["sup_total_m2"])
    else:
        costo = S.REFACCION_INTEGRAL_ARS_M2 * (1 + S.IVA_GENERAL) / S.TC_ARS_USD * vta["sup_total_m2"]
    return costo.where(reciclar, 0.0).round(0)


# ==========================================================================
# TIR
# ==========================================================================

def tir(neta_pct, costo_inicial_pct, anios: int = S.HORIZONTE_ANIOS) -> np.ndarray:
    """
    TIR anual, en %, de: pagar el precio mas `costo_inicial_pct` de el, cobrar
    `neta_pct` del precio al final de cada anio durante `anios`, y vender al
    mismo precio al final. Sin apreciacion ni costos de salida.

    Por biseccion, vectorizada: el valor presente cae con la tasa.
    """
    n = np.asarray(neta_pct, dtype=float) / 100
    c = np.asarray(costo_inicial_pct, dtype=float) / 100
    n, c = np.broadcast_arrays(n, c)
    t = np.arange(1, anios + 1)

    def vpn(r):
        desc = (1 + r[:, None]) ** -t
        return -(1 + c) + n * desc.sum(axis=1) + desc[:, -1]

    lo = np.full(n.shape, -0.5)
    hi = np.full(n.shape, 0.5)
    for _ in range(60):
        mid = (lo + hi) / 2
        positivo = vpn(mid) > 0
        lo = np.where(positivo, mid, lo)
        hi = np.where(positivo, hi, mid)
    return np.where(np.isnan(n) | np.isnan(c), np.nan, (lo + hi) / 2 * 100)
