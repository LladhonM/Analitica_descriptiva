#!/usr/bin/env python
"""
test_supuestos.py — Verifica que supuestos.py sea coherente consigo mismo y
con lo que efectivamente uso el pipeline.

El riesgo que cubre: alguien cambia un componente de los gastos (o la
vacancia) y el KPI de rentabilidad neta se mueve en silencio, o no se mueve
porque el dataset quedo generado con los valores viejos. Ninguno de los dos
casos tira error; los dos dejan un numero equivocado en el informe.

Tres bloques:
  1. Aritmetica interna: los derivados salen de sus componentes.
  2. Contra el pipeline: el modelo recibio exactamente estos supuestos.
  3. Contra los datos: las referencias tomadas del dataset siguen valiendo.
Los bloques 2 y 3 necesitan data/processed/; si no existe, se saltean y se
informa cuantos quedaron sin correr.

Uso:
    py src/test_supuestos.py
"""

import os
import sys

import joblib
import pandas as pd

import supuestos as S


fallos = []
corridos = 0
salteados = 0
TOL = 1e-9


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(f"{descripcion}" + (f"\n      {detalle}" if detalle else ""))


def suma_coincide(componentes: dict, total: float) -> bool:
    """El total que recibe el modelo tiene que ser la suma de sus partes."""
    return abs(round(sum(componentes.values()), 2) - total) < TOL


# ==========================================================================
# 1. ARITMETICA INTERNA
# ==========================================================================

# El test que motiva el archivo.
check("ADMIN + ABL + EXTRAORDINARIAS + MANTENIMIENTO == GASTOS_PCT",
      abs(S.ADMINISTRACION_PCT + S.ABL_PCT + S.EXTRAORDINARIAS_PCT
          + S.MANTENIMIENTO_PCT - S.GASTOS_PCT) < 0.005 + TOL,
      f"suma {S.ADMINISTRACION_PCT + S.ABL_PCT + S.EXTRAORDINARIAS_PCT + S.MANTENIMIENTO_PCT}"
      f" contra GASTOS_PCT {S.GASTOS_PCT}")

# El diccionario es lo que se suma: si alguien agrega un quinto gasto como
# constante suelta y no lo mete aca, el total no lo ve.
check("GASTOS_COMPONENTES contiene exactamente los cuatro componentes",
      S.GASTOS_COMPONENTES == {
          "administracion": S.ADMINISTRACION_PCT, "abl": S.ABL_PCT,
          "extraordinarias": S.EXTRAORDINARIAS_PCT, "mantenimiento": S.MANTENIMIENTO_PCT},
      f"{S.GASTOS_COMPONENTES}")
check("GASTOS_PCT es la suma de GASTOS_COMPONENTES",
      suma_coincide(S.GASTOS_COMPONENTES, S.GASTOS_PCT))

# Negativos: el chequeo tiene que detectar un componente cambiado sin
# actualizar el total, y un total cambiado sin tocar componentes. Sin estos,
# un suma_coincide que siempre diera True pasaria el test de arriba.
alterado = dict(S.GASTOS_COMPONENTES, mantenimiento=S.MANTENIMIENTO_PCT + 1.0)
check("NEG: un componente cambiado sin el total se detecta",
      not suma_coincide(alterado, S.GASTOS_PCT))
check("NEG: un total cambiado sin los componentes se detecta",
      not suma_coincide(S.GASTOS_COMPONENTES, S.GASTOS_PCT + 0.01))

# Cada derivado, desde sus insumos.
check("VACANCIA_PCT = meses vacios / (contrato + meses vacios)",
      abs(S.VACANCIA_PCT - round(S.MESES_VACIOS_POR_ROTACION
          / (S.DURACION_CONTRATO_MESES + S.MESES_VACIOS_POR_ROTACION) * 100, 2)) < TOL)
check("ABL_PCT = ABL en ARS / (alquiler de referencia x TC)",
      abs(S.ABL_PCT - round(S.ABL_ARS_MES / (S.ALQUILER_REF_USD_MES * S.TC_ARS_USD) * 100, 2)) < TOL)
check("EXTRAORDINARIAS_PCT = fraccion extraordinaria x expensas/alquiler",
      abs(S.EXTRAORDINARIAS_PCT - round(S.EXTRAORD_SOBRE_EXPENSAS
          * S.EXPENSAS_SOBRE_ALQUILER * 100, 2)) < TOL)
check("MANTENIMIENTO_PCT = meses por anio / 12",
      abs(S.MANTENIMIENTO_PCT - round(S.MANTENIMIENTO_MESES_POR_ANIO / 12 * 100, 2)) < TOL)

# Rangos de sanidad: atrapan un error de unidad (0.08 en vez de 8.0).
check("vacancia entre 0% y 25%", 0 < S.VACANCIA_PCT < 25, f"{S.VACANCIA_PCT}")
check("gastos entre 0% y 40%", 0 < S.GASTOS_PCT < 40, f"{S.GASTOS_PCT}")
check("todos los componentes positivos", all(v > 0 for v in S.GASTOS_COMPONENTES.values()))
check("presupuesto: minimo < maximo", S.PRESUPUESTO_MIN_USD < S.PRESUPUESTO_MAX_USD)
check("banda de retorno: piso <= techo", S.RETORNO_MIN_PISO_PCT <= S.RETORNO_MIN_TECHO_PCT)
check("banda de retorno en % y no en fraccion", 1 < S.RETORNO_MIN_PISO_PCT < 30)
check("horizonte cubre al menos un contrato",
      S.HORIZONTE_ANIOS * 12 >= S.DURACION_CONTRATO_MESES)
check("la grilla de sensibilidad contiene los valores de la 1ra entrega",
      S.VACANCIA_PCT_ENTREGA_1 in S.SENSIBILIDAD_VACANCIA
      and S.GASTOS_PCT_ENTREGA_1 in S.SENSIBILIDAD_GASTOS)


# --- Alquiler temporal ------------------------------------------------------
check("temporal: comision de plataforma entre 0% y 30%", 0 < S.COMISION_PLATAFORMA_PCT < 30)
check("temporal: gestion entre 0% y 40%", 0 <= S.GESTION_TEMPORAL_PCT < 40)
check("temporal: mantenimiento entre 0% y 30%", 0 < S.MANTENIMIENTO_TEMPORAL_PCT < 30)
margen_temporal = ((1 - S.COMISION_PLATAFORMA_PCT / 100) * (1 - S.GESTION_TEMPORAL_PCT / 100)
                   - S.MANTENIMIENTO_TEMPORAL_PCT / 100)
check("temporal: el margen variable es positivo (si no, ninguna ocupacion alcanza)",
      margen_temporal > 0, f"margen {margen_temporal:.3f}")
check("temporal: servicios = canasta IIEP menos transporte",
      S.SERVICIOS_ARS_MES == 282_758 - 116_688, f"{S.SERVICIOS_ARS_MES}")
check("temporal: amoblamiento crece con los dormitorios",
      S.AMOBLAMIENTO_USD["0-1"] < S.AMOBLAMIENTO_USD["2"] < S.AMOBLAMIENTO_USD["3+"])
check("temporal: ocupacion de referencia en %", 1 < S.OCUPACION_REF_PCT <= 100)


# ==========================================================================
# 2. CONTRA EL PIPELINE: lo que el modelo recibio de verdad
# ==========================================================================

MODELO = "data/processed/modelo_alquiler.joblib"
DATASET = "data/processed/dataset_analitico.csv"

if os.path.exists(MODELO):
    m = joblib.load(MODELO)
    # Si falla, el dataset se genero con otros supuestos (o con --gastos a
    # mano): reejecutar py src/kpis.py.
    check("el modelo recibio el GASTOS_PCT de supuestos.py",
          abs(m["gastos"] - S.GASTOS_PCT) < TOL,
          f"joblib {m['gastos']} contra supuestos {S.GASTOS_PCT}: reejecutar py src/kpis.py")
    check("el modelo recibio la VACANCIA_PCT de supuestos.py",
          abs(m["vacancia"] - S.VACANCIA_PCT) < TOL,
          f"joblib {m['vacancia']} contra supuestos {S.VACANCIA_PCT}: reejecutar py src/kpis.py")
    comp = m.get("gastos_componentes")
    check("el joblib guardo los componentes y suman lo aplicado",
          comp is not None and suma_coincide(comp, m["gastos"]), f"{comp}")
else:
    salteados += 4

df = None
if os.path.exists(DATASET):
    df = pd.read_csv(DATASET, encoding="utf-8-sig", low_memory=False)
    v = df[df["rent_bruta_pct"].notna()]
    factor = (1 - S.VACANCIA_PCT / 100) * (1 - S.GASTOS_PCT / 100)
    desvio = float((v["rent_neta_pct"] - (v["rent_bruta_pct"] * factor).round(2)).abs().max())
    # 0,01 de tolerancia: la bruta ya viene redondeada a 2 decimales.
    check("rent_neta_pct = bruta x (1 - vacancia) x (1 - gastos) en todo el dataset",
          desvio <= 0.011, f"desvio maximo {desvio:.3f} pp")
else:
    salteados += 1

# La ocupacion de equilibrio que reporta temporal.py tiene que ser, por
# definicion, la que iguala las dos netas. Si alguien cambia la formula de
# una y no la otra, esta identidad se rompe.
TEMPORAL = "data/processed/temporal_vs_tradicional.csv"
if os.path.exists(TEMPORAL):
    tv = pd.read_csv(TEMPORAL, encoding="utf-8-sig")
    neta_eq = (tv["adr_mediana_usd"] * 365 * tv["ocupacion_equilibrio_pct"] / 100
               * margen_temporal - tv["fijos_usd"])
    dif = float((neta_eq - tv["trad_neta_usd"]).abs().max())
    check("temporal: con la ocupacion de equilibrio las dos netas empatan",
          dif < 1.0, f"diferencia maxima USD {dif:.2f}: reejecutar py src/temporal.py")
    f_trad = (1 - S.VACANCIA_PCT / 100) * (1 - S.GASTOS_PCT / 100)
    dif = float((tv["trad_neta_usd"] - tv["alquiler_est_mediano_usd"] * 12 * f_trad).abs().max())
    check("temporal: la neta tradicional usa los supuestos vigentes del KPI 2",
          dif < 1.0, f"diferencia maxima USD {dif:.2f}: reejecutar py src/temporal.py")
else:
    salteados += 2


# ==========================================================================
# 3. CONTRA LOS DATOS: las referencias tomadas del dataset siguen valiendo
# ==========================================================================

if df is not None:
    a = df[df["operacion"] == "alquiler"]
    ref = a[(a["ambientes"] == 2) & a["sup_total_m2"].between(40, 60)]["alquiler_usd_mes"].median()
    check("ALQUILER_REF_USD_MES coincide con el dataset (+-2%)",
          abs(ref / S.ALQUILER_REF_USD_MES - 1) < 0.02,
          f"dataset {ref:.1f} contra supuestos {S.ALQUILER_REF_USD_MES}")
    exp = a["expensas_sobre_alquiler"].median()
    check("EXPENSAS_SOBRE_ALQUILER coincide con el dataset (+-0,005)",
          abs(exp - S.EXPENSAS_SOBRE_ALQUILER) < 0.005,
          f"dataset {exp:.4f} contra supuestos {S.EXPENSAS_SOBRE_ALQUILER}")
    presentes = set(df["superficie_rango"].dropna().unique())
    check("ORDEN_SUPERFICIE_RANGO tiene las mismas etiquetas que limpieza.py",
          presentes == set(S.ORDEN_SUPERFICIE_RANGO),
          f"dataset {sorted(presentes)} contra supuestos {S.ORDEN_SUPERFICIE_RANGO}")
else:
    salteados += 3


# ==========================================================================
# RESULTADO
# ==========================================================================

print(f"Tests corridos : {corridos}")
print(f"Salteados      : {salteados}" + ("  (falta data/processed: correr el pipeline)"
                                         if salteados else ""))
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
