#!/usr/bin/env python
"""
comparacion_modelos.py — El modelo de alquiler contra una referencia simple y
contra dos alternativas, todo fuera de muestra con el mismo esquema.

POR QUE
-------
La consigna pide que un modelo predictivo se compare con una referencia
razonable y se evalue fuera de muestra. Cuatro modelos:

  mediana barrio x tramo   la referencia: alquiler/m2 mediano de la celda del
                           barrio y tramo de superficie, por la superficie
  ridge                    el modelo vigente, 21 predictoras
  ridge + espaciales       el mismo, con las distancias de espacial.py
  boosting                 gradient boosting con las mismas variables que el
                           anterior, afinado por validacion cruzada interna

Cada uno se evalua con KFold de 5 particiones en tres semillas: la del modelo
vigente y dos mas, para ver si las diferencias son senial o ruido de la
particion. La referencia se calcula dentro de cada fold, para que tampoco vea
los datos que predice.

EL CRITERIO
-----------
No se elige el mejor numero. Un modelo reemplaza al Ridge solo si mejora el
R2 en al menos supuestos.MEJORA_MINIMA_R2 en todas las semillas: los
coeficientes del Ridge se leen como variaciones porcentuales y alimentan el
informe, y eso no se cambia por una mejora que la particion puede borrar.

Tambien compara la banda del KPI 4 de la 2da entrega (error mediano del
tramo) con la de esta (regresion cuantilica calibrada, kpis.py): cuantos
alquileres observados caen adentro de cada una.

Uso:
    py src/comparacion_modelos.py      # unos 4 minutos, por el boosting

Salidas:
    data/processed/comparacion_modelos.csv         una fila por modelo y semilla
    data/processed/reporte_comparacion_modelos.txt log
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GridSearchCV, KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

import modelo_alquiler as M
import supuestos as S
from fuentes_externas import Reporte


ENTRADA = "data/processed/dataset_espacial.csv"
MODELO = "data/processed/modelo_alquiler.joblib"
SALIDA = "data/processed/comparacion_modelos.csv"
REPORTE = "data/processed/reporte_comparacion_modelos.txt"

SEMILLAS = [M.SEMILLA_CV, 7, 2026]
ESPACIALES = ["dist_subte_m", "dist_tren_m", "dist_metrobus_m", "dist_transporte_m",
              "dist_plaza_m", "dist_parque_m"]
# Grilla chica del boosting: 16 combinaciones, elegidas por validacion
# cruzada interna de 3 particiones dentro de cada fold externo.
GRILLA_BOOSTING = {
    "mod__learning_rate": [0.03, 0.1],
    "mod__max_leaf_nodes": [7, 31],
    "mod__min_samples_leaf": [10, 30],
    "mod__l2_regularization": [0.0, 1.0],
}


# ==========================================================================
# MODELOS
# ==========================================================================

def ridge_espacial() -> Pipeline:
    """El Ridge vigente con las distancias como numericas mas."""
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]),
         M.NUMERICAS + ESPACIALES),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), M.CATEGORICAS),
        ("dum", "passthrough", M.DUMMIES),
    ])
    return Pipeline([("pre", pre), ("mod", RidgeCV(alphas=np.logspace(-2, 3, 30)))])


def boosting() -> GridSearchCV:
    """Gradient boosting con categoricas nativas, afinado por CV interna."""
    pre = ColumnTransformer([("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                              M.CATEGORICAS)], remainder="passthrough")
    pipe = Pipeline([("pre", pre),
                     ("mod", HistGradientBoostingRegressor(random_state=0, categorical_features=[0, 1]))])
    return GridSearchCV(pipe, GRILLA_BOOSTING, cv=KFold(3, shuffle=True, random_state=0),
                        scoring="neg_mean_squared_error", n_jobs=-1)


def referencia(alq: pd.DataFrame, kf: KFold) -> np.ndarray:
    """
    log del alquiler predicho por la mediana del alquiler/m2 de la celda
    barrio x tramo, calculada solo con los alquileres de entrenamiento de cada
    fold. Celda vacia: la del barrio; barrio vacio: la de toda la muestra.
    """
    tramo = pd.cut(alq["sup_total_m2"], M.BINS_SUP, labels=M.LAB_SUP).astype(str)
    m2 = alq["alquiler_usd_mes"] / alq["sup_total_m2"]
    pred = np.zeros(len(alq))
    for tr, te in kf.split(alq):
        celda = m2.iloc[tr].groupby([alq["barrio"].iloc[tr], tramo.iloc[tr]]).median()
        barrio = m2.iloc[tr].groupby(alq["barrio"].iloc[tr]).median()
        todos = m2.iloc[tr].median()
        v = [celda.get((b, t), barrio.get(b, todos))
             for b, t in zip(alq["barrio"].iloc[te], tramo.iloc[te])]
        pred[te] = np.log(np.asarray(v) * alq["sup_total_m2"].iloc[te].values)
    return pred


# ==========================================================================
# METRICAS
# ==========================================================================

def metricas(alq: pd.DataFrame, y: np.ndarray, pred_log: np.ndarray) -> dict:
    """R2 en log, error relativo mediano y su apertura por tramo de superficie."""
    real = alq["alquiler_usd_mes"].values
    err = np.abs(np.exp(pred_log) - real) / real
    tramo = pd.cut(alq["sup_total_m2"], M.BINS_SUP, labels=M.LAB_SUP)
    por_tramo = pd.Series(err).groupby(tramo.values, observed=True).median()
    return {"r2_log": 1 - ((y - pred_log) ** 2).sum() / ((y - y.mean()) ** 2).sum(),
            "error_mediano_pct": float(np.median(err) * 100),
            **{f"error_{t}_pct": float(por_tramo[t] * 100) for t in M.LAB_SUP}}


def cobertura_banda_anterior(alq: pd.DataFrame, y: np.ndarray, kf: KFold) -> float:
    """
    La banda de la 2da entrega: estimacion +- error relativo mediano de su
    tramo. Por construccion (es una mediana), deja afuera a la mitad.
    """
    pred = cross_val_predict(M.construir_pipeline(), alq[M.NUMERICAS + M.CATEGORICAS + M.DUMMIES], y, cv=kf)
    real = alq["alquiler_usd_mes"].values
    err = np.abs(np.exp(pred) - real) / real
    tramo = pd.cut(alq["sup_total_m2"], M.BINS_SUP, labels=M.LAB_SUP)
    err_tramo = pd.Series(err).groupby(tramo.values, observed=True).transform("median").values
    return float((err <= err_tramo).mean())


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> int:
    for p in (ENTRADA, MODELO):
        if not os.path.exists(p):
            print(f"No existe {p}. Correr el pipeline hasta py src/kpis.py")
            return 1

    rep = Reporte()
    rep.titulo("MODELO DE ALQUILER: COMPARACION FUERA DE MUESTRA")
    rep(f"Fecha: {datetime.now():%Y-%m-%d %H:%M}")

    df = M.preparar(pd.read_csv(ENTRADA, encoding="utf-8-sig", low_memory=False))
    alq = df[df["operacion"] == "alquiler"].dropna(
        subset=["alquiler_usd_mes", "sup_total_m2", "barrio"]).reset_index(drop=True)
    y = np.log(alq["alquiler_usd_mes"].values)
    X21 = alq[M.NUMERICAS + M.CATEGORICAS + M.DUMMIES]
    XE = alq[M.CATEGORICAS + M.NUMERICAS + ESPACIALES + M.DUMMIES]
    rep(f"Alquileres: {len(alq):,}. Esquema: KFold({M.N_FOLDS}) en las semillas {SEMILLAS}.")

    filas = []
    for semilla in SEMILLAS:
        kf = KFold(M.N_FOLDS, shuffle=True, random_state=semilla)
        preds = {
            "mediana barrio x tramo": referencia(alq, kf),
            "ridge": cross_val_predict(M.construir_pipeline(), X21, y, cv=kf),
            "ridge + espaciales": cross_val_predict(ridge_espacial(), XE, y, cv=kf),
            "boosting": cross_val_predict(boosting(), XE, y, cv=kf),
        }
        for modelo, p in preds.items():
            filas.append({"modelo": modelo, "semilla": semilla, **metricas(alq, y, p)})
        rep(f"    semilla {semilla}: lista")
    t = pd.DataFrame(filas)

    rep.titulo("TABLA COMPARATIVA (promedio de las tres semillas; entre corchetes, minimo y maximo)")
    orden = ["mediana barrio x tramo", "ridge", "ridge + espaciales", "boosting"]
    rep(f"    {'modelo':<24}{'R2 en log':>24}{'error mediano':>24}")
    for m in orden:
        g = t[t["modelo"] == m]
        rep(f"    {m:<24}{g['r2_log'].mean():>10.4f} [{g['r2_log'].min():.4f}, {g['r2_log'].max():.4f}]"
            f"{g['error_mediano_pct'].mean():>9.2f}% [{g['error_mediano_pct'].min():.2f}, "
            f"{g['error_mediano_pct'].max():.2f}]")
    rep("")
    rep("Error relativo mediano por tramo de superficie (promedio de las semillas):")
    rep(f"    {'modelo':<24}" + "".join(f"{s:>9}" for s in M.LAB_SUP))
    for m in orden:
        g = t[t["modelo"] == m]
        rep(f"    {m:<24}" + "".join(f"{g[f'error_{s}_pct'].mean():>8.1f}%" for s in M.LAB_SUP))

    # La decision, armada con las cifras de la tabla.
    rep.titulo("DECISION")
    base = t[t["modelo"] == "ridge"].set_index("semilla")["r2_log"]
    ref = t[t["modelo"] == "mediana barrio x tramo"].set_index("semilla")["r2_log"]
    rep(f"Contra la referencia, el Ridge gana {(base - ref).min():+.4f} a {(base - ref).max():+.4f} de R2 "
        f"segun la semilla.")
    reemplaza = None
    for m in ["ridge + espaciales", "boosting"]:
        d = t[t["modelo"] == m].set_index("semilla")["r2_log"] - base
        rep(f"{m}: {d.min():+.4f} a {d.max():+.4f} de R2 contra el Ridge "
            f"(criterio: {S.MEJORA_MINIMA_R2:+.2f} en todas las semillas).")
        if (d >= S.MEJORA_MINIMA_R2).all() and reemplaza is None:
            reemplaza = m
    rep("")
    if reemplaza is None:
        rep("Ninguna alternativa cumple el criterio: el modelo vigente sigue siendo el Ridge de")
        rep("21 predictoras, y los KPIs no cambian. Sus coeficientes se leen como variaciones")
        rep("porcentuales del alquiler, y ninguna mejora observada paga perder eso.")
    else:
        rep(f"{reemplaza} cumple el criterio y deberia reemplazar al Ridge en kpis.py.")

    rep.titulo("BANDA DEL KPI 4: ANTES Y DESPUES")
    kf = KFold(M.N_FOLDS, shuffle=True, random_state=M.SEMILLA_CV)
    anterior = cobertura_banda_anterior(alq, y, kf)
    banda = joblib.load(MODELO)["banda"]
    rep(f"Alquileres observados dentro de la banda, fuera de muestra:")
    rep(f"    2da entrega, estimacion +- error mediano del tramo : {anterior:.1%}")
    rep(f"    3ra entrega, percentiles 10 y 90 calibrados       : {banda['cobertura_calibrada']:.1%}"
        f"  (objetivo {M.COBERTURA_OBJETIVO:.0%})")
    rep("La banda anterior era un rango del 50% por construccion: decia 'el alquiler esta entre")
    rep("estos dos valores' y acertaba la mitad de las veces. La nueva es mas ancha porque cubre")
    rep("lo que dice cubrir.")

    t.round(4).to_csv(SALIDA, index=False, encoding="utf-8-sig")
    rep("")
    rep(f"Archivo: {SALIDA} ({len(t)} filas)")
    with open(REPORTE, "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
