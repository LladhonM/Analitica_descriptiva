"""
validacion.py — Los tests formales de H1 a H4 (notebook 04).

Cada funcion devuelve el estadistico, el p-valor y lo necesario para un
intervalo de confianza. La lectura (si el efecto cambia la decision) la hace
el notebook, porque depende del problema y no de la estadistica.

POR QUE NO STATSMODELS
----------------------
Las cuatro piezas que hacen falta (permutacion, Holm, errores agrupados y Van
Elteren) son cortas y se verifican contra scipy en test_validacion.py. Sumar
una dependencia para eso no se justifica.

  permutacion_spearman  H1: Spearman unilateral con p-valor por permutacion
  holm                  H1: correccion por comparaciones multiples
  ols_agrupado          H2: minimos cuadrados con errores agrupados (CR1)
  van_elteren           H3: Mann-Whitney estratificado
  pendiente_intra       H4: efecto con efectos fijos de celda, y su bootstrap
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# ==========================================================================
# H1: SPEARMAN CON PERMUTACION
# ==========================================================================

def permutacion_spearman(x, y, n_perm: int = 10_000, semilla: int = 0) -> tuple[float, float]:
    """
    Spearman y p-valor unilateral (H1: rho < 0) por permutacion.

    Permutar y entre unidades destruye cualquier asociacion y conserva las
    dos distribuciones: es la distribucion de rho bajo H0 sin suponer
    normalidad ni muestra grande. p = (1 + permutaciones con rho <= observado)
    / (n_perm + 1), que nunca da cero.
    """
    rx, ry = stats.rankdata(x), stats.rankdata(y)
    rho = float(np.corrcoef(rx, ry)[0, 1])
    rng = np.random.default_rng(semilla)
    perm = np.array([np.corrcoef(rx, rng.permutation(ry))[0, 1] for _ in range(n_perm)])
    return rho, float((1 + (perm <= rho).sum()) / (n_perm + 1))


def holm(p: pd.Series) -> pd.Series:
    """
    p-valores ajustados por Holm-Bonferroni: controla la probabilidad de un
    falso positivo en toda la familia, y es menos conservador que Bonferroni.
    """
    orden = p.sort_values()
    m = len(p)
    ajustado = np.maximum.accumulate([(m - i) * v for i, v in enumerate(orden.values)])
    return pd.Series(np.minimum(ajustado, 1.0), index=orden.index).reindex(p.index)


# ==========================================================================
# H2: MINIMOS CUADRADOS CON ERRORES AGRUPADOS
# ==========================================================================

def ols_agrupado(X: np.ndarray, y: np.ndarray, grupos: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Coeficientes y errores estandar agrupados (CR1, con la correccion de
    muestra finita habitual).

    Los avisos de un mismo barrio comparten todo lo que no se mide (la calle,
    la cuadra, el estado del edificio): sus errores no son independientes, y
    el error estandar comun subestimaria la incertidumbre. El agrupado la
    estima permitiendo cualquier correlacion dentro del grupo.
    """
    n, k = X.shape
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    u = y - X @ beta
    meat = np.zeros((k, k))
    g_ids = pd.factorize(grupos)[0]
    G = g_ids.max() + 1
    for g in range(G):
        s = X[g_ids == g].T @ u[g_ids == g]
        meat += np.outer(s, s)
    c = G / (G - 1) * (n - 1) / (n - k)
    v = c * xtx_inv @ meat @ xtx_inv
    return beta, np.sqrt(np.diag(v))


# ==========================================================================
# H3: VAN ELTEREN
# ==========================================================================

def van_elteren(y: pd.Series, grupo: pd.Series, estrato: pd.Series, minimo: int = 5) -> dict:
    """
    Test de Van Elteren: Mann-Whitney dentro de cada estrato, combinado con
    pesos 1 / (n + 1). Compara grupo == 1 contra grupo == 0 solo entre
    semejantes; un estrato entra si cada grupo tiene al menos `minimo`.

    Devuelve z (negativo si el grupo 1 tiende a valores menores) y los
    p-valores unilateral (H1: grupo 1 menor) y bilateral, con la varianza
    corregida por empates.
    """
    num, var, celdas, n_tot = 0.0, 0.0, 0, 0
    for _, idx in estrato.groupby(estrato, observed=True).groups.items():
        ys, gs = y.loc[idx], grupo.loc[idx]
        ok = ys.notna()
        ys, gs = ys[ok], gs[ok]
        n1, n0 = int((gs == 1).sum()), int((gs == 0).sum())
        if n1 < minimo or n0 < minimo:
            continue
        n = n1 + n0
        r = stats.rankdata(ys.values)
        w = r[(gs == 1).values].sum() - n1 * (n + 1) / 2
        _, t = np.unique(ys.values, return_counts=True)
        v = n1 * n0 / 12 * ((n + 1) - (t ** 3 - t).sum() / (n * (n - 1)))
        peso = 1 / (n + 1)
        num += peso * w
        var += peso ** 2 * v
        celdas += 1
        n_tot += n
    if celdas == 0:
        return {"z": np.nan, "p_menor": np.nan, "p_bilateral": np.nan, "celdas": 0, "avisos": 0}
    z = num / np.sqrt(var)
    return {"z": float(z), "p_menor": float(stats.norm.cdf(z)), "p_bilateral": float(2 * stats.norm.sf(abs(z))),
            "celdas": celdas, "avisos": n_tot}


# ==========================================================================
# H4: PENDIENTE CON EFECTOS FIJOS DE CELDA
# ==========================================================================

def _sumas_por_celda(x: pd.Series, y: pd.Series, celda: pd.Series) -> pd.DataFrame:
    """Sumas desviadas de la media de la celda: con ellas, la pendiente intra es un cociente."""
    d = pd.DataFrame({"x": x, "y": y, "c": celda}).dropna()
    d = d[d.groupby("c")["x"].transform("size") >= 2]
    xd = d["x"] - d.groupby("c")["x"].transform("mean")
    yd = d["y"] - d.groupby("c")["y"].transform("mean")
    return pd.DataFrame({"sxy": xd * yd, "sxx": xd * xd, "c": d["c"]}).groupby("c")[["sxy", "sxx"]].sum()


def pendiente_intra(x: pd.Series, y: pd.Series, celda: pd.Series,
                    n_boot: int = 2_000, semilla: int = 0) -> tuple[float, np.ndarray, int]:
    """
    Pendiente de y sobre x con efectos fijos de celda (estimador intra: la
    regresion con una dummy por celda da exactamente esto), y su distribucion
    bootstrap remuestreando CELDAS: los avisos de una celda no son
    independientes, y remuestrear filas achicaria el error.

    Devuelve la pendiente, las pendientes bootstrap y la cantidad de celdas.
    """
    s = _sumas_por_celda(x, y, celda)
    beta = s["sxy"].sum() / s["sxx"].sum()
    rng = np.random.default_rng(semilla)
    pesos = rng.multinomial(len(s), np.full(len(s), 1 / len(s)), size=n_boot)
    boot = (pesos @ s["sxy"].values) / (pesos @ s["sxx"].values)
    return float(beta), boot, len(s)


# ==========================================================================
# RESUMEN DE LOS CUATRO TESTS (para el informe)
# ==========================================================================

def resumen_hipotesis(df: pd.DataFrame, n_boot: int = 5_000) -> dict:
    """
    Las cifras de la tabla resumen del notebook 04, con los mismos
    procedimientos, umbrales y semillas. Las usa reporte.py: el informe no
    puede leer las salidas de un notebook, y escribir los numeros a mano los
    desincronizaria. Si se cambia un test en el notebook, hay que cambiarlo aca.
    """
    import accesibilidad as A
    import eda
    import supuestos as S

    r = {}
    ok = df[(df["estimacion_confiable"] == 1) & df["rent_bruta_pct"].notna()]
    estrato = ["barrio", "superficie_rango"]

    # H1: Spearman entre barrios, y por tramo con Holm.
    g = ok.groupby("barrio").agg(n=("rent_bruta_pct", "size"), m2=("venta_m2_usd", "median"),
                                 renta=("rent_bruta_pct", "median"))
    b = g[g["n"] >= S.MIN_VENTAS_BARRIO]
    r["h1_rho"], r["h1_p"] = permutacion_spearman(b["m2"], b["renta"], n_perm=10_000, semilla=1)
    ts = stats.theilslopes(b["renta"], b["m2"])
    r.update(h1_barrios=len(b), h1_efecto=ts.slope * 500, h1_ic=(ts.low_slope * 500, ts.high_slope * 500))
    ps = {}
    for tramo in S.ORDEN_SUPERFICIE_RANGO:
        gg = ok[ok["superficie_rango"] == tramo].groupby("barrio").agg(
            n=("rent_bruta_pct", "size"), m2=("venta_m2_usd", "median"), renta=("rent_bruta_pct", "median"))
        gg = gg[gg["n"] >= S.MIN_AVISOS_CELDA]
        if len(gg) >= 5:
            ps[tramo] = permutacion_spearman(gg["m2"], gg["renta"], n_perm=10_000, semilla=2)[1]
    holm_p = holm(pd.Series(ps))
    r.update(h1_tramos=len(ps), h1_tramos_rechazan=int((holm_p < S.ALFA).sum()))

    # H2: efectos fijos de barrio y controles, errores agrupados por barrio.
    v = df[(df["operacion"] == "venta") & df["venta_m2_usd"].notna() & df["dist_transporte_m"].notna()]
    y = np.log(v["venta_m2_usd"].values)
    X0 = A.matriz_base(v, controles=True)
    G = v["barrio"].nunique()
    q = stats.t.ppf(0.975, G - 1)
    for nombre, reg in [("lineal", v[["dist_transporte_m"]].values / 1000),
                        ("escalon", (v["dist_transporte_m"].values > 1000).astype(float)[:, None])]:
        beta, se = ols_agrupado(np.hstack([X0, reg]), y, v["barrio"].values)
        t = beta[-1] / se[-1]
        r[f"h2_{nombre}_pct"] = float(np.expm1(beta[-1]) * 100)
        r[f"h2_{nombre}_ic"] = (float(np.expm1(beta[-1] - q * se[-1]) * 100), float(np.expm1(beta[-1] + q * se[-1]) * 100))
        r[f"h2_{nombre}_p"] = float(stats.t.cdf(t, G - 1))
    r["h2_lejos_pct"] = float((v["dist_transporte_m"] > 1000).mean() * 100)

    # H3: Van Elteren y efecto mediano por celda con bootstrap de celdas.
    ventas = df[(df["operacion"] == "venta") & df["venta_m2_usd"].notna()]
    r["h3_p_precio"] = van_elteren(ventas["venta_m2_usd"], ventas["a_reciclar"],
                                   ventas["barrio"] + " | " + ventas["superficie_rango"], S.MIN_GRUPO_ESTRATO)["p_menor"]
    r["h3_p_renta"] = 1 - van_elteren(ok["rent_bruta_pct"], ok["a_reciclar"],
                                      ok["barrio"] + " | " + ok["superficie_rango"], S.MIN_GRUPO_ESTRATO)["p_menor"]
    for base, col, relativo, semilla, clave in [(ventas, "venta_m2_usd", True, 5, "h3_precio"),
                                                (ok, "rent_bruta_pct", False, 6, "h3_renta")]:
        t = eda.efecto_estratificado(base, "a_reciclar", col, estrato, S.MIN_GRUPO_ESTRATO)
        x = (t["diferencia"] / t["mediana_0"] * 100 if relativo else t["diferencia"]).values
        w = t["peso"].values
        rng = np.random.default_rng(semilla)
        bt = [eda.mediana_ponderada(x[i], w[i]) for i in (rng.integers(0, len(t), len(t)) for _ in range(n_boot))]
        r[clave] = eda.mediana_ponderada(x, w)
        r[f"{clave}_ic"] = tuple(np.percentile(bt, [2.5, 97.5]))

    # H4: dos pendientes intra-celda y Wald con error bootstrap por celdas.
    obs = df[df["antiguedad_anios_imputada"] == 0]
    vv = obs[(obs["operacion"] == "venta") & obs["venta_m2_usd"].notna()]
    aa = obs[(obs["operacion"] == "alquiler") & obs["alquiler_m2_usd_mes"].notna()]
    bv, boot_v, _ = pendiente_intra(vv["antiguedad_anios"], np.log(vv["venta_m2_usd"]),
                                    vv["barrio"] + "|" + vv["superficie_rango"], n_boot=n_boot, semilla=7)
    ba, boot_a, _ = pendiente_intra(aa["antiguedad_anios"], np.log(aa["alquiler_m2_usd_mes"]),
                                    aa["barrio"] + "|" + aa["superficie_rango"], n_boot=n_boot, semilla=8)
    z = (bv - ba) / (boot_v - boot_a).std(ddof=1)
    decada = lambda x: np.expm1(10 * np.asarray(x)) * 100
    rel = (1 + decada(ba) / 100) / (1 + decada(bv) / 100) - 1
    r.update(h4_venta=float(decada(bv)), h4_alquiler=float(decada(ba)), h4_p=float(stats.norm.cdf(z)),
             h4_bruta_pp=float(rel * ok["rent_bruta_pct"].median()),
             h4_rel_ic=tuple(np.percentile((1 + decada(boot_a) / 100) / (1 + decada(boot_v) / 100) - 1,
                                           [2.5, 97.5]) * 100))
    return r
