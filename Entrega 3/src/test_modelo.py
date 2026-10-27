#!/usr/bin/env python
"""
test_modelo.py — Tests de la banda cuantilica, de la metadata del modelo y de
la comparacion contra la referencia.

Lo que cubre:
  1. Sin datos: la calibracion conformal cubre lo que promete sobre un caso
     sintetico donde la banda cruda es demasiado angosta, la perdida pinball y
     los grupos de evidencia.
  2. Sobre los datos: que el .joblib traiga su metadata y que el hash
     coincida con los alquileres de entrada (si no, el modelo es de otra
     corrida); que la banda del dataset sea coherente con la estimacion; y que
     la comparacion tenga todos los modelos y semillas.

Uso:
    py src/test_modelo.py
"""

import hashlib
import os
import sys

import joblib
import numpy as np
import pandas as pd

import modelo_alquiler as M


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


# ==========================================================================
# 1. SIN DATOS
# ==========================================================================

rng = np.random.default_rng(3)
n = 4000
y = rng.normal(0, 1, n)
# Banda cruda demasiado angosta: +-0,8 cubre ~58% de una normal, no 80%.
lo, hi = np.full(n, -0.8), np.full(n, 0.8)
grupo = np.where(np.arange(n) < n / 2, "10-29", "100+")
aj = M.ajuste_conformal(y, lo, hi, grupo)
cruda = ((y >= lo) & (y <= hi)).mean()
nueva = np.array([aj[g] for g in grupo])
calibrada = ((y >= lo - nueva) & (y <= hi + nueva)).mean()
check("NEG: la banda cruda del caso sintetico cubre de menos", cruda < 0.65, f"{cruda:.3f}")
check("conformal: la banda calibrada cubre al menos el 80%", calibrada >= M.COBERTURA_OBJETIVO, f"{calibrada:.3f}")
check("conformal: y no mucho mas (no ensancha de mas)", calibrada < M.COBERTURA_OBJETIVO + 0.02, f"{calibrada:.3f}")
check("conformal: un grupo sin observaciones usa el ajuste de todos",
      aj["<10"] == aj["30-99"] and np.isfinite(aj["<10"]))
ancha = M.ajuste_conformal(y, np.full(n, -3.0), np.full(n, 3.0), grupo)
check("conformal: una banda demasiado ancha se angosta (ajuste negativo)", ancha["100+"] < 0, f"{ancha}")

check("pinball con cuantil 0,5 = la mitad del error absoluto medio",
      abs(M.perdida_pinball(y, np.zeros(n), 0.5) - np.abs(y).mean() / 2) < 1e-12)
g = M.grupo_evidencia(pd.Series([0, 9, 10, 29, 30, 99, 100, np.nan]))
check("grupos de evidencia: cortes en 10, 30 y 100, nulo como sin evidencia",
      list(g) == ["<10", "<10", "10-29", "10-29", "30-99", "30-99", "100+", "<10"], f"{list(g)}")


# ==========================================================================
# 2. SOBRE LOS DATOS
# ==========================================================================

RUTAS = {"modelo": ruta("data/processed/modelo_alquiler.joblib"),
         "entrada": ruta("data/processed/dataset_espacial.csv"),
         "analitico": ruta("data/processed/dataset_analitico.csv"),
         "comparacion": ruta("data/processed/comparacion_modelos.csv")}
faltan = [p for p in RUTAS.values() if not os.path.exists(p)]
if faltan:
    print(f"Faltan archivos: {faltan}")
    print("Correr el pipeline hasta py src/kpis.py y py src/comparacion_modelos.py")
    sys.exit(1)

m = joblib.load(RUTAS["modelo"])
meta = m.get("metadata", {})
for clave in ["sklearn", "entrenado", "hash_entrenamiento_sha256", "predictoras",
              "metricas_validacion", "cobertura_banda", "n_entrenamiento"]:
    check(f"metadata del .joblib: trae '{clave}'", clave in meta)

df = M.preparar(pd.read_csv(RUTAS["entrada"], encoding="utf-8-sig", low_memory=False))
alq = df[df["operacion"] == "alquiler"].dropna(subset=["alquiler_usd_mes", "sup_total_m2", "barrio"])
cols = M.NUMERICAS + M.CATEGORICAS + M.DUMMIES
h = hashlib.sha256(alq[cols + ["alquiler_usd_mes"]].to_csv(index=False).encode("utf-8")).hexdigest()
check("metadata: el hash coincide con los alquileres de entrada (el modelo es de esta corrida)",
      meta.get("hash_entrenamiento_sha256") == h)
check("NEG: con un alquiler cambiado, el hash ya no coincide",
      hashlib.sha256(alq[cols + ["alquiler_usd_mes"]].assign(alquiler_usd_mes=alq["alquiler_usd_mes"] + 1)
                     .to_csv(index=False).encode("utf-8")).hexdigest() != h)
cob = meta.get("cobertura_banda", {})
check("metadata: cobertura calibrada de la banda dentro de 3 pp del objetivo",
      abs(cob.get("calibrada", 0) - M.COBERTURA_OBJETIVO) <= 0.03, f"{cob}")

a = pd.read_csv(RUTAS["analitico"], encoding="utf-8-sig", low_memory=False)
v = a[a["rent_bruta_pct"].notna()]
check("banda: p10 < p90 en toda venta", (v["alquiler_p10_usd_mes"] < v["alquiler_p90_usd_mes"]).all())
check("banda: la estimacion puntual cae dentro de su banda",
      ((v["alquiler_est_usd_mes"] >= v["alquiler_p10_usd_mes"])
       & (v["alquiler_est_usd_mes"] <= v["alquiler_p90_usd_mes"])).mean() > 0.99)
check("banda: rent_bruta_min y max salen del p10 y el p90",
      np.allclose(v["rent_bruta_min"], (v["alquiler_p10_usd_mes"] * 12 / v["venta_usd"] * 100).round(2), atol=0.011)
      and np.allclose(v["rent_bruta_max"], (v["alquiler_p90_usd_mes"] * 12 / v["venta_usd"] * 100).round(2), atol=0.011))
check("la banda vieja ya no esta en el dataset", "error_estimacion" not in a.columns)
check("banda: vacia en los alquileres",
      a.loc[a["operacion"] == "alquiler", ["alquiler_p10_usd_mes", "alquiler_p90_usd_mes"]].isna().all().all())

c = pd.read_csv(RUTAS["comparacion"], encoding="utf-8-sig")
check("comparacion: 4 modelos x 3 semillas", len(c) == 12 and c["modelo"].nunique() == 4)
r = c.pivot(index="semilla", columns="modelo", values="r2_log")
check("comparacion: el Ridge le gana a la referencia en todas las semillas",
      (r["ridge"] > r["mediana barrio x tramo"]).all())
check("comparacion: la semilla del modelo vigente reproduce su R2",
      abs(r.loc[M.SEMILLA_CV, "ridge"] - meta["metricas_validacion"]["r2_log"]) < 0.0005)


print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
