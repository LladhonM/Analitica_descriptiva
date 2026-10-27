#!/usr/bin/env python
"""
accesibilidad.py — H2: el precio del m2 y la distancia a la red de transporte.

HIPOTESIS
---------
El precio del m2 decrece con la distancia al transporte, y existe un radio de
influencia a partir del cual el beneficio se diluye.

METODO (declarado desde la 1ra entrega)
---------------------------------------
Regresion de log(USD/m2) sobre la distancia, CON EFECTOS FIJOS DE BARRIO. Sin
el barrio, la distancia mide centralidad: los barrios centrales son caros y
estan cerca de todo. Con el barrio fijo, la comparacion es entre avisos del
mismo barrio que estan mas cerca o mas lejos de una estacion.

Se informa la MAGNITUD y la FORMA de la relacion, no su significancia: el
contraste formal con p-valor es de test_hipotesis (paso siguiente).

  1. Centralidad contra accesibilidad: la pendiente sin y con barrio fijo, y
     cuanto R2 agrega la distancia una vez que el barrio esta en el modelo.
  2. Perfil por tramos de distancia, con tres especificaciones: barrio fijo;
     barrio fijo y controles del inmueble; lo mismo, solo departamentos. Los
     controles importan: lejos de la red hay mas casas y PH, que tienen otro
     precio del m2 por razones que no son la distancia.
  3. Radio de influencia: un modelo con quiebre (efecto lineal solo mas alla
     de un umbral), recorriendo umbrales.
  4. El antecedente: en el repositorio de trabajo del grupo aparecio que la
     correlacion intra-barrio entre precio y distancia al subte se volvia
     negativa a mas de 1 km. Se replica con los mismos terminos.

Uso:
    py src/accesibilidad.py

Salidas:
    data/processed/h2_perfil_distancia.csv  efecto por tramo, medida y especificacion
    data/processed/reporte_h2.txt           log
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import numpy as np
import pandas as pd

import supuestos as S
from fuentes_externas import Reporte


ANALITICO = "data/processed/dataset_analitico.csv"
SALIDA = "data/processed/h2_perfil_distancia.csv"
REPORTE = "data/processed/reporte_h2.txt"

MEDIDAS = {
    "dist_transporte_m": "combinada",
    "dist_subte_m": "subte",
    "dist_tren_m": "tren",
    "dist_metrobus_m": "metrobus",
}
# Controles del inmueble: lo que cambia el precio del m2 dentro de un barrio
# por razones que no son la distancia. es_a_estrenar queda afuera: tiene
# nulos y la antiguedad ya la contiene.
CONTROLES_NUM = ["log_sup", "antiguedad_anios", "a_reciclar", "amenities", "cochera_txt"]


# ==========================================================================
# REGRESION
# ==========================================================================

def ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    """Minimos cuadrados: coeficientes y R2."""
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    return b, float(1 - (r ** 2).sum() / ((y - y.mean()) ** 2).sum())


def efecto_pct(b: float) -> float:
    """Coeficiente sobre log(precio) -> variacion porcentual del precio."""
    return float(np.expm1(b) * 100)


def matriz_base(v: pd.DataFrame, controles: bool) -> np.ndarray:
    """Efectos fijos de barrio (una columna por barrio, sin constante) y, si se pide, controles."""
    partes = [pd.get_dummies(v["barrio"], dtype=float)]
    if controles:
        partes.append(pd.get_dummies(v["tipo_familia"], dtype=float, drop_first=True))
        partes.append(v[CONTROLES_NUM].astype(float))
    return pd.concat(partes, axis=1).values


def tramos(dist: pd.Series) -> pd.Series:
    bordes = S.TRAMOS_DISTANCIA_M + [np.inf]
    etiquetas = [f"{a:,}-{b:,}" if np.isfinite(b) else f"{a:,}+" for a, b in zip(bordes[:-1], bordes[1:])]
    return pd.cut(dist, bordes, labels=etiquetas, right=False)


# ==========================================================================
# BLOQUES DEL REPORTE
# ==========================================================================

def centralidad_contra_accesibilidad(v: pd.DataFrame, rep: Reporte) -> None:
    rep.titulo("1. CENTRALIDAD CONTRA ACCESIBILIDAD: pendiente sin y con barrio fijo")
    y = v["y"].values
    uno = np.ones((len(v), 1))
    fe = matriz_base(v, controles=False)
    _, r2_fe = ols(fe, y)
    rep(f"R2 del barrio solo: {r2_fe:.3f}")
    rep("")
    rep(f"    {'medida':<11}{'sin barrio':>14}{'con barrio':>14}{'R2 que agrega':>16}")
    for col, nombre in MEDIDAS.items():
        km = v[col].values[:, None] / 1000
        b0, _ = ols(np.hstack([uno, km]), y)
        b1, r2 = ols(np.hstack([fe, km]), y)
        rep(f"    {nombre:<11}{efecto_pct(b0[-1]):>11.1f}%/km{efecto_pct(b1[-1]):>11.1f}%/km"
            f"{r2 - r2_fe:>16.4f}")
    rep("")
    rep("Sin barrio fijo, la pendiente mezcla accesibilidad con centralidad. Con barrio")
    rep("fijo, lo que queda es la diferencia entre avisos del mismo barrio.")


def perfil(v: pd.DataFrame, rep: Reporte) -> pd.DataFrame:
    rep.titulo("2. PERFIL POR TRAMOS DE DISTANCIA (efecto sobre el precio del m2, contra el primer tramo)")
    especificaciones = [
        ("barrio", v.index, False),
        ("barrio + controles", v.index, True),
        ("barrio + controles, deptos", v.index[v["tipo_familia"] == "departamento"], True),
    ]
    filas = []
    for col, nombre in MEDIDAS.items():
        for esp, idx, ctrl in especificaciones:
            s = v.loc[idx]
            t = tramos(s[col])
            D = pd.get_dummies(t, dtype=float)
            ref = D.columns[0]
            b, _ = ols(np.hstack([matriz_base(s, ctrl), D.drop(columns=ref).values]), s["y"].values)
            for k, (et, coef) in enumerate(zip(D.columns[1:], b[-(D.shape[1] - 1):])):
                filas.append({"medida": nombre, "especificacion": esp, "tramo_m": et,
                              "efecto_pct": round(efecto_pct(coef), 1), "n": int((t == et).sum())})
            filas.append({"medida": nombre, "especificacion": esp, "tramo_m": ref,
                          "efecto_pct": 0.0, "n": int((t == ref).sum())})
    p = pd.DataFrame(filas)

    orden = list(tramos(pd.Series([0])).cat.categories)
    for nombre in MEDIDAS.values():
        rep(f"{nombre}:")
        sub = p[p["medida"] == nombre]
        n = sub[sub["especificacion"] == "barrio"].set_index("tramo_m")["n"]
        rep(f"    {'especificacion':<28}" + "".join(f"{t:>12}" for t in orden))
        rep(f"    {'avisos':<28}" + "".join(f"{int(n[t]):>12,}" for t in orden))
        for esp in [e[0] for e in especificaciones]:
            f = sub[sub["especificacion"] == esp].set_index("tramo_m")["efecto_pct"]
            rep(f"    {esp:<28}" + "".join(f"{f[t]:>11.1f}%" for t in orden))
        rep("")
    return p


def radio(v: pd.DataFrame, rep: Reporte) -> pd.DataFrame:
    rep.titulo("3. RADIO DE INFLUENCIA: efecto lineal solo mas alla de un umbral")
    rep("Modelo: log(m2) = barrio + controles + b x max(distancia - umbral, 0).")
    rep("Si la distancia no importa hasta el umbral y despues si, el mejor umbral es el radio.")
    rep("")
    X0 = matriz_base(v, controles=True)
    filas = []
    for u in S.UMBRALES_H2_M:
        quiebre = np.maximum(v["dist_transporte_m"].values - u, 0)[:, None] / 1000
        b, r2 = ols(np.hstack([X0, quiebre]), v["y"].values)
        filas.append({"umbral_m": u, "efecto_pct_km": efecto_pct(b[-1]), "r2": r2,
                      "avisos_mas_alla": int((v["dist_transporte_m"] > u).sum())})
    t = pd.DataFrame(filas)
    mejor = t.loc[t["r2"].idxmax()]
    rep(f"    {'umbral':>8}{'por km mas alla':>18}{'R2':>10}{'avisos mas alla':>18}")
    for _, f in t.iterrows():
        rep(f"    {int(f['umbral_m']):>6} m{f['efecto_pct_km']:>16.1f}%{f['r2']:>10.5f}"
            f"{int(f['avisos_mas_alla']):>18,}")
    rep("")
    rep(f"Mejor ajuste: umbral de {int(mejor['umbral_m'])} m. La diferencia de R2 entre el mejor y el peor")
    rep(f"umbral es {t['r2'].max() - t['r2'].min():.5f}: el quiebre no esta marcado con precision, se lee")
    rep("como un rango y no como un numero.")
    return t


def antecedente(v: pd.DataFrame, rep: Reporte) -> None:
    rep.titulo("4. ANTECEDENTE: correlacion intra-barrio a mas y a menos de 1 km")
    rep("Spearman entre el precio del m2 descontado el promedio de su barrio y la distancia,")
    rep("separando los avisos a mas y a menos de 1 km de la red.")
    rep("")
    v = v.assign(yd=v["y"] - v.groupby("barrio")["y"].transform("mean"))
    for col in ("dist_subte_m", "dist_transporte_m"):
        for lejos, g in v.groupby(v[col] > 1000):
            rep(f"    {MEDIDAS[col]:<10} {'a mas de 1 km' if lejos else 'hasta 1 km':<14} "
                f"{len(g):>6,} avisos   Spearman {g['yd'].corr(g[col], method='spearman'):+.3f}")


def composicion(v: pd.DataFrame, rep: Reporte) -> None:
    rep.titulo("5. COMPOSICION: que hay lejos de la red")
    t = pd.crosstab(tramos(v["dist_transporte_m"]), v["tipo_familia"], normalize="index") * 100
    rep(f"    {'tramo (m)':<14}" + "".join(f"{c:>14}" for c in t.columns))
    for k, f in t.iterrows():
        rep(f"    {k:<14}" + "".join(f"{x:>13.1f}%" for x in f))
    rep("")
    rep("Por eso el perfil se informa tambien con controles y solo para departamentos.")


def lectura(v: pd.DataFrame, p: pd.DataFrame, r: pd.DataFrame, rep: Reporte) -> None:
    """La lectura se arma con las cifras de arriba, para que no pueda contradecirlas."""
    rep.titulo("LECTURA")
    fe = matriz_base(v, controles=False)
    _, r2_fe = ols(fe, v["y"].values)
    _, r2 = ols(np.hstack([fe, v[["dist_transporte_m"]].values / 1000]), v["y"].values)
    c = p[(p["medida"] == "combinada") & (p["especificacion"] == "barrio + controles")].set_index("tramo_m")
    d = p[(p["medida"] == "combinada") & (p["especificacion"] == "barrio + controles, deptos")].set_index("tramo_m")
    orden = list(tramos(pd.Series([0])).cat.categories)
    cerca, medio, lejos = orden[1:3], orden[3], orden[4]
    rep(f"- Con el barrio en el modelo, la distancia a la red agrega {r2 - r2_fe:.4f} de R2 "
        f"(el barrio solo explica {r2_fe:.3f}).")
    rep(f"- Hasta 1 km, con controles: tramos {', '.join(cerca)} m, "
        f"{', '.join(f'{c.loc[t, 'efecto_pct']:+.1f}%' for t in cerca)} contra el primero.")
    rep(f"- Entre 1 y 1,5 km el m2 vale {c.loc[medio, 'efecto_pct']:+.1f}% "
        f"({d.loc[medio, 'efecto_pct']:+.1f}% en departamentos), con {int(c.loc[medio, 'n']):,} avisos.")
    casas_ph = (v.loc[tramos(v["dist_transporte_m"]) == lejos, "tipo_familia"] != "departamento").mean() * 100
    rep(f"- Mas alla de 1,5 km: {c.loc[lejos, 'efecto_pct']:+.1f}% "
        f"({d.loc[lejos, 'efecto_pct']:+.1f}% en departamentos), con {int(c.loc[lejos, 'n']):,} avisos, "
        f"{casas_ph:.0f}% de ellos casas y PH.")
    mejor = r.loc[r["r2"].idxmax()]
    rep(f"- Radio: el modelo con quiebre ajusta mejor con umbral de {int(mejor['umbral_m'])} m "
        f"({mejor['efecto_pct_km']:+.1f}% por km mas alla), sin un optimo marcado.")


# ==========================================================================
# MAIN
# ==========================================================================

def main() -> int:
    if not os.path.exists(ANALITICO):
        print(f"No existe {ANALITICO}. Correr el pipeline hasta py src/kpis.py")
        return 1

    rep = Reporte()
    rep.titulo("H2 — PRECIO DEL M2 Y DISTANCIA AL TRANSPORTE")
    rep(f"Fecha: {datetime.now():%Y-%m-%d %H:%M}")

    d = pd.read_csv(ANALITICO, encoding="utf-8-sig", low_memory=False)
    v = d[(d["operacion"] == "venta") & d["venta_m2_usd"].notna()
          & d["dist_transporte_m"].notna()].copy()
    v["y"] = np.log(v["venta_m2_usd"])
    rep(f"Base: {len(v):,} avisos de venta con precio del m2 y coordenadas (todas las ventas:")
    rep("H2 es sobre el precio, no depende de la estimacion del alquiler).")
    rep("Magnitud y forma; el contraste formal con p-valor va en el paso de tests.")

    centralidad_contra_accesibilidad(v, rep)
    p = perfil(v, rep)
    r = radio(v, rep)
    antecedente(v, rep)
    composicion(v, rep)
    lectura(v, p, r, rep)

    p.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    rep("")
    rep(f"Archivo: {SALIDA} ({len(p)} filas)")
    with open(REPORTE, "w", encoding="utf-8") as f:
        f.write("\n".join(rep.lineas))
    return 0


if __name__ == "__main__":
    sys.exit(main())
