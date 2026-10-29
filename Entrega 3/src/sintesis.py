#!/usr/bin/env python
"""
sintesis.py — Sintesis de atributos (PCA y MCA) y micro-mercados (notebook 05).

QUE RESUELVE
------------
Cada aviso tiene 29 atributos fisicos extraidos del texto (amenities del
edificio, equipamiento de la unidad, estado), mas su tipo, tamanio,
antiguedad y disposicion. Son demasiados para leerlos de a uno y estan
correlacionados: un edificio con pileta suele tener SUM y solarium. La
reduccion de dimensionalidad busca los pocos ejes que los resumen, y el
clustering sobre esos ejes, grupos de propiedades parecidas: micro-mercados.

POR QUE LOS DOS METODOS
-----------------------
  PCA  sobre las 29 dummies estandarizadas. Es lo que se declaro en el plan
       de la 2da entrega. Una dummy no es una variable continua, asi que el
       porcentaje de varianza de cada componente sale bajo y se lee con
       cuidado.
  MCA  analisis de correspondencias multiples sobre las mismas 29 (como
       si/no) mas las cuatro categoricas de estructura. Es el metodo hecho
       para variables categoricas. Su inercia se corrige por Benzecri, porque
       la inercia cruda de la tabla disyuntiva subestima cuanto resume cada eje.

Si los dos metodos encuentran los mismos ejes, el resultado no depende del
metodo.

QUE QUEDA AFUERA
----------------
Las dummies comerciales (oportunidad, financiacion, apto_credito,
apto_profesional, renta_actual, dueno_directo) describen el aviso y no la
propiedad. `amenities` y `n_amenities` son resumenes de otras dummies: se usan
para comparar contra los ejes, no para construirlos.

POR QUE NO PRINCE NI STATSMODELS
--------------------------------
El MCA es una descomposicion en valores singulares de la tabla disyuntiva
completa: diez lineas de numpy, verificadas en test_sintesis.py contra un
oraculo independiente (con dos variables, sus autovalores salen del
chi-cuadrado de scipy). Una dependencia nueva no se justifica.

Uso: desde el notebook 05. No escribe archivos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

import validacion as V


# ==========================================================================
# CONFIGURACION
# ==========================================================================

EDIFICIO = ["pileta", "parrilla", "gimnasio", "sum", "solarium", "laundry", "sauna", "coworking",
            "seguridad", "ascensor", "baulera", "cochera_txt"]
UNIDAD = ["aire_acondicionado", "losa_radiante", "calefaccion", "balcon", "terraza", "patio_jardin",
          "dependencia", "toilette", "vestidor", "lavadero", "luminoso", "amoblado", "apto_mascotas"]
ESTADO = ["a_reciclar", "reciclado", "estrenar", "en_pozo"]
ATRIBUTOS = EDIFICIO + UNIDAD + ESTADO
ESTRUCTURA = ["tipo_familia", "superficie_rango", "antiguedad_rango", "disposicion"]

# Ejes que se retienen. Con la correccion de Benzecri, los tres primeros del
# MCA resumen mas del 95% de la inercia; el cuarto agrega alrededor de 1%.
N_EJES = 3
# Micro-mercados. k se elige entre 2 y 8 por silueta y por si los grupos se
# pueden nombrar; ver el notebook 05.
K_MICROMERCADOS = 4
SEMILLA = 0


# ==========================================================================
# PCA
# ==========================================================================

def pca_atributos(df: pd.DataFrame) -> dict:
    """
    PCA sobre las 29 dummies estandarizadas.

    Las cargas son correlaciones entre cada dummy y el componente (vector
    propio por la raiz del autovalor): se leen en la misma escala para todos
    los componentes.
    """
    Z = StandardScaler().fit_transform(df[ATRIBUTOS].astype(float).values)
    pca = PCA().fit(Z)
    cargas = pd.DataFrame(pca.components_.T * np.sqrt(pca.explained_variance_), index=ATRIBUTOS,
                          columns=[f"CP{i + 1}" for i in range(len(ATRIBUTOS))])
    return {"varianza": pca.explained_variance_ratio_, "autovalores": pca.explained_variance_,
            "cargas": cargas, "puntajes": pca.transform(Z)}


# ==========================================================================
# MCA
# ==========================================================================

def tabla_mca(df: pd.DataFrame) -> pd.DataFrame:
    """Las cuatro categoricas de estructura y las 29 dummies como si/no."""
    t = df[ESTRUCTURA].astype(str).copy()
    for c in ATRIBUTOS:
        t[c] = np.where(df[c] == 1, "si", "no")
    return t


def benzecri(autovalores: np.ndarray, q: int) -> np.ndarray:
    """
    Inercia corregida de Benzecri, como proporcion.

    En la tabla disyuntiva, todo eje con autovalor <= 1/Q es ruido de la
    codificacion; los demas se reescalan. Sin la correccion, el primer eje de
    un MCA con 33 variables parece explicar 12% aunque resuma casi todo.
    """
    lam = np.asarray(autovalores)
    c = np.where(lam > 1 / q, (q / (q - 1) * (lam - 1 / q)) ** 2, 0.0)
    return c / c.sum()


def mca(tabla: pd.DataFrame, n_ejes: int = N_EJES) -> dict:
    """
    Analisis de correspondencias multiples: analisis de correspondencias de
    la tabla disyuntiva completa (una columna por categoria).

    Devuelve los autovalores (inercia de cada eje), la proporcion corregida
    de Benzecri, las coordenadas principales de cada aviso y de cada
    categoria, y la contribucion de cada categoria a cada eje.
    """
    Z = pd.get_dummies(tabla, prefix_sep="=", dtype=float)
    q = tabla.shape[1]
    P = Z.values / Z.values.sum()
    r, c = P.sum(1), P.sum(0)
    S_ = (P - np.outer(r, c)) / np.sqrt(np.outer(r, c))
    U, s, Vt = np.linalg.svd(S_, full_matrices=False)
    # El signo de cada eje es arbitrario: se fija para que la categoria que
    # mas contribuye quede del lado positivo, y asi no cambie entre corridas.
    signo = np.sign(Vt[np.arange(len(s)), np.abs(Vt).argmax(1)])
    U, Vt = U * signo, Vt * signo[:, None]
    ejes = [f"D{i + 1}" for i in range(n_ejes)]
    return {
        "autovalores": s ** 2,
        "benzecri": benzecri(s ** 2, q),
        "filas": U[:, :n_ejes] * s[:n_ejes] / np.sqrt(r)[:, None],
        "categorias": pd.DataFrame(Vt[:n_ejes].T * s[:n_ejes] / np.sqrt(c)[:, None], index=Z.columns, columns=ejes),
        "contribucion": pd.DataFrame(Vt[:n_ejes].T ** 2, index=Z.columns, columns=ejes),
        "masa": pd.Series(c, index=Z.columns),
    }


# ==========================================================================
# MICRO-MERCADOS
# ==========================================================================

def silueta_por_k(X: np.ndarray, ks, muestra: int = 4_000, semilla: int = SEMILLA) -> pd.Series:
    """Silueta media de k-medias para cada k, medida en una muestra (es cuadratica en n)."""
    i = np.random.default_rng(semilla).choice(len(X), min(muestra, len(X)), replace=False)
    return pd.Series({k: silhouette_score(X[i], KMeans(k, n_init=20, random_state=semilla).fit(X).labels_[i])
                      for k in ks}, name="silueta")


def micromercados(X: np.ndarray, k: int = K_MICROMERCADOS, semilla: int = SEMILLA) -> np.ndarray:
    """
    k-medias sobre los ejes del MCA. Las etiquetas se renumeran por tamanio
    (0 = el grupo mas grande), para que no dependan del orden de k-medias.
    """
    lab = KMeans(k, n_init=20, random_state=semilla).fit(X).labels_
    orden = pd.Series(lab).value_counts().index
    return pd.Series(lab).map({g: i for i, g in enumerate(orden)}).values


def estabilidad(X: np.ndarray, etiquetas: np.ndarray, k: int = K_MICROMERCADOS, n: int = 20,
                fraccion: float = 0.8, semilla: int = SEMILLA) -> np.ndarray:
    """
    Indice de Rand ajustado entre los grupos y los que salen de reajustar
    k-medias en n submuestras del 80%. Cerca de 1: los grupos no dependen de
    la muestra; cerca de 0: son un corte arbitrario.
    """
    rng = np.random.default_rng(semilla)
    ari = []
    for b in range(n):
        i = rng.choice(len(X), int(fraccion * len(X)), replace=False)
        km = KMeans(k, n_init=10, random_state=b).fit(X[i])
        ari.append(adjusted_rand_score(etiquetas, km.predict(X)))
    return np.array(ari)


def nombrar(df: pd.DataFrame, grupo: str = "grupo") -> dict:
    """
    Nombre de cada grupo segun su perfil, con reglas fijas y no a mano:
    el de mas casas y PH, el de mas amenities entre los demas, el de mayor
    superficie entre los que quedan, y el ultimo. Supone K_MICROMERCADOS = 4.
    """
    p = df.groupby(grupo).agg(casa_ph=("tipo_familia", lambda s: s.isin(["casa", "ph"]).mean()),
                              amenities=("amenities", "mean"), sup=("sup_total_m2", "median"))
    nombres = {}
    g = p["casa_ph"].idxmax()
    nombres[g] = "PH y casas"
    g = p.drop(index=list(nombres))["amenities"].idxmax()
    nombres[g] = "torre con amenities"
    g = p.drop(index=list(nombres))["sup"].idxmax()
    nombres[g] = "departamento clasico grande"
    for g in p.index.difference(list(nombres)):
        nombres[g] = "departamento estandar"
    return nombres


# ==========================================================================
# PRIMA DE CADA GRUPO, CON PRECIOS OBSERVADOS
# ==========================================================================

def prima_en_celda(sub: pd.DataFrame, col: str, grupo: str, referencia) -> pd.DataFrame:
    """
    Cuanto mas (o menos) vale el m2 de cada grupo que el de la referencia,
    comparando avisos de la misma celda barrio x superficie y el mismo tipo.

    Regresion de log(col) con efectos fijos de celda y de tipo; errores
    agrupados por barrio (validacion.ols_agrupado). Solo entran celdas con al
    menos dos avisos. Usa precios OBSERVADOS: la rentabilidad estimada no
    sirve para esto, porque su numerador sale de un modelo que ya usa parte
    de estos atributos.
    """
    sub = sub[sub[col].notna() & (sub[col] > 0)]
    celda = sub["barrio"] + "|" + sub["superficie_rango"]
    sub = sub[celda.map(celda.value_counts()) >= 2]
    celda = celda.loc[sub.index]
    g = pd.get_dummies(sub[grupo], dtype=float).drop(columns=referencia)
    X = np.hstack([pd.get_dummies(celda, dtype=float).values,
                   pd.get_dummies(sub["tipo_familia"], dtype=float, drop_first=True).values, g.values])
    b, se = V.ols_agrupado(X, np.log(sub[col].values), sub["barrio"].values)
    k = g.shape[1]
    t = stats.t.ppf(0.975, sub["barrio"].nunique() - 1)
    return pd.DataFrame({"prima_pct": np.expm1(b[-k:]) * 100,
                         "ic_inf": np.expm1(b[-k:] - t * se[-k:]) * 100,
                         "ic_sup": np.expm1(b[-k:] + t * se[-k:]) * 100,
                         "avisos": [int((sub[grupo] == c).sum()) for c in g.columns]}, index=g.columns)
