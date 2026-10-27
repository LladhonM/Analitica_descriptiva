#!/usr/bin/env python
"""
reporte.py — Emite informe/INFORME_HALLAZGOS.md con todas las cifras calculadas en vivo.

POR QUE UN SCRIPT Y NO UN DOCUMENTO ESCRITO A MANO
--------------------------------------------------
Un informe tipeado se desincroniza del dataset la primera vez que alguien
reejecuta el pipeline, y nadie se entera. Aca cada numero del texto sale de un
f-string alimentado por los datos: si cambia un supuesto o se corrige la
limpieza, el informe se regenera con los numeros nuevos. Las cifras narradas
coinciden con las calculadas por construccion.

Los calculos usan las mismas funciones de eda.py y los mismos umbrales de
supuestos.py que el notebook 03, para que el informe y el notebook digan lo
mismo.

Uso:
    py src/reporte.py      (despues de kpis.py, fuentes_externas.py, temporal.py y sesgo.py)

Entradas:
    data/processed/dataset_analitico.csv, sensibilidad_supuestos.csv,
    temporal_vs_tradicional.csv, sesgo_precio_barrio.csv,
    sesgo_representacion_comuna.csv
    data/external/colegio_escribanos_mensual.csv

Salida:
    informe/INFORME_HALLAZGOS.md
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

import eda
import supuestos as S


P = "data/processed"
E = "data/external"
SALIDA = "informe/INFORME_HALLAZGOS.md"
ESTRATO = ["barrio", "superficie_rango"]
ESTRATO_T = ESTRATO + ["tipo_propiedad"]


# --------------------------------------------------------------------------
# Formato en castellano: coma decimal y punto de miles
# --------------------------------------------------------------------------

def num(x: float, d: int = 0) -> str:
    s = f"{x:,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, d: int = 1, signo: bool = False) -> str:
    return (f"{'+' if signo and x > 0 else ''}" + num(x, d)) + "%"


def pp(x: float, d: int = 2, signo: bool = True) -> str:
    return (f"{'+' if signo and x > 0 else ''}" + num(x, d)) + " pp"


def usd(x: float) -> str:
    return "USD " + num(x, 0)


def rho(x: float) -> str:
    return num(x, 3)


def lista(items) -> str:
    """'4, 8 y 9' en vez de '4, 8, 9'."""
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items) or "ninguna"
    return ", ".join(items[:-1]) + " y " + items[-1]


def trimestre(tr: str) -> str:
    """'2026-T2' -> '2do trimestre de 2026'."""
    anio, q = tr.split("-T")
    return f"{ {'1': '1er', '2': '2do', '3': '3er', '4': '4to'}[q] } trimestre de {anio}"


def fecha(iso: str) -> str:
    return datetime.strptime(iso[:10], "%Y-%m-%d").strftime("%d-%m-%Y")


# --------------------------------------------------------------------------
# Calculos
# --------------------------------------------------------------------------

def leer(nombre: str, carpeta: str = P) -> pd.DataFrame:
    return pd.read_csv(os.path.join(carpeta, nombre), encoding="utf-8-sig", low_memory=False)


def calcular() -> dict:
    """Todos los numeros del informe, en un solo lugar."""
    df = leer("dataset_analitico.csv")
    ventas_kpi = df[(df.operacion == "venta") & df.rent_bruta_pct.notna()]
    ok = ventas_kpi[ventas_kpi.estimacion_confiable == 1]
    sens = leer("sensibilidad_supuestos.csv")
    tv = leer("temporal_vs_tradicional.csv")
    sp = leer("sesgo_precio_barrio.csv")
    sr = leer("sesgo_representacion_comuna.csv")
    col = leer("colegio_escribanos_mensual.csv", E)
    tpub = leer("estadistica_ciudad_tiempo_publicacion.csv", E)

    r = {"n_ok": len(ok), "n_kpi": len(ventas_kpi),
         "fecha_scraping": fecha(str(df.fecha_scraping.min())),
         "fecha_scraping_fin": fecha(str(df.fecha_scraping.max()))}
    piso, techo = S.RETORNO_MINIMO_BANDA
    r.update(piso=piso, techo=techo, soberano=S.RETORNO_SOBERANO_REF_PCT)

    # --- 1. Ladrillo contra renta fija --------------------------------------
    factor = (1 - S.VACANCIA_PCT / 100) * (1 - S.GASTOS_PCT / 100)
    alc = ok[ok.venta_usd.between(*S.PRESUPUESTO_USD)]
    optimista = ok.rent_bruta_max * factor
    r.update(
        bruta_med=ok.rent_bruta_pct.median(), neta_med=ok.rent_neta_pct.median(),
        neta_sobre_piso=(ok.rent_neta_pct >= piso).mean() * 100,
        neta_sobre_techo=(ok.rent_neta_pct >= techo).mean() * 100,
        bruta_sobre_piso=(ok.rent_bruta_pct >= piso).mean() * 100,
        neta_alc_med=alc.rent_neta_pct.median(),
        neta_alc_sobre_piso=(alc.rent_neta_pct >= piso).mean() * 100,
        optimista_sobre_piso=(optimista >= piso).mean() * 100,
        pct_en_presupuesto=len(alc) / len(ok) * 100,
        vacancia=S.VACANCIA_PCT, gastos=S.GASTOS_PCT,
        se_lleva=(1 - factor) * 100,
        brecha_piso=piso - ok.rent_neta_pct.median(),
        repago_med=ok.meses_repago.median(),
        horizonte=S.HORIZONTE_ANIOS,
        recupero_horizonte=S.HORIZONTE_ANIOS * 12 / ok.meses_repago.median() * 100,
        sens_neta_min=sens.neta_mediana.min(), sens_neta_max=sens.neta_mediana.max(),
        sens_barrios_min=int(sens.barrios_sobre_piso.min()),
        sens_barrios_max=int(sens.barrios_sobre_piso.max()),
        sens_spearman_min=sens.spearman_ranking_vs_base.min(),
        sens_vac_min=sens.vacancia_pct.min(), sens_vac_max=sens.vacancia_pct.max(),
        sens_gas_min=sens.gastos_pct.min(), sens_gas_max=sens.gastos_pct.max(),
    )
    rank = ok.groupby("barrio").agg(n=("rent_neta_pct", "size"), neta=("rent_neta_pct", "median"))
    rank = rank[rank.n >= S.MIN_VENTAS_BARRIO]
    r.update(n_barrios=len(rank), barrios_sobre_piso=int((rank.neta >= piso).sum()),
             barrios_sobre_piso_lista=", ".join(
                 eda.nombres_barrio(rank[rank.neta >= piso].index)) or "ninguno")

    # --- 2. Temporal -------------------------------------------------------
    r.update(tv_celdas=len(tv), tv_gana_base=int(tv.gana_temporal_base.sum()),
             tv_gana_ref=int(tv.gana_temporal_ref.sum()), ocup_ref=S.OCUPACION_REF_PCT,
             tv_equil_med=tv.ocupacion_equilibrio_pct.median(),
             tv_equil_min=tv.ocupacion_equilibrio_pct.min(),
             tv_equil_auto=tv.ocupacion_equilibrio_auto_pct.median(),
             tv_ocup_med=tv.ocupacion_mediana_pct.median(),
             tv_neta_base_med=tv.temp_neta_pct.median(), tv_neta_ref_med=tv.temp_neta_ref_pct.median())

    # --- 3. Sesgo ---------------------------------------------------------
    usados, nuevos = sp[sp.estado == "usado"], sp[sp.estado == "estrenar"]
    r.update(sp_celdas=len(sp), sp_barato=(sp.desvio_pct < 0).mean() * 100,
             sp_med=sp.desvio_pct.median(), sp_med_usado=usados.desvio_pct.median(),
             sp_med_nuevo=nuevos.desvio_pct.median(),
             sp_pond=np.average(sp.desvio_pct, weights=sp.n_remax),
             sr_reasignar=(sr.pct_cartera_venta - sr.pct_departamentos_ciudad).abs().sum() / 2,
             sr_sobre=sr.loc[sr.indice_venta > 1.25, "comuna"].tolist(),
             sr_sub=sr.loc[sr.indice_venta < 0.75, "comuna"].tolist(),
             sr_min=sr.indice_venta.min(), sr_max=sr.indice_venta.max())
    # Si se comprara al precio publicado promedio del mercado y no al de la
    # cartera, la renta bajaria en proporcion al desvio (el precio divide).
    r["neta_a_precio_mercado"] = r["neta_med"] * (1 + r["sp_pond"] / 100)

    # --- 4. Dispersion intra contra entre -----------------------------------
    b = eda.por_barrio(ok, "rent_bruta_pct", minimo=S.MIN_VENTAS_BARRIO)
    b["venta_m2"] = ok.groupby("barrio").venta_m2_usd.median().reindex(b.index)
    ratios = []
    for tramo in S.ORDEN_SUPERFICIE_RANGO:
        sub = ok[ok.superficie_rango == tramo]
        n = sub.groupby("barrio").size()
        validos = n[n >= S.MIN_VENTAS_BARRIO].index
        if len(validos) < 2:
            continue
        g = sub[sub.barrio.isin(validos)].groupby("barrio").rent_bruta_pct
        iqr = g.quantile(.75) - g.quantile(.25)
        ratios.append(iqr.max() / (g.median().max() - g.median().min()))
    med_mkt = ok.rent_bruta_pct.median()
    r.update(entre=b.mediana.max() - b.mediana.min(),
             barrio_alto=eda.nombre_barrio(b.mediana.idxmax()),
             barrio_bajo=eda.nombre_barrio(b.mediana.idxmin()),
             iqr_max=b.IQR.max(), iqr_max_barrio=eda.nombre_barrio(b.IQR.idxmax()),
             iqr_med=b.IQR.median(), ratio_tramo_min=min(ratios), ratio_tramo_max=max(ratios),
             solapan=((ok.rent_bruta_min <= med_mkt) & (ok.rent_bruta_max >= med_mkt)).mean() * 100,
             err_med=ok.error_estimacion.median() * 100)

    # --- 5. Que comprar ---------------------------------------------------
    r["h1_rho"] = b.venta_m2.corr(b.mediana, method="spearman")
    rh = []
    for tramo in S.ORDEN_SUPERFICIE_RANGO:
        sub = ok[ok.superficie_rango == tramo]
        g = sub.groupby("barrio").agg(n=("rent_bruta_pct", "size"), m2=("venta_m2_usd", "median"),
                                      renta=("rent_bruta_pct", "median"))
        g = g[g.n >= S.MIN_AVISOS_CELDA]
        if len(g) >= 5:
            rh.append(g.m2.corr(g.renta, method="spearman"))
    r.update(h1_tramo_min=min(rh), h1_tramo_max=max(rh), h1_tramos=len(rh))
    g_tp = leer("../reference/ranking_barrios_entrega1.csv")
    r["h1_rho_e1"] = g_tp.venta_m2.corr(g_tp.rent_bruta, method="spearman")

    r["am_ingenua"] = (ok.loc[ok.amenities == 1, "rent_bruta_pct"].median()
                       - ok.loc[ok.amenities == 0, "rent_bruta_pct"].median())
    t_am = eda.efecto_estratificado(ok, "amenities", "rent_bruta_pct", ESTRATO, S.MIN_GRUPO_ESTRATO)
    t_amt = eda.efecto_estratificado(ok, "amenities", "rent_bruta_pct", ESTRATO_T, S.MIN_GRUPO_ESTRATO)
    ra, rat = eda.resumir_efecto(t_am, len(ok)), eda.resumir_efecto(t_amt, len(ok))
    r.update(am_estrato=ra["mediana_ponderada"], am_estrato_t=rat["mediana_ponderada"],
             am_celdas=ra["celdas"], am_neg=ra["pct_celdas_negativas"])
    for resp, clave in [("venta_m2_usd", "am_prima_precio"), ("alquiler_est_m2", "am_prima_alq")]:
        t = eda.efecto_estratificado(ok, "amenities", resp, ESTRATO, S.MIN_GRUPO_ESTRATO)
        r[clave] = eda.mediana_ponderada(t.diferencia / t.mediana_0 * 100, t.peso)

    deptos = ok[ok.tipo_familia == "departamento"]
    orden = S.ORDEN_SUPERFICIE_RANGO
    chico, grande = orden[0], orden[3]
    filas = []
    for _, g in deptos.groupby("barrio"):
        a_ = g.loc[g.superficie_rango == chico, "rent_bruta_pct"]
        z_ = g.loc[g.superficie_rango == grande, "rent_bruta_pct"]
        if len(a_) >= S.MIN_GRUPO_ESTRATO and len(z_) >= S.MIN_GRUPO_ESTRATO:
            filas.append((a_.median() - z_.median(), min(len(a_), len(z_))))
    ctl = pd.DataFrame(filas, columns=["dif", "peso"])
    r.update(tam_chico=chico, tam_grande=grande, tam_barrios=len(ctl),
             tam_dif=eda.mediana_ponderada(ctl.dif, ctl.peso), tam_pct=(ctl.dif > 0).mean() * 100)

    ventas_all = df[(df.operacion == "venta") & df.venta_m2_usd.notna()]
    t3p = eda.efecto_estratificado(ventas_all, "a_reciclar", "venta_m2_usd", ESTRATO, S.MIN_GRUPO_ESTRATO)
    t3r = eda.efecto_estratificado(ok, "a_reciclar", "rent_bruta_pct", ESTRATO, S.MIN_GRUPO_ESTRATO)
    r.update(h3_desc=eda.mediana_ponderada(t3p.diferencia / t3p.mediana_0 * 100, t3p.peso),
             h3_celdas=len(t3p), h3_neg=(t3p.diferencia < 0).mean() * 100,
             h3_renta=eda.resumir_efecto(t3r, len(ok))["mediana_ponderada"], h3_celdas_r=len(t3r))

    def spearman_estrato(base, y, minimo):
        base = base[(base.antiguedad_anios_imputada == 0) & base[y].notna()]
        rs, ns = [], []
        for _, g in base.groupby(ESTRATO, observed=True):
            if len(g) >= minimo and g.antiguedad_anios.nunique() > 1:
                rs.append(g.antiguedad_anios.corr(g[y], method="spearman")); ns.append(len(g))
        return eda.mediana_ponderada(rs, ns), len(rs)
    r["h4_venta"], r["h4_celdas_v"] = spearman_estrato(df[df.operacion == "venta"], "venta_m2_usd",
                                                       S.MIN_CELDA_CORRELACION)
    r["h4_alq"], r["h4_celdas_a"] = spearman_estrato(df[df.operacion == "alquiler"],
                                                     "alquiler_m2_usd_mes", S.MIN_AVISOS_CELDA)

    # --- Liquidez: tiempo medio de publicacion (IDECBA, toda la Ciudad) -----
    ult_t = tpub.trimestre.max()
    tot = tpub[tpub.ambientes == "Total"].set_index("trimestre").dias
    r.update(liq_trim=ult_t, liq_dias=float(tot[ult_t]), liq_meses=float(tot[ult_t]) / 30.4,
             liq_max=float(tot.max()), liq_max_trim=tot.idxmax())

    # --- Zonas: el mapa del notebook 03 en numeros -------------------------
    zonas = {"norte": [2, 13, 14], "centro": [1, 3, 5, 6, 15],
             "sur y oeste": [4, 7, 8, 9, 10, 11, 12]}
    r["zona_norte_comunas"] = zonas["norte"]
    for zona, comunas in zonas.items():
        z = ok[ok.comuna.isin(comunas)]
        r[f"zona_{zona}_piso"] = (z.rent_neta_pct >= piso).mean() * 100
        r[f"zona_{zona}_pct"] = len(z) / len(ok) * 100

    # --- Contexto de mercado ------------------------------------------------
    ult = col.dropna(subset=["monto_promedio_usd"]).iloc[-1]
    a25 = col[col.mes.str.startswith("2025")]
    r.update(escritura=float(ult.monto_promedio_usd), escritura_mes=ult.mes,
             hip_2025=a25.hipotecas.sum() / a25.compraventas.sum() * 100,
             venta_med=ok.venta_usd.median())
    return r


# --------------------------------------------------------------------------
# Texto
# --------------------------------------------------------------------------

def informe(r: dict) -> str:
    L = []
    w = L.append
    w("# Informe de hallazgos — 2da pre-entrega")
    w("")
    w("**TP Integrador · 82.04 Analítica Descriptiva (ITBA) · Grupo 2**")
    w("")
    w(f"*Generado por `py src/reporte.py` el {datetime.now():%d-%m-%Y}. Cada cifra de este documento "
      f"se calcula al generarlo a partir de `data/processed/` y `data/external/`: si se reejecuta el "
      f"pipeline, el informe se regenera con los números nuevos.*")
    w("")
    w("**Cliente:** un pequeño inversor con ahorros en dólares que compra **una sola unidad** en CABA "
      f"para alquilarla, con un presupuesto de {usd(S.PRESUPUESTO_MIN_USD)} a {usd(S.PRESUPUESTO_MAX_USD)}. "
      f"**Base:** {num(r['n_ok'])} departamentos, casas y PH en venta de la cartera de RE/MAX, "
      f"relevados entre el {r['fecha_scraping']} y el {r['fecha_scraping_fin']}, con alquiler estimado confiable.")
    w("")
    w("Los hallazgos van ordenados por cuánto cambian la decisión del inversor. Cada uno cierra con "
      "la decisión que modifica.")
    w("")
    w("---")
    w("")

    # 1
    # Los titulos tambien dependen de los datos: si maniana la neta supera el
    # piso, el titulo no puede seguir afirmando lo contrario.
    w("## 1. Solo por renta, el ladrillo " + ("no le gana" if r["neta_med"] < r["piso"] else "le gana")
      + " a un bono corporativo en dólares")
    w("")
    w(f"La rentabilidad **neta** mediana (después de {pct(r['vacancia'], 2)} de vacancia y "
      f"{pct(r['gastos'], 2)} de gastos del propietario) es **{pct(r['neta_med'], 2)}**. La banda de "
      f"retorno mínimo, las obligaciones negociables corporativas en dólares de YPF 2031 y Pampa 2037, "
      f"va de **{pct(r['piso'], 2)} a {pct(r['techo'], 2)}**. La propiedad mediana queda "
      f"{pp(abs(r['brecha_piso']), signo=False)} {'por debajo' if r['brecha_piso'] > 0 else 'por encima'} del piso.")
    w("")
    w("| | mediana | supera el piso de la banda |")
    w("|---|---|---|")
    w(f"| Rentabilidad bruta | {pct(r['bruta_med'], 2)} | {pct(r['bruta_sobre_piso'])} |")
    w(f"| Rentabilidad neta | {pct(r['neta_med'], 2)} | {pct(r['neta_sobre_piso'])} |")
    w(f"| Neta, solo dentro del presupuesto | {pct(r['neta_alc_med'], 2)} | {pct(r['neta_alc_sobre_piso'])} |")
    w(f"| Neta en el extremo optimista de la banda de error (KPI 4) | — | {pct(r['optimista_sobre_piso'])} |")
    w("")
    nb = r["barrios_sobre_piso"]
    w(f"De los {r['n_barrios']} barrios con {S.MIN_VENTAS_BARRIO} o más ventas, "
      f"{nb} {'tiene' if nb == 1 else 'tienen'} una neta mediana sobre el piso "
      f"({r['barrios_sobre_piso_lista']}). "
      f"La comparación es contra un instrumento que paga en dólares, cotiza en bolsa y no tiene "
      f"vacancia, inquilino ni expensas extraordinarias.")
    w("")
    w(f"**El resultado depende poco de los supuestos en el nivel, pero mucho en el umbral.** Recorriendo "
      f"vacancia de {pct(r['sens_vac_min'], 0)} a {pct(r['sens_vac_max'], 0)} y gastos de "
      f"{pct(r['sens_gas_min'], 0)} a {pct(r['sens_gas_max'], 0)}, la neta mediana se mueve entre "
      f"{pct(r['sens_neta_min'], 2)} y {pct(r['sens_neta_max'], 2)}: "
      f"{'en ningún escenario alcanza el piso' if r['sens_neta_max'] < r['piso'] else 'en algún escenario alcanza el piso'}. "
      f"Lo que sí cambia es cuántos barrios lo superan: de {r['sens_barrios_max']} en el escenario más "
      f"favorable a {r['sens_barrios_min']} en el más adverso.")
    w("")
    w(f"**Tampoco lo resuelve el horizonte.** Con un repago mediano de {num(r['repago_med'])} meses, en "
      f"{r['horizonte']} años el alquiler devuelve el {pct(r['recupero_horizonte'], 0)} del precio. El resto "
      f"depende de revender la unidad, en un mercado donde en 2025 solo el {pct(r['hip_2025'])} de las "
      f"compraventas de la Ciudad se hizo con hipoteca: los compradores pagan con ahorros propios. "
      f"Y vender lleva tiempo: en el {trimestre(r['liq_trim'])} un departamento en venta pasaba en promedio "
      f"{num(r['liq_dias'])} días publicado, unos {num(r['liq_meses'], 1)} meses (el máximo de la serie "
      f"fue {num(r['liq_max'])} días, en el {trimestre(r['liq_max_trim'])}). "
      f"Es el costo de salida que una obligación negociable no tiene. Es tiempo publicado, no tiempo de "
      f"venta, y es de toda la Ciudad (Instituto de Estadística de la Ciudad, sobre avisos de Argenprop).")
    w("")
    w("**Qué no dice:** que comprar sea un error. El KPI mide renta corriente y deja afuera la apreciación "
      "del inmueble, que un corte temporal único no permite estimar.")
    w("")
    w("> **Decisión que cambia.** La pregunta deja de ser \"¿en qué barrio compro?\" y pasa a ser "
      "\"¿compro o no?\". Comprar para renta solo se justifica para las unidades cuya neta supera el piso de "
      "la banda con margen, o como una apuesta explícita a la revalorización, declarada como tal. Para la "
      "unidad típica, la alternativa de renta fija en dólares domina en retorno corriente, liquidez y "
      "riesgo de gestión.")
    w("")

    # 2
    w("## 2. Alquilar por noche no rescata la inversión")
    w("")
    w(f"Se comparó el alquiler temporal contra el tradicional, **neta contra neta**, en {r['tv_celdas']} "
      f"combinaciones de barrio y dormitorios con datos suficientes de los dos lados (Inside Airbnb y RE/MAX). "
      f"En el temporal las expensas y los servicios los paga el dueño, y se suman comisión de plataforma, "
      f"gestión, desgaste y amoblamiento.")
    w("")
    w(f"Como la ocupación no se observa, la medida central es la **ocupación de equilibrio**, con la que el "
      f"temporal empata al tradicional: mediana **{pct(r['tv_equil_med'])}** con gestión tercerizada "
      f"({pct(r['tv_equil_auto'])} autogestionado) y nunca menos de {pct(r['tv_equil_min'])}. La ocupación "
      f"que estima Inside Airbnb para esas celdas tiene una mediana de {pct(r['tv_ocup_med'])}: con ella, el "
      f"temporal le gana al tradicional en {r['tv_gana_base']} de {r['tv_celdas']} celdas, con una neta "
      f"mediana de {pct(r['tv_neta_base_med'], 2)}. Aun con el {pct(r['ocup_ref'], 0)} de ocupación que "
      f"informa la prensa, gana en {r['tv_gana_ref']}.")
    w("")
    comp_ref = ("mayor que" if r["tv_equil_med"] > r["ocup_ref"] else "menor o igual que")
    w("> **Decisión que cambia.** El temporal no es la salida para mejorar la renta de la unidad típica. "
      "Solo se justifica si el inversor puede sostener una ocupación por encima del equilibrio de su barrio "
      f"y su tipología, que en la mediana es {comp_ref} la ocupación que publica la prensa para el mercado.")
    w("")

    # 3
    w("## 3. La cartera de RE/MAX publica " + ("más barato" if r["sp_pond"] < 0 else "más caro")
      + " que el mercado: sus rentabilidades están del lado " + ("alto" if r["sp_pond"] < 0 else "bajo"))
    w("")
    w(f"Contra el precio publicado del m² que calcula el Instituto de Estadística de la Ciudad sobre avisos "
      f"de Argenprop, en la misma celda de barrio, ambientes y estado, RE/MAX publica más barato en el "
      f"{pct(r['sp_barato'], 0)} de las {r['sp_celdas']} celdas comparadas: {pct(r['sp_med_usado'], 1, True)} "
      f"de desvío mediano en usados y {pct(r['sp_med_nuevo'], 1, True)} a estrenar. Contra el stock de "
      f"departamentos del Censo 2022, la cartera sobrerrepresenta "
      f"{'la comuna' if len(r['sr_sobre']) == 1 else 'las comunas'} {lista(r['sr_sobre'])} y subrepresenta "
      f"{'la comuna' if len(r['sr_sub']) == 1 else 'las comunas'} {lista(r['sr_sub'])}: habría que reasignar el {pct(r['sr_reasignar'])} de las ventas para "
      f"replicar la composición de la Ciudad.")
    w("")
    w(f"El precio está en el denominador de la rentabilidad. Si la unidad se comprara al precio publicado "
      f"promedio del mercado y no al de la cartera, la neta mediana bajaría de {pct(r['neta_med'], 2)} a "
      f"alrededor de {pct(r['neta_a_precio_mercado'], 2)} (aplicando el desvío promedio ponderado de "
      f"{pct(r['sp_pond'], 1, True)}), suponiendo que el alquiler no cambia. No hay fuente oficial para medir "
      f"si la cartera de alquileres tiene el mismo sesgo, así que el efecto neto no se puede firmar.")
    w("")
    w("> **Decisión que cambia.** Los niveles absolutos de rentabilidad del trabajo son los de la cartera de "
      "RE/MAX, no los de CABA, y probablemente están del lado alto: la brecha contra la renta fija del "
      "hallazgo 1 es, si algo, mayor. El inversor debe usar el análisis para **comparar** propiedades y "
      "barrios entre sí, no para prometerse una rentabilidad.")
    w("")

    # 4
    w("## 4. Elegir la propiedad pesa tanto como elegir el barrio")
    w("")
    w(f"Entre el barrio que más rinde ({r['barrio_alto']}) y el que menos ({r['barrio_bajo']}) hay "
      f"{pp(r['entre'], signo=False)} de rentabilidad bruta mediana. El rango intercuartil **dentro** de un "
      f"solo barrio llega a {pp(r['iqr_max'], signo=False)} ({r['iqr_max_barrio']}), y el mediano es "
      f"{pp(r['iqr_med'], signo=False)}. No es mezcla de tamaños: dentro de cada rango de superficie, la "
      f"dispersión interna máxima de un barrio equivale a entre {pct(r['ratio_tramo_min'] * 100, 0)} y "
      f"{pct(r['ratio_tramo_max'] * 100, 0)} de la distancia entre barrios.")
    w("")
    w(f"Pero la estimación tiene su propio error, de {pct(r['err_med'])} mediano: para el "
      f"{pct(r['solapan'])} de las propiedades, la banda de incertidumbre contiene la mediana del mercado, "
      f"y su diferencia contra el promedio no se distingue del ruido.")
    w("")
    w("> **Decisión que cambia.** \"Comprá en tal barrio\" no alcanza como criterio. El inversor tiene que "
      "comparar unidades concretas, y solo preferir una sobre otra cuando sus bandas de incertidumbre no se "
      "superponen. Si se superponen, la elección se decide por liquidez o por riesgo, no por el KPI.")
    w("")

    # 5
    w("## 5. Qué rinde más, comparando propiedades semejantes")
    w("")
    w("Cada efecto se mide **dentro de celdas de barrio y rango de superficie**, para no atribuirle a un "
      "atributo lo que es diferencia de zona o de tamaño.")
    w("")
    w(f"- **Metro cuadrado barato.** Los barrios con el m² más caro rinden menos (Spearman {rho(r['h1_rho'])} "
      f"sobre {r['n_barrios']} barrios), y la relación se sostiene dentro de cada rango de superficie "
      f"(de {rho(r['h1_tramo_min'])} a {rho(r['h1_tramo_max'])}).")
    w(f"- **Fuera del corredor norte.** En el norte (comunas {lista(r['zona_norte_comunas'])}) solo el "
      f"{pct(r['zona_norte_piso'])} de las propiedades supera en neto el piso de las ON, contra el "
      f"{pct(r['zona_centro_piso'])} en el centro y el {pct(r['zona_sur y oeste_piso'])} en el sur y "
      f"oeste, con la oferta repartida en proporciones parecidas entre las tres zonas "
      f"({pct(r['zona_norte_pct'], 0)}, {pct(r['zona_centro_pct'], 0)} y "
      f"{pct(r['zona_sur y oeste_pct'], 0)}).")
    w(f"- **Amenities.** {'Restan' if r['am_estrato'] < 0 else 'Suman'} {pp(abs(r['am_estrato']), signo=False)} "
      f"de rentabilidad dentro del estrato ({pp(abs(r['am_estrato_t']), signo=False)} fijando también el tipo "
      f"de propiedad), con diferencia negativa en el {pct(r['am_neg'], 0)} de {r['am_celdas']} celdas. Encarecen el m² un {pct(r['am_prima_precio'])} y "
      f"suben el alquiler por m² solo un {pct(r['am_prima_alq'])}.")
    w(f"- **Unidades chicas.** Entre departamentos del mismo barrio, los de {r['tam_chico']} m² rinden "
      f"{pp(r['tam_dif'])} respecto de los de {r['tam_grande']} m², y rinden más en el "
      f"{pct(r['tam_pct'], 0)} de los {r['tam_barrios']} barrios comparables.")
    w(f"- **A reciclar.** Cotizan con un descuento de {pct(-r['h3_desc'])} en el m² respecto de propiedades "
      f"comparables (negativo en el {pct(r['h3_neg'], 0)} de {r['h3_celdas']} celdas), y dejan "
      f"{pp(r['h3_renta'])} de rentabilidad bruta antes de descontar el costo del reciclaje, que el dataset "
      f"no tiene.")
    w("")
    w("> **Decisión que cambia.** Dentro del presupuesto, conviene buscar fuera del corredor norte e inclinarse por barrios de m² más barato, "
      "unidades chicas y edificios sin amenities, y mirar las unidades a reciclar como oportunidad solo si "
      "el costo de obra cabe en el descuento. Pagar amenities es una decisión de consumo, no de inversión. "
      "Las unidades chicas rotan más de inquilino: la vacancia uniforme del KPI 2 probablemente la "
      "subestima.")
    w("")

    # 6
    w("## 6. Estado de las hipótesis")
    w("")
    w("Se evalúan por el tamaño del efecto dentro del estrato, sin p-valor. El contraste formal es alcance "
      "de la 3ra entrega, y el test que lo hará queda declarado.")
    w("")
    w("| Hipótesis | Evidencia en esta entrega | Estado | Test formal (3ra entrega) |")
    w("|---|---|---|---|")
    w(f"| **H1.** La rentabilidad bruta cae con el precio del m² del barrio | Spearman {rho(r['h1_rho'])} "
      f"sobre {r['n_barrios']} barrios; de {rho(r['h1_tramo_min'])} a {rho(r['h1_tramo_max'])} dentro de "
      f"cada rango de superficie. La 1ra entrega daba {rho(r['h1_rho_e1'])}: la diferencia la explican las "
      f"dummies de RegEx (README) | {'Respaldada' if r['h1_rho'] < -0.5 and r['h1_tramo_max'] < -0.5 else 'No respaldada'} | Spearman unilateral con p-valor por permutación, repetido "
      f"por tramo con corrección por comparaciones múltiples |")
    w(f"| **H2.** El precio del m² cae con la distancia al subte | No evaluable: requiere fusión espacial | "
      f"Pendiente | Regresión del precio del m² sobre la distancia, con efectos fijos de barrio |")
    w(f"| **H3.** Los inmuebles a reciclar cotizan con descuento, y ese descuento es la oportunidad | "
      f"Descuento de {pct(-r['h3_desc'])} en el m² en {r['h3_celdas']} celdas; {pp(r['h3_renta'])} de "
      f"rentabilidad bruta en {r['h3_celdas_r']} celdas | "
      f"{'Respaldada, tentativa por la cantidad de celdas' if r['h3_desc'] < 0 and r['h3_renta'] > 0 else 'No respaldada'} | "
      f"Van Elteren (Mann-Whitney estratificado por celda) |")
    w(f"| **H4.** La antigüedad pesa más en el precio de venta que en el alquiler | Spearman antigüedad vs "
      f"m² dentro del estrato: {rho(r['h4_venta'])} en venta ({r['h4_celdas_v']} celdas) contra "
      f"{rho(r['h4_alq'])} en alquiler ({r['h4_celdas_a']} celdas), con antigüedad observada | "
      f"{'Respaldada, tentativa por las pocas celdas de alquiler' if r['h4_venta'] < r['h4_alq'] else 'No respaldada'} | "
      f"Wald sobre la diferencia de coeficientes de dos regresiones (log precio y log alquiler) con efectos "
      f"fijos de celda |")
    w("")
    w("> **Decisión que cambia.** H1 y H4 describen el mismo mecanismo: el precio de compra se mueve más que "
      "el alquiler, y lo que abarata la compra (zona, antigüedad) sube la renta. Para un inversor que busca "
      "renta, lo viejo y lo periférico no son defectos a evitar sino la fuente del rendimiento, siempre que "
      "entre en su tolerancia de riesgo y liquidez.")
    w("")

    # Limites
    w("## Lo que este informe no permite afirmar")
    w("")
    w("- **Retorno total.** Solo se mide renta; la apreciación requiere una serie temporal.")
    w("- **Causalidad.** Comparar dentro del estrato controla por zona, tamaño y tipología, no por todo.")
    w("- **El mercado de CABA.** Se describe la cartera de una red inmobiliaria, con el sesgo del hallazgo 3.")
    w("- **Precios de cierre.** Todos los precios son de publicación, del lado de la venta y del alquiler.")
    w("- **Liquidez por propiedad.** El tiempo de publicación es un promedio de la Ciudad; el dataset "
      "es un corte único y no mide cuánto tarda en venderse cada unidad.")
    w("")
    w("Los supuestos (vacancia, gastos, banda de retorno, horizonte, costos del temporal) están en "
      "`supuestos.py` con su fuente y fecha. El detalle de cada hallazgo está en `notebooks/03_eda.ipynb`, y "
      "las fuentes externas, en `informe/FUENTES_EXTERNAS.md`.")
    w("")
    return "\n".join(L)


def main() -> int:
    requeridos = [os.path.join(P, f) for f in ["dataset_analitico.csv", "sensibilidad_supuestos.csv",
                                               "temporal_vs_tradicional.csv", "sesgo_precio_barrio.csv",
                                               "sesgo_representacion_comuna.csv"]]
    requeridos += [os.path.join(E, "colegio_escribanos_mensual.csv"),
                   os.path.join(E, "estadistica_ciudad_tiempo_publicacion.csv"),
                   "data/reference/ranking_barrios_entrega1.csv"]
    faltan = [f for f in requeridos if not os.path.exists(f)]
    if faltan:
        print(f"Faltan insumos: {faltan}")
        print("Correr antes: py src/kpis.py, py src/fuentes_externas.py, py src/temporal.py, py src/sesgo.py")
        return 1
    r = calcular()
    texto = informe(r)
    os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
    with open(SALIDA, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)
    print(f"Escrito {SALIDA} ({len(texto.splitlines())} lineas)")
    print(f"    neta mediana {r['neta_med']:.2f}% contra piso {r['piso']:.2f}%; "
          f"{r['neta_sobre_piso']:.1f}% de las propiedades lo supera")
    return 0


if __name__ == "__main__":
    sys.exit(main())
