"""
modelo_alquiler.py — Estima el alquiler esperado de cada propiedad en venta
y calcula su rentabilidad.

EL PROBLEMA QUE RESUELVE
------------------------
El dataset tiene ~8 ventas por cada alquiler. Para calcular la rentabilidad de
una propiedad en venta hace falta saber cuanto se alquilaria, pero esa propiedad
no esta publicada en alquiler.

Tres formas de estimarlo, de peor a mejor:

  1. Mediana de barrio x ambientes -> solo el 28% de las ventas cae en una celda
     con 20+ alquileres. No alcanza.
  2. Mediana del barrio x m2 -> cubre 85%, error ~14%. Ignora antiguedad,
     amenities y todo lo demas.
  3. Modelo de regresion -> usa las ~1.350 observaciones JUNTAS en vez de
     partirlas en celdas chicas. Cubre el 100% y da el menor error de las
     tres (el valor vigente esta en data/processed/reporte_kpis.txt).

Este modulo implementa la opcion 3, con la 2 como referencia de control.

POR QUE log(alquiler) Y NO alquiler
-----------------------------------
El precio inmobiliario es multiplicativo, no aditivo: un balcon no suma "USD 80",
suma "un 8% mas". Modelar el logaritmo captura eso, estabiliza la varianza
(la dispersion crece con el precio) y hace que los coeficientes se lean
directamente como variaciones porcentuales.

Al predecir hay que volver a la escala original. Como E[exp(X)] != exp(E[X]),
se aplica la correccion de Duan (smearing), que evita subestimar sistematicamente.

No se ejecuta solo: lo orquesta kpis.py, que le pasa la vacancia y los gastos
de supuestos.py y persiste el modelo entrenado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import QuantileRegressor, RidgeCV
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# ==========================================================================
# CONFIGURACION
# ==========================================================================

# Variables predictoras. Se eligieron por disponibilidad (>95% de completitud)
# y por tener sentido economico, no por busqueda automatica: un modelo que hay
# que defender en un informe se explica mejor si las variables son justificables.
NUMERICAS = ["log_sup", "ambientes", "banos", "dormitorios", "antiguedad_anios"]
CATEGORICAS = ["barrio", "tipo_familia"]
DUMMIES = [
    "balcon", "cochera_txt", "amenities", "ascensor", "aire_acondicionado",
    "pileta", "amoblado", "parrilla", "seguridad", "baulera", "luminoso",
    "patio_jardin", "a_reciclar", "reciclado",
]

# Minimo de alquileres en un barrio para confiar en su estimacion.
# Por debajo, el modelo extrapola desde otros barrios y hay que marcarlo.
MIN_ALQ_BARRIO = 10

# Segmentos de superficie usados para medir el error de forma diferenciada.
# El error del modelo NO es uniforme: crece con el tamanio de la propiedad.
BINS_SUP = [0, 35, 50, 70, 100, 10000]
LAB_SUP = ["<35", "35-50", "50-70", "70-100", "100+"]

# Validacion cruzada: la misma particion para el modelo, la banda y la
# comparacion contra otros modelos (comparacion_modelos.py).
SEMILLA_CV = 42
N_FOLDS = 5

# Banda del KPI 4: percentiles 10 y 90 del alquiler. Si esta bien calibrada,
# el 80% de los alquileres observados cae adentro.
CUANTILES_BANDA = (0.10, 0.90)
COBERTURA_OBJETIVO = CUANTILES_BANDA[1] - CUANTILES_BANDA[0]
# Penalizacion L1 de la regresion cuantilica: se elige por perdida pinball
# fuera de muestra entre estos valores.
ALPHAS_CUANTIL = [0.0, 0.0005, 0.001, 0.002, 0.005]
# Grupos de evidencia: cuantos alquileres observados tiene el barrio. La
# calibracion de la banda se hace por separado en cada grupo, para que se
# ensanche donde hay menos datos. El primer corte es MIN_ALQ_BARRIO.
CORTES_EVIDENCIA = [0, MIN_ALQ_BARRIO, 30, 100, np.inf]
GRUPOS_EVIDENCIA = ["<10", "10-29", "30-99", "100+"]


# ==========================================================================
# UTILIDADES
# ==========================================================================

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

    def guardar(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lineas))


def preparar(df: pd.DataFrame) -> pd.DataFrame:
    """Crea las columnas derivadas que necesita el modelo."""
    df = df.copy()
    df["log_sup"] = np.log(df["sup_total_m2"].where(df["sup_total_m2"] > 0))
    for c in DUMMIES:
        if c not in df.columns:
            df[c] = 0
    return df


def construir_pipeline() -> Pipeline:
    """
    Preprocesamiento + modelo.

    RidgeCV elige solo el nivel de regularizacion por validacion cruzada.
    La regularizacion importa porque `barrio` genera ~48 dummies y varios
    barrios tienen pocas observaciones: sin penalizacion, el modelo les
    ajustaria ruido.
    """
    pre = ColumnTransformer([
        ("num", Pipeline([
            ("imp", SimpleImputer(strategy="median")),
            ("esc", StandardScaler()),
        ]), NUMERICAS),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5), CATEGORICAS),
        ("dum", "passthrough", DUMMIES),
    ])
    return Pipeline([
        ("pre", pre),
        ("mod", RidgeCV(alphas=np.logspace(-2, 3, 30))),
    ])


def factor_smearing(residuos: np.ndarray) -> float:
    """
    Correccion de Duan para volver de log a la escala original.

    exp(prediccion_en_log) subestima la media porque la transformacion es
    convexa. El factor es el promedio de exp(residuos) y corrige ese sesgo
    sin asumir normalidad.
    """
    return float(np.mean(np.exp(residuos)))


# ==========================================================================
# ENTRENAMIENTO Y VALIDACION
# ==========================================================================

def entrenar_y_validar(alq: pd.DataFrame, rep: Reporte):
    """
    Entrena el modelo y reporta su desempeño fuera de muestra.

    Devuelve el pipeline final, el factor de smearing y las metricas de
    validacion, que viajan como metadata en el .joblib.
    """
    X = alq[NUMERICAS + CATEGORICAS + DUMMIES]
    y = np.log(alq["alquiler_usd_mes"])

    pipe = construir_pipeline()
    kf = KFold(N_FOLDS, shuffle=True, random_state=SEMILLA_CV)

    rep.titulo("VALIDACION DEL MODELO (5-fold, fuera de muestra)")
    rep(f"Observaciones de entrenamiento : {len(alq):,}")
    rep(f"Variables                      : {len(NUMERICAS)} numericas, "
        f"{len(CATEGORICAS)} categoricas, {len(DUMMIES)} dicotomicas")
    rep("")

    # cross_val_predict garantiza que cada prediccion venga de un modelo
    # que NO vio esa fila: es la unica forma honesta de medir el error.
    pred_log = cross_val_predict(pipe, X, y, cv=kf)
    real = alq["alquiler_usd_mes"].values
    est = np.exp(pred_log)

    ss_res = float(((y - pred_log) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot

    err_rel = np.abs(est - real) / real
    rep(f"R2 (en log)                    : {r2:.3f}")
    rep(f"Error relativo mediano         : {np.median(err_rel)*100:.1f}%")
    rep(f"Error relativo medio           : {err_rel.mean()*100:.1f}%")
    rep(f"Predicciones con error < 10%   : {(err_rel < .10).mean()*100:.1f}%")
    rep(f"Predicciones con error < 20%   : {(err_rel < .20).mean()*100:.1f}%")
    rep(f"Predicciones con error > 50%   : {(err_rel > .50).mean()*100:.1f}%")

    # --- Referencia de control: mediana del barrio por m2 ---
    med = alq.groupby("barrio")["alquiler_m2_usd_mes"].transform("median")
    est_simple = (med * alq["sup_total_m2"]).values
    ok = ~np.isnan(est_simple)
    err_simple = np.abs(est_simple[ok] - real[ok]) / real[ok]
    rep("")
    rep(f"Control — mediana barrio x m2  : {np.median(err_simple)*100:.1f}% "
        f"(y es optimista: se calcula dentro de la misma muestra)")
    mejora = (np.median(err_simple) - np.median(err_rel)) / np.median(err_simple) * 100
    rep(f"Mejora del modelo              : {mejora:.0f}%")

    # --- Error POR SEGMENTO DE SUPERFICIE ---
    #
    # Importante: el error global esta calculado sobre la mezcla de ALQUILERES,
    # que son sistematicamente mas chicos que las ventas (mediana 45 vs 66 m2).
    # Como el error crece con el tamanio, el error global subestima el de las
    # ventas. Hasta la 2da entrega la banda del KPI 4 salia de esta tabla; desde
    # la 3ra sale de banda_cuantilica(), y esta queda como diagnostico.
    tmp = alq.copy()
    tmp["_err"] = err_rel
    tmp["_seg"] = pd.cut(tmp["sup_total_m2"], BINS_SUP, labels=LAB_SUP)
    err_seg = tmp.groupby("_seg", observed=True)["_err"].median()

    rep("")
    rep("Error por segmento de superficie:")
    rep(f"    {'segmento':<12}{'n':>6}{'error':>9}")
    for s in LAB_SUP:
        if s in err_seg.index:
            n = int((tmp["_seg"] == s).sum())
            rep(f"    {s:<12}{n:>6}{err_seg[s]*100:>8.1f}%")
    rep("")
    rep("    El error crece con la superficie. Como las ventas son mas grandes")
    rep("    que los alquileres, el error real sobre las ventas es mayor que el")
    rep("    global: un error unico subestimaria la incertidumbre.")

    # --- Factor de smearing ---
    #
    # Se calcula con los residuos OUT-OF-FOLD (los de cross_val_predict), no con
    # los del modelo ya ajustado. Duan lo define con residuos in-sample, pero
    # esos son artificialmente chicos: el modelo vio esas filas al entrenar.
    # Como el factor es mean(exp(residuo)), subestimarlos subestima la correccion.
    # La diferencia aca es minima (~0.02%), pero usar los honestos no cuesta nada
    # y evita una objecion metodologica.
    smear = factor_smearing((y - pred_log).values)

    # Modelo FINAL entrenado con todos los datos.
    # Esto es deliberado: las metricas de arriba ya se midieron fuera de muestra,
    # asi que para el modelo que se guarda y se usa en produccion conviene
    # aprovechar las 1.348 observaciones y no solo el 80% de un fold.
    pipe.fit(X, y)

    rep("")
    rep(f"Factor de smearing (Duan)      : {smear:.4f}   (residuos out-of-fold)")

    metricas = {
        "esquema": f"KFold({N_FOLDS}, shuffle=True, random_state={SEMILLA_CV})",
        "r2_log": round(r2, 4),
        "error_relativo_mediano": round(float(np.median(err_rel)), 4),
        "error_por_tramo": {str(k): round(float(v), 4) for k, v in err_seg.items()},
        "smearing": round(smear, 4),
    }
    return pipe, smear, metricas


def reportar_coeficientes(pipe: Pipeline, rep: Reporte) -> None:
    """
    Traduce los coeficientes a efectos porcentuales legibles.

    Como el target es log(alquiler), un coeficiente b se lee como
    (exp(b) - 1) * 100 por ciento de variacion.
    """
    rep.titulo("EFECTO DE CADA VARIABLE SOBRE EL ALQUILER")
    rep("Lectura: cuanto varia el alquiler esperado, en %, ante la presencia")
    rep("de la caracteristica (dummies) o un desvio estandar mas (numericas).")
    rep("")

    pre = pipe.named_steps["pre"]
    coefs = pipe.named_steps["mod"].coef_
    nombres = list(pre.get_feature_names_out())

    efectos = [(n.split("__")[-1], (np.exp(c) - 1) * 100) for n, c in zip(nombres, coefs)]

    # Las de barrio se listan aparte: son ~48 y tienen otra interpretacion
    barrios = [(n.replace("barrio_", ""), e) for n, e in efectos if n.startswith("barrio_")]
    resto = [(n, e) for n, e in efectos if not n.startswith("barrio_")]

    resto.sort(key=lambda x: -abs(x[1]))
    rep("Caracteristicas del inmueble:")
    for n, e in resto[:18]:
        signo = "+" if e >= 0 else ""
        rep(f"    {n:<26} {signo}{e:>6.1f}%")

    barrios.sort(key=lambda x: -x[1])
    rep("")
    rep("Barrios que mas suman (vs. el promedio):")
    for n, e in barrios[:8]:
        rep(f"    {n:<26} +{e:>6.1f}%")
    rep("")
    rep("Barrios que mas restan:")
    for n, e in barrios[-8:]:
        rep(f"    {n:<26} {e:>7.1f}%")


# ==========================================================================
# BANDA DE INCERTIDUMBRE: REGRESION CUANTILICA CONFORMALIZADA
# ==========================================================================
#
# El KPI 4 necesita, para cada propiedad, un rango donde caiga su alquiler. Dos
# pasos:
#   1. Regresion cuantilica lineal de los percentiles 10 y 90, con el mismo
#      preprocesamiento que el Ridge: la banda cambia con las caracteristicas
#      del inmueble.
#   2. Calibracion conformal por grupo de evidencia (CQR, Romano, Patterson y
#      Candes, 2019): la regresion cuantilica mide la dispersion de los
#      alquileres, no cuantos datos hay detras de cada barrio, asi que su
#      ancho no depende de la evidencia. La calibracion corrige la banda de
#      cada grupo por separado hasta que cubra el 80% fuera de muestra: si un
#      grupo se predice peor, se ensancha mas.
# No mejora la estimacion puntual: mejora lo que se sabe de su confianza.

def pipeline_cuantil(cuantil: float, alpha: float) -> Pipeline:
    """El preprocesamiento del Ridge, con regresion cuantilica lineal."""
    p = construir_pipeline()
    p.steps[-1] = ("mod", QuantileRegressor(quantile=cuantil, alpha=alpha, solver="highs"))
    return p


def grupo_evidencia(n_alq: pd.Series) -> pd.Series:
    """Grupo segun cuantos alquileres observados tiene el barrio."""
    return pd.cut(n_alq.fillna(0), CORTES_EVIDENCIA, labels=GRUPOS_EVIDENCIA, right=False).astype(str)


def perdida_pinball(y: np.ndarray, pred: np.ndarray, cuantil: float) -> float:
    """La perdida que minimiza la regresion cuantilica: la usada para elegir alpha."""
    d = y - pred
    return float(np.mean(np.maximum(cuantil * d, (cuantil - 1) * d)))


def _cuantiles_fuera_de_muestra(X, y, alpha: float, kf) -> tuple[np.ndarray, np.ndarray]:
    lo = cross_val_predict(pipeline_cuantil(CUANTILES_BANDA[0], alpha), X, y, cv=kf)
    hi = cross_val_predict(pipeline_cuantil(CUANTILES_BANDA[1], alpha), X, y, cv=kf)
    return lo, hi


def ajuste_conformal(y: np.ndarray, lo: np.ndarray, hi: np.ndarray, grupo: np.ndarray) -> dict:
    """
    Cuanto ensanchar la banda (en log) en cada grupo para cubrir el 80%.

    El puntaje de cada observacion es cuanto quedo afuera de su banda fuera
    de muestra (negativo si cayo adentro). El ajuste es su cuantil
    ceil((n + 1) x 0,8) / n, que garantiza la cobertura con n finito. Un grupo
    sin observaciones usa el ajuste de todos juntos.
    """
    puntaje = np.maximum(lo - y, y - hi)

    def cuantil(s: np.ndarray) -> float:
        k = min(np.ceil((len(s) + 1) * COBERTURA_OBJETIVO) / len(s), 1.0)
        return float(np.quantile(s, k, method="higher"))

    global_ = cuantil(puntaje)
    return {g: cuantil(puntaje[grupo == g]) if (grupo == g).any() else global_
            for g in GRUPOS_EVIDENCIA}


def banda_cuantilica(alq: pd.DataFrame, vta: pd.DataFrame, rep: Reporte):
    """
    Percentiles 10 y 90 del alquiler de cada venta, calibrados.

    Devuelve las dos columnas en USD y un diccionario con lo necesario para
    reproducir la banda (alpha, modelos, ajustes) y sus coberturas.
    """
    rep.titulo("BANDA DE INCERTIDUMBRE (KPI 4): REGRESION CUANTILICA CONFORMALIZADA")
    cols = NUMERICAS + CATEGORICAS + DUMMIES
    X, y = alq[cols], np.log(alq["alquiler_usd_mes"]).values
    kf = KFold(N_FOLDS, shuffle=True, random_state=SEMILLA_CV)
    q_lo, q_hi = CUANTILES_BANDA

    # 1. Penalizacion por perdida pinball fuera de muestra.
    perdidas, oof = {}, {}
    for a in ALPHAS_CUANTIL:
        lo, hi = _cuantiles_fuera_de_muestra(X, y, a, kf)
        perdidas[a] = perdida_pinball(y, lo, q_lo) + perdida_pinball(y, hi, q_hi)
        oof[a] = (lo, hi)
    alpha = min(perdidas, key=perdidas.get)
    lo, hi = oof[alpha]
    rep("Penalizacion L1 (perdida pinball fuera de muestra, menor es mejor):")
    for a, p in perdidas.items():
        rep(f"    alpha {a:<7} {p:.5f}" + ("   <- elegida" if a == alpha else ""))

    n_barrio = alq.groupby("barrio")["barrio"].transform("size")
    grupo = grupo_evidencia(n_barrio).values
    cruda = (y >= lo) & (y <= hi)

    # 2. Cobertura de la banda calibrada, sin hacer trampa: el ajuste de cada
    # fold externo se calcula solo con los alquileres de entrenamiento.
    calibrada = np.zeros(len(alq), dtype=bool)
    for tr, te in kf.split(X):
        lo_i, hi_i = _cuantiles_fuera_de_muestra(X.iloc[tr], y[tr], alpha, kf)
        n_tr = alq.iloc[tr].groupby("barrio").size()
        aj = ajuste_conformal(y[tr], lo_i, hi_i, grupo_evidencia(alq["barrio"].iloc[tr].map(n_tr)).values)
        d = grupo_evidencia(alq["barrio"].iloc[te].map(n_tr)).map(aj).values
        m_lo = pipeline_cuantil(q_lo, alpha).fit(X.iloc[tr], y[tr])
        m_hi = pipeline_cuantil(q_hi, alpha).fit(X.iloc[tr], y[tr])
        calibrada[te] = ((y[te] >= m_lo.predict(X.iloc[te]) - d)
                         & (y[te] <= m_hi.predict(X.iloc[te]) + d))

    # 3. Modelos finales y ajuste con todos los alquileres.
    ajuste = ajuste_conformal(y, lo, hi, grupo)
    m_lo = pipeline_cuantil(q_lo, alpha).fit(X, y)
    m_hi = pipeline_cuantil(q_hi, alpha).fit(X, y)
    d = grupo_evidencia(vta["n_alq_barrio"]).map(ajuste).values
    a = m_lo.predict(vta[cols]) - d
    b = m_hi.predict(vta[cols]) + d
    banda = pd.DataFrame({"alquiler_p10_usd_mes": np.exp(np.minimum(a, b)).round(2),
                          "alquiler_p90_usd_mes": np.exp(np.maximum(a, b)).round(2)}, index=vta.index)

    rep("")
    rep(f"Cobertura fuera de muestra (objetivo {COBERTURA_OBJETIVO:.0%}): cruda {cruda.mean():.1%}, "
        f"calibrada {calibrada.mean():.1%}")
    rep(f"    {'grupo':<8}{'alquileres':>11}{'cruda':>9}{'calibrada':>11}{'ensanche':>10}"
        f"{'ancho p90/p10':>15}")
    for g in GRUPOS_EVIDENCIA:
        en = grupo == g
        ancho = np.exp(hi[en] - lo[en] + 2 * ajuste[g])
        rep(f"    {g:<8}{int(en.sum()):>11}{cruda[en].mean():>9.1%}{calibrada[en].mean():>11.1%}"
            f"{np.expm1(ajuste[g]):>+9.1%}{np.median(ancho):>14.2f}x")
    rep("")
    rep("cruda    : la regresion cuantilica sola. calibrada: con el ajuste de su grupo, medido")
    rep("           con validacion anidada. ensanche: cuanto se corre cada borde de la banda.")

    info = {"alpha": alpha, "cuantiles": CUANTILES_BANDA, "modelo_p10": m_lo, "modelo_p90": m_hi,
            "ajuste_log_por_grupo": ajuste, "cortes_evidencia": CORTES_EVIDENCIA,
            "cobertura_cruda": round(float(cruda.mean()), 4),
            "cobertura_calibrada": round(float(calibrada.mean()), 4),
            "cobertura_cruda_por_grupo": {g: round(float(cruda[grupo == g].mean()), 4)
                                          for g in GRUPOS_EVIDENCIA if (grupo == g).any()},
            "cobertura_calibrada_por_grupo": {g: round(float(calibrada[grupo == g].mean()), 4)
                                              for g in GRUPOS_EVIDENCIA if (grupo == g).any()},
            "alquileres_por_grupo": {g: int((grupo == g).sum()) for g in GRUPOS_EVIDENCIA}}
    return banda, info


# ==========================================================================
# IMPUTACION Y RENTABILIDAD
# ==========================================================================

def imputar(vta: pd.DataFrame, pipe: Pipeline, smear: float,
            cobertura: pd.Series, rep: Reporte) -> pd.DataFrame:
    """Estima el alquiler esperado de cada propiedad en venta."""
    rep.titulo("IMPUTACION DEL ALQUILER ESPERADO A LAS VENTAS")

    X = vta[NUMERICAS + CATEGORICAS + DUMMIES]
    vta = vta.copy()
    vta["alquiler_est_usd_mes"] = (np.exp(pipe.predict(X)) * smear).round(2)
    vta["alquiler_est_m2"] = (vta["alquiler_est_usd_mes"] / vta["sup_total_m2"]).round(2)

    # Marca de confianza: si el barrio tiene pocos alquileres, el modelo
    # extrapola desde otros barrios y la estimacion es mas fragil.
    vta["n_alq_barrio"] = vta["barrio"].map(cobertura).fillna(0).astype(int)
    vta["estimacion_confiable"] = (vta["n_alq_barrio"] >= MIN_ALQ_BARRIO).astype(int)

    rep(f"Propiedades estimadas          : {len(vta):,}")
    rep(f"Con estimacion confiable       : {int(vta['estimacion_confiable'].sum()):,} "
        f"({vta['estimacion_confiable'].mean()*100:.1f}%)")
    rep(f"En barrios con < {MIN_ALQ_BARRIO} alquileres  : "
        f"{int((1-vta['estimacion_confiable']).sum()):,}")
    rep("")
    rep(f"Alquiler estimado — mediana    : USD {vta['alquiler_est_usd_mes'].median():,.0f}/mes")
    rep(f"Alquiler estimado — rango p5-p95: USD "
        f"{vta['alquiler_est_usd_mes'].quantile(.05):,.0f} a "
        f"{vta['alquiler_est_usd_mes'].quantile(.95):,.0f}")
    return vta


def calcular_rentabilidad(vta: pd.DataFrame, vacancia: float, gastos: float | pd.Series,
                          rep: Reporte) -> pd.DataFrame:
    """
    Calcula los KPIs de rentabilidad.

    Rentabilidad Bruta Anual = (Alquiler mensual x 12) / Precio de venta

    Rentabilidad Neta Anual  = Bruta x (1 - vacancia) x (1 - gastos)

    Banda (KPI 4)            = la bruta con los percentiles 10 y 90 del
                               alquiler (columnas de banda_cuantilica)

    Nota sobre expensas: en CABA las ordinarias las paga el inquilino, por eso
    NO se descuentan del ingreso del propietario. Lo que si pesa es la vacancia
    (meses sin inquilino), la administracion, el ABL y las extraordinarias:
    todo eso esta agrupado en el parametro `gastos`, que es un numero para
    todas las propiedades o una serie con el de cada una (ABL segmentado).
    """
    rep.titulo("KPIs DE RENTABILIDAD")
    rep(f"Vacancia supuesta              : {vacancia:.1f}%")
    if isinstance(gastos, pd.Series):
        rep(f"Gastos del propietario         : por propiedad, mediana {gastos.median():.2f}% "
            f"(p10 {gastos.quantile(.1):.2f}%, p90 {gastos.quantile(.9):.2f}%)")
    else:
        rep(f"Gastos del propietario         : {gastos:.1f}%")
    rep("")

    v = vta.copy()
    v["rent_bruta_pct"] = (v["alquiler_est_usd_mes"] * 12 / v["venta_usd"] * 100).round(2)
    v["rent_neta_pct"] = (v["rent_bruta_pct"] * (1 - vacancia / 100)
                          * (1 - gastos / 100)).round(2)
    v["meses_repago"] = (v["venta_usd"] / v["alquiler_est_usd_mes"]).round(0)

    # Banda de incertidumbre de CADA propiedad: los percentiles 10 y 90 de su
    # alquiler, pasados a rentabilidad bruta con su propio precio.
    v["rent_bruta_min"] = (v["alquiler_p10_usd_mes"] * 12 / v["venta_usd"] * 100).round(2)
    v["rent_bruta_max"] = (v["alquiler_p90_usd_mes"] * 12 / v["venta_usd"] * 100).round(2)
    ancho = v["rent_bruta_max"] - v["rent_bruta_min"]
    rep(f"Banda p10-p90 de la bruta: ancho mediano {ancho.median():.2f} pp "
        f"(p10 {ancho.quantile(.1):.2f}, p90 {ancho.quantile(.9):.2f})")
    adentro = (v["rent_bruta_pct"] >= v["rent_bruta_min"]) & (v["rent_bruta_pct"] <= v["rent_bruta_max"])
    rep(f"    la estimacion puntual cae dentro de su banda en el {adentro.mean():.1%} de las ventas")
    rep("")

    ok = v[v["estimacion_confiable"] == 1]
    rep(f"Rentabilidad bruta — mediana   : {ok['rent_bruta_pct'].median():.2f}%")
    rep(f"Rentabilidad bruta — p25 a p75 : {ok['rent_bruta_pct'].quantile(.25):.2f}% a "
        f"{ok['rent_bruta_pct'].quantile(.75):.2f}%")
    rep(f"Rentabilidad neta — mediana    : {ok['rent_neta_pct'].median():.2f}%")
    rep(f"Meses de repago — mediana      : {ok['meses_repago'].median():,.0f} "
        f"({ok['meses_repago'].median()/12:.1f} años)")
    rep("")
    rep("Lectura de la incertidumbre (mediana de la base):")
    rep(f"    rentabilidad bruta {ok['rent_bruta_pct'].median():.2f}%  ->  banda de "
        f"{ok['rent_bruta_min'].median():.2f}% a {ok['rent_bruta_max'].median():.2f}%")
    return v


def ranking_barrios(v: pd.DataFrame, rep: Reporte) -> pd.DataFrame:
    """
    Ranking de barrios por rentabilidad NETA mediana.

    Con gastos planos, ordenar por bruta o por neta daba lo mismo. Con el ABL
    segmentado ya no: los gastos cambian de una propiedad a otra, y lo que
    cobra el inversor es la neta. Los empates se ordenan por nombre, para que
    el ranking no cambie entre corridas.
    """
    rep.titulo("RANKING DE BARRIOS POR RENTABILIDAD NETA")

    ok = v[v["estimacion_confiable"] == 1]
    agg = dict(
        n_ventas=("venta_usd", "size"),
        venta_med=("venta_usd", "median"),
        venta_m2=("venta_m2_usd", "median"),
        alq_est=("alquiler_est_usd_mes", "median"),
        rent_bruta=("rent_bruta_pct", "median"),
        rent_neta=("rent_neta_pct", "median"),
    )
    if "tir_5a_pct" in ok.columns:
        agg["tir_5a"] = ("tir_5a_pct", "median")
    g = ok.groupby("barrio").agg(**agg)
    g = (g[g["n_ventas"] >= 30].reset_index()
         .sort_values(["rent_neta", "barrio"], ascending=[False, True]).set_index("barrio"))

    con_tir = "tir_5a" in g.columns
    rep(f"{'barrio':<20}{'n':>6}{'venta USD':>12}{'USD/m2':>9}"
        f"{'alq est':>9}{'bruta':>8}{'neta':>7}" + (f"{'TIR 5a':>8}" if con_tir else ""))
    rep("-" * (79 if con_tir else 71))
    for b, r in g.iterrows():
        rep(f"{b:<20}{int(r['n_ventas']):>6}{r['venta_med']:>12,.0f}"
            f"{r['venta_m2']:>9,.0f}{r['alq_est']:>9,.0f}"
            f"{r['rent_bruta']:>7.2f}%{r['rent_neta']:>6.2f}%"
            + (f"{r['tir_5a']:>7.2f}%" if con_tir else ""))

    # Correlacion: valida (o refuta) la hipotesis de relacion inversa
    c = g["venta_m2"].corr(g["rent_bruta"], method="spearman")
    rep("")
    rep(f"Correlacion de Spearman entre precio/m2 y rentabilidad: {c:.3f}")
    if c < -0.5:
        rep("-> Relacion inversa fuerte: los barrios caros rinden menos como renta.")
        rep("   Esto CONFIRMA la hipotesis planteada en el trabajo.")
    elif c < -0.2:
        rep("-> Relacion inversa moderada.")
    else:
        rep("-> No hay relacion inversa clara. Revisar la hipotesis.")
    return g
