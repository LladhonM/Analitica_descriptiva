#!/usr/bin/env python
"""
test_costos.py — Tests del ABL segmentado, los costos de entrada y la TIR
(costos.py), y de su materializacion en el dataset.

Lo que cubre:
  1. La formula del ABL contra un oraculo externo: los siete ejemplos que
     calcula Roomix (05-05-2026) con la Ley 6927. Ademas, el minimo, el tope,
     el recargo y que la escala no salte en los bordes de los tramos.
  2. Costos de entrada, refaccion y TIR, sin datos.
  3. Sobre los datos: que el escenario plano reproduzca la neta de la 2da
     entrega y que las columnas nuevas sean coherentes entre si.

Cada control lleva un NEGATIVO cuando tiene sentido provocar el error. No
toca la red. Las rutas se resuelven desde la ubicacion de este archivo.

Uso:
    py src/test_costos.py
"""

import os
import sys

import numpy as np
import pandas as pd

import costos as C
import supuestos as S


fallos = []
corridos = 0

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ruta(relativa: str) -> str:
    return os.path.join(RAIZ, relativa)


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


SIN_TOPE = np.array([1e15])


def abl(vfh: float, cg: float, mercado=SIN_TOPE) -> float:
    return float(C.abl_anual_ars(np.array([vfh]), np.array([cg]), mercado)[0])


# ==========================================================================
# 1. ABL (sin datos)
# ==========================================================================

# Roomix, "Cuanto se paga de ABL en CABA 2026", 05-05-2026: VFH, coeficiente
# geografico y total anual (Inmobiliario + Tasa). Los de 40M en adelante
# incluyen el recargo del 1% de la tasa.
ROOMIX = [(15e6, 0.75, 255_000), (15e6, 1.25, 285_000), (25e6, 0.75, 427_925),
          (25e6, 1.75, 527_925), (40e6, 1.25, 781_575), (60e6, 1.25, 1_195_175),
          (100e6, 1.75, 2_248_875)]
for vfh, cg, esperado in ROOMIX:
    obtenido = abl(vfh, cg)
    check(f"ABL de Roomix: VFH {vfh / 1e6:.0f}M, CG {cg}", abs(obtenido - esperado) < 1,
          f"esperado {esperado:,}, obtenido {obtenido:,.0f}")
check("NEG: sin el recargo, el ejemplo de 40M no coincide con Roomix",
      abs(C.impuesto_inmobiliario(np.array([40e6]))[0] + 40e6 * 0.008 * (1 + 1.25 * 0.5) - 781_575) > 1)

check("minimo anual de $14.100 (art. 44)", abl(1_000, 0.0) == S.ABL_MINIMO_ANUAL_ARS)
check("tope del 1% del valor de mercado (art. 45)",
      abl(100e6, 1.75, np.array([50e6])) == 50e6 * S.ABL_TOPE_SOBRE_MERCADO)
check("recargo: solo por encima de $32M de VFH",
      abl(32_000_000, 1.0) < abl(32_000_001, 1.0) - 1_000)
bordes = np.array([t[0] for t in S.INMOBILIARIO_TRAMOS[1:]], dtype=float)
salto = C.impuesto_inmobiliario(bordes) - C.impuesto_inmobiliario(bordes - 1)
check("Inmobiliario: la escala no salta en los bordes de los tramos", (np.abs(salto) < 1).all(),
      f"saltos {salto.round(2)}")
vfh = np.linspace(1e6, 300e6, 500)
check("ABL creciente con la VFH", (np.diff(C.abl_anual_ars(vfh, np.full(500, 1.0), np.full(500, 1e15))) > 0).all())

cg = C.coef_geografico(pd.Series(["palermo", "constitucion", "no es un barrio"]))
check("CG de un barrio partido: promedio de sus subzonas",
      abs(cg[0] - np.mean(S.ABL_COEF_GEOGRAFICO["palermo"])) < 1e-12)
check("CG de un barrio con un solo valor", cg[1] == 0.50)
check("NEG: un barrio desconocido da NaN, no un coeficiente inventado", np.isnan(cg[2]))

# Calibracion sobre un caso armado: la referencia mediana tiene que pagar ABL_PCT.
rng = np.random.default_rng(0)
n = 400
sint = pd.DataFrame({
    "barrio": rng.choice(["palermo", "almagro", "flores"], n),
    "tipo_familia": "departamento",
    "ambientes": rng.choice([1, 2, 3], n),
    "sup_total_m2": rng.uniform(30, 90, n),
    "venta_m2_usd": rng.uniform(1_500, 3_000, n),
})
sint["venta_usd"] = sint["venta_m2_usd"] * sint["sup_total_m2"]
sint["alquiler_est_usd_mes"] = sint["venta_usd"] * 0.07 / 12
p = C.calibrar_proporcion(sint)
ref = C.es_referencia(sint)
check("calibracion: la referencia mediana paga ABL_PCT",
      abs(C.abl_por_propiedad(sint, p).loc[ref, "abl_pct"].median() - S.ABL_PCT) < 0.01, f"proporcion {p:.4f}")
check("calibracion: dentro del tope legal", 0 < p <= S.VFH_TOPE_SOBRE_MERCADO)


# ==========================================================================
# 2. COSTOS DE ENTRADA, REFACCION Y TIR (sin datos)
# ==========================================================================

umbral_usd = S.SELLOS_UMBRAL_ARS / S.TC_ARS_USD
precios = pd.Series([umbral_usd - 1_000, umbral_usd + 1_000])
base = C.costos_entrada_pct(precios, "base")
fijo = S.COMISION_COMPRADOR_PCT[0] + S.ESCRIBANO_PCT[0] + S.REGISTRALES_PCT[0]
check("entrada: sellos reducidos hasta el umbral (mitad de 2,70%)",
      abs(base[0] - (fijo + S.SELLOS_ALICUOTA_REDUCIDA_PCT / 2)) < 0.005, f"{base[0]}")
check("entrada: sellos generales arriba del umbral (mitad de 3,50%)",
      abs(base[1] - (fijo + S.SELLOS_ALICUOTA_PCT / 2)) < 0.005, f"{base[1]}")
check("entrada: sin costos da 0", (C.costos_entrada_pct(precios, "sin") == 0).all())
check("entrada: el escenario alto cuesta mas que el base",
      (C.costos_entrada_pct(precios, "alto") > base).all())

u = pd.DataFrame({"a_reciclar": [1, 0, 1], "banos": [1, 1, np.nan], "sup_total_m2": [50, 50, 50]})
r = C.refaccion_usd(u, "base")
esperado = S.REFACCION_BANO_USD + S.REFACCION_COCINA_USD + S.PINTURA_ARS_POR_M2 / S.TC_ARS_USD * 50
check("refaccion base: bano + cocina + pintura", abs(r[0] - esperado) < 1, f"{r[0]} contra {esperado:.0f}")
check("refaccion: 0 si la unidad no es a reciclar", r[1] == 0)
check("refaccion: sin dato de banos cuenta uno", abs(r[2] - r[0]) < 1)
check("refaccion: la integral cuesta mas que la minima", C.refaccion_usd(u, "alto")[0] > r[0])

t = C.tir([5.67, 10.0, 0.0, np.nan], [0, 0, 0, 0])
check("TIR sin costos iniciales = neta", np.allclose(t[:3], [5.67, 10.0, 0.0], atol=1e-6), f"{t}")
check("TIR con dato faltante da NaN", np.isnan(t[3]))
t = C.tir([5.67, 5.67, 5.67], [0, 5, 10])
check("TIR decrece con los costos iniciales", t[0] > t[1] > t[2], f"{t}")
# Con costo c y neta n, el VPN a la TIR tiene que ser cero.
n_, c_ = 0.0567, 0.0555
r_ = C.tir([5.67], [5.55])[0] / 100
vpn = -(1 + c_) + sum(n_ / (1 + r_) ** k for k in range(1, 6)) + (1 + r_) ** -5
check("TIR: el valor presente a esa tasa es cero", abs(vpn) < 1e-9, f"{vpn}")


# ==========================================================================
# 3. SOBRE LOS DATOS
# ==========================================================================

RUTAS = {"analitico": ruta("data/processed/dataset_analitico.csv"),
         "antes_despues": ruta("data/processed/antes_despues_kpis.csv")}
faltan = [p for p in RUTAS.values() if not os.path.exists(p)]
if faltan:
    print(f"Faltan archivos: {faltan}")
    print("Correr el pipeline hasta py src/kpis.py")
    sys.exit(1)

df = pd.read_csv(RUTAS["analitico"], encoding="utf-8-sig", low_memory=False)
ad = pd.read_csv(RUTAS["antes_despues"], encoding="utf-8-sig")
v = df[df["rent_bruta_pct"].notna()]
ok = v[v["estimacion_confiable"] == 1]

antes = ad.loc[ad["escenario"].str.startswith("antes"), "mediana_pct"].iloc[0]
check("el escenario ABL plano reproduce la neta mediana de la 2da entrega (5,67%)",
      abs(antes - 5.67) < 0.005, f"{antes}")
check("ABL: positivo en toda venta con KPI", (v["abl_pct"] > 0).all() and (v["abl_ars_mes"] > 0).all())
check("ABL: no supera el 1% anual del valor de mercado (art. 45)",
      (v["abl_ars_mes"] * 12 <= v["venta_usd"] * S.TC_ARS_USD * S.ABL_TOPE_SOBRE_MERCADO + 1).all())
check("costos de entrada: entre el base sin sellos y el alto con sellos generales",
      v["costos_entrada_pct"].between(fijo, S.COMISION_COMPRADOR_PCT[1] + S.ESCRIBANO_PCT[1]
                                      + S.REGISTRALES_PCT[1] + S.SELLOS_ALICUOTA_PCT / 2).all())
check("refaccion: solo en unidades a reciclar",
      ((v["refaccion_usd"] > 0) == (v["a_reciclar"] == 1)).all())
check("alquiler post-refaccion: solo en unidades a reciclar",
      (v["alquiler_post_refaccion_usd_mes"].notna() == (v["a_reciclar"] == 1)).all())
sin_rec = v[v["a_reciclar"] == 0]
check("TIR menor que la neta en toda unidad que no se refacciona (los costos de entrada restan)",
      (sin_rec["tir_5a_pct"] < sin_rec["rent_neta_pct"]).all())
check("las columnas nuevas estan vacias en los alquileres",
      df.loc[df["operacion"] == "alquiler", ["abl_pct", "tir_5a_pct", "costos_entrada_pct"]].isna().all().all())


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
