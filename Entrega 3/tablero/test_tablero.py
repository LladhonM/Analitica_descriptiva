#!/usr/bin/env python
"""
test_tablero.py — Tests de la logica del tablero (datos.py).

Oraculos independientes:
  - las cifras de referencia del informe y del README (neta mediana 5,65%,
    19,4% sobre el piso, TIR mediana 4,27%, embudo 4.484 -> 227 -> 18 -> 4),
    que el tablero tiene que reproducir sin filtros
  - cada filtro, contra la condicion que dice aplicar, fila por fila
con NEGATIVOS: un filtro que deja 0 filas no rompe los KPIs ni el embudo.

Uso:
    py tablero/test_tablero.py      # desde Entrega 3/, o desde tablero/
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import datos as T
import supuestos as S


fallos = []
corridos = 0


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


piso, techo = S.RETORNO_MINIMO_BANDA
df = T.cargar()

# --- Carga ------------------------------------------------------------------------
check("carga: 9.203 ventas con estimacion confiable", len(df) == 9203, f"{len(df)} filas")
check("carga: solo ventas confiables",
      (df["operacion"] == "venta").all() and (df["estimacion_confiable"] == 1).all())
check("carga: sin el BOM en la primera columna", "id_aviso" in df.columns)
check("carga: solo las columnas de GUIA_TABLERO.md", set(df.columns) <= set(T.COLUMNAS) | {"barrio_nombre"},
      f"de mas: {sorted(set(df.columns) - set(T.COLUMNAS))}")
check("carga: deja afuera los textos crudos", "descripcion" not in df.columns and "precio_m2" not in df.columns)
for c in T.BOOLEANAS:
    check(f"carga: {c} es booleana y sin nulos", df[c].dtype == bool, str(df[c].dtype))
check("carga: nombre de barrio para mostrar, con tildes",
      (df.loc[df["barrio"] == "nunez", "barrio_nombre"] == "Núñez").all()
      and (df["barrio"] == "nunez").any())

# --- Sin filtros: las cifras del informe ------------------------------------------
todo = T.Filtros.sin_filtros(df)
sf = T.filtrar(df, todo)
k = T.kpis(sf)
check("sin filtros: N = 9.203", k["n"] == 9203, str(k["n"]))
check("sin filtros: neta mediana 5,65%", round(k["neta_mediana"], 2) == 5.65, f"{k['neta_mediana']:.4f}")
check("sin filtros: TIR mediana 4,27%", round(k["tir_mediana"], 2) == 4.27, f"{k['tir_mediana']:.4f}")
check("sin filtros: 19,4% sobre el piso", round(k["pct_sobre_piso"], 1) == 19.4, f"{k['pct_sobre_piso']:.3f}")
check("sin filtros: distancia al piso = neta mediana - piso",
      math.isclose(k["pp_al_piso"], k["neta_mediana"] - piso))
check("sin filtros: la banda mediana encierra a la neta mediana",
      k["neta_min_mediana"] < k["neta_mediana"] < k["neta_max_mediana"])
emb = T.embudo(sf)
check("sin filtros: embudo 4.484 -> 227 -> 18 -> 4", [n for _, n in emb] == [4484, 227, 18, 4],
      str([n for _, n in emb]))
check("embudo: cuatro etapas con nombre", len(emb) == 4 and all(isinstance(e, str) and e for e, _ in emb))

# --- Filtros por defecto ----------------------------------------------------------
dflt = T.Filtros()
check("defecto: presupuesto de supuestos.py", dflt.presupuesto == S.PRESUPUESTO_USD)
check("defecto: tipo departamento", dflt.tipo == "departamento")
d = T.filtrar(df, dflt)
check("defecto: es el universo de la decision (4.484)", len(d) == 4484, f"{len(d)} filas")
check("defecto: el embudo no cambia", [n for _, n in T.embudo(d)] == [4484, 227, 18, 4])

# --- Cada filtro hace lo que dice -------------------------------------------------
casos = [
    ("presupuesto", dict(presupuesto=(100_000, 150_000)), lambda x: x["venta_usd"].between(100_000, 150_000)),
    ("tipo", dict(tipo="ph"), lambda x: x["tipo_familia"] == "ph"),
    ("comuna", dict(comunas=(13, 14)), lambda x: x["comuna"].isin([13, 14])),
    ("barrio", dict(barrios=("palermo",)), lambda x: x["barrio"] == "palermo"),
    ("ambientes", dict(ambientes=(2,)), lambda x: x["ambientes"] == 2),
    ("superficie", dict(superficies=("36-55",)), lambda x: x["superficie_rango"] == "36-55"),
    ("antiguedad", dict(antiguedades=("a estrenar",)), lambda x: x["antiguedad_rango"] == "a estrenar"),
]
for nombre, cambio, cond in casos:
    f = T.filtrar(df, T.Filtros.sin_filtros(df).con(**cambio))
    check(f"filtro {nombre}: achica N", 0 < len(f) < len(df), f"{len(f)} filas")
    check(f"filtro {nombre}: todas las filas cumplen", bool(cond(f).all()))

# NEG: un barrio que no esta en la comuna elegida deja 0 filas.
vacio = T.filtrar(df, T.Filtros.sin_filtros(df).con(comunas=(1,), barrios=("palermo",)))
check("vacio: barrio fuera de la comuna deja 0 filas", len(vacio) == 0, f"{len(vacio)} filas")
kv = T.kpis(vacio)
check("vacio: N = 0 y medianas sin dato, sin excepcion",
      kv["n"] == 0 and math.isnan(kv["neta_mediana"]) and math.isnan(kv["pct_sobre_piso"]))
check("vacio: embudo en cero", [n for _, n in T.embudo(vacio)] == [0, 0, 0, 0])

# --- Opciones de los filtros ------------------------------------------------------
b13 = T.barrios_de(df, (13,))
check("barrios: acotados por la comuna", set(b13) == set(df.loc[df["comuna"] == 13, "barrio"]))
check("barrios: sin comuna elegida, todos", set(T.barrios_de(df, ())) == set(df["barrio"]))
check("superficie: en orden de tamanio", T.opciones(df, "superficie_rango")[0] == "hasta 35"
      and T.opciones(df, "superficie_rango")[-1] == "120+")
check("antiguedad: de nueva a vieja", T.opciones(df, "antiguedad_rango")[0] == "a estrenar"
      and T.opciones(df, "antiguedad_rango")[-1] == "50+")

# --- Frase y encabezado -----------------------------------------------------------
check("frase: debajo del piso dice 'menos'", "menos" in T.frase(k))
check("frase: sobre el piso dice 'más'", "más" in T.frase({**k, "pp_al_piso": 0.5}))
check("frase: sin propiedades no inventa un numero", T.frase(kv) == "")
check("frase: coma decimal", f"{abs(k['pp_al_piso']):.2f}".replace(".", ",") in T.frase(k), T.frase(k))
check("relevamiento: fechas del dato", T.fechas_relevamiento(df) == "16 y 17-08-2026", T.fechas_relevamiento(df))
check("colores: el acento es solo #FFD275", T.COLORES["acento"] == "#FFD275")
check("colores: un solo color de seleccion, distinto de todos los demas", T.COLORES.get("seleccion") == "#00A676"
      and list(T.COLORES.values()).count("#00A676") == 1)


# --- Pestana 2: ranking, H1, mapa -------------------------------------------------
rk = T.cargar_ranking(df)
check("ranking: 29 barrios con 30 ventas o mas", len(rk) == 29 and (rk["n_ventas"] >= S.MIN_VENTAS_BARRIO).all())
check("ranking: ordenado por neta", rk["rent_neta"].is_monotonic_increasing)
med = df.groupby("barrio")["rent_neta_pct"].median()
check("ranking: la neta es la mediana del dataset", (rk["rent_neta"] - rk["barrio"].map(med)).abs().max() < 1e-9)
check("ranking: la banda encierra a la neta de cada barrio",
      ((rk["neta_min"] <= rk["rent_neta"]) & (rk["rent_neta"] <= rk["neta_max"])).all())
check("ranking: nombre con tildes", "Núñez" in set(rk["barrio_nombre"]) or "nunez" not in set(rk["barrio"]))
check("ranking: no responde a los filtros", len(T.cargar_ranking(T.filtrar(df, dflt))) == 29)

h = T.h1(sf)
check("H1 sin filtros: 29 barrios", len(h["barrios"]) == 29, str(len(h["barrios"])))
check("H1 sin filtros: -0,98 pp por USD 500/m2", round(h["pendiente"], 2) == -0.98, f"{h['pendiente']:.4f}")
check("H1 sin filtros: IC [-1,16, -0,81]",
      (round(h["ic"][0], 2), round(h["ic"][1], 2)) == (-1.16, -0.81), str(h["ic"]))
check("H1: con los filtros por defecto cambia", round(T.h1(d)["pendiente"], 2) != -0.98)
h_chico = T.h1(T.filtrar(df, T.Filtros.sin_filtros(df).con(barrios=("palermo",))))
check("H1: con menos de 3 barrios no hay pendiente, sin excepcion",
      len(h_chico["barrios"]) < 3 and math.isnan(h_chico["pendiente"]))

pos = T.posicion_banda(T.pd.Series([piso - 0.01, piso, techo, techo + 0.01, float("nan")]))
check("posicion: bordes de la banda", list(pos[:4]) == ["debajo", "en_banda", "en_banda", "sobre"], str(list(pos)))
check("posicion: sin dato queda sin dato", T.pd.isna(pos.iloc[4]))
check("posicion: una etiqueta y un color por categoria",
      set(T.POSICIONES) == {"debajo", "en_banda", "sobre"}
      and [c for _, c in T.POSICIONES.values()] == [T.COLORES["debajo_piso"], T.COLORES["en_banda"],
                                                   T.COLORES["sobre_techo"]])
check("mapa: 5 ventas sin coordenadas", T.sin_coordenadas(df) == 5, str(T.sin_coordenadas(df)))
check("mapa: vacio no rompe", T.sin_coordenadas(vacio) == 0)

# --- Pestana 3: P1, frontera P2 y ficha ---------------------------------------------
p1 = T.p1_tabla(sf)
check("P1 sin filtros: 18 propiedades", len(p1) == 18, str(len(p1)))
check("P1: solo del universo y marcadas por decision.py", bool((p1["universo_decision"] & p1["p1_comprar"]).all()))
check("P1: ordenadas por neta pesimista, de mayor a menor", p1["neta_min_pct"].is_monotonic_decreasing)
check("P1: todas estan en la frontera P2", bool(p1["p2_no_dominada"].all()))
p1b = T.p1_tabla(T.filtrar(df, T.Filtros.sin_filtros(df).con(barrios=("san cristobal",))))
check("P1: responde a los filtros", 0 < len(p1b) < 18 and (p1b["barrio"] == "san cristobal").all(), str(len(p1b)))
check("P1: descuento del encabezado ~30% sin filtros", T.descuento_p1(p1) == 30, str(T.descuento_p1(p1)))

fr = T.frontera_p2(sf)
check("P2 sin filtros: 140 propiedades", len(fr) == 140, str(len(fr)))
check("P2: solo del universo", bool((fr["universo_decision"] & fr["p2_no_dominada"]).all()))
check("P2: ancho de banda = max - min", ((fr["ancho"] - (fr["neta_max_pct"] - fr["neta_min_pct"])).abs() < 1e-9).all())
check("P2: ordenada por ancho de banda, la mas angosta primero", fr["ancho"].is_monotonic_increasing)
# NEG (GUIA_TABLERO.md): nunca ordenar la frontera por rentabilidad.
check("P2: no queda ordenada por neta", not fr["rent_neta_pct"].is_monotonic_increasing
      and not fr["rent_neta_pct"].is_monotonic_decreasing)

check("vacio: P1 y P2 sin filas, sin excepcion", len(T.p1_tabla(vacio)) == 0 and len(T.frontera_p2(vacio)) == 0)
check("vacio: sin descuento que mostrar", T.descuento_p1(T.p1_tabla(vacio)) is None)

uno = p1.iloc[0]
f = T.fila(sf, uno["id_aviso"])
check("ficha: devuelve la propiedad pedida", f is not None and f["id_aviso"] == uno["id_aviso"])
check("ficha: id que no esta en la vista -> None", T.fila(vacio, uno["id_aviso"]) is None)
check("ficha: sin seleccion -> None", T.fila(sf, None) is None)
check("ids unicos: la seleccion no es ambigua", df["id_aviso"].is_unique)

# --- Pestana 4: tradicional contra temporal ----------------------------------------
p3 = T.cargar_p3()
check("P3: 47 celdas en todas las filas", (p3["celdas"] == 47).all())
check("P3: la vacancia base de supuestos.py esta en la tabla", S.VACANCIA_PCT in T.vacancias(p3),
      str(T.vacancias(p3)))
check("P3: vacancias ordenadas", T.vacancias(p3) == sorted(T.vacancias(p3)))
base = T.p3_vacancia(p3, S.VACANCIA_PCT)
en53 = base[base["ocupacion_sostenible_pct"] == S.OCUPACION_REF_PCT].set_index("gestion")["gana_temporal"]
check("P3 base: con 53% gana en 2 celdas tercerizada y 28 autogestionada",
      en53.to_dict() == {"autogestionado": 28, "tercerizada": 2}, str(en53.to_dict()))
eq = T.equilibrio(base)
check("P3 base: equilibrio 65,5% tercerizada y 51,7% autogestionada",
      eq == {"tercerizada": 65.5, "autogestionado": 51.7}, str(eq))
check("P3: ocupacion de Inside Airbnb 18,6%", round(T.ocupacion_airbnb(), 1) == 18.6, str(T.ocupacion_airbnb()))
for g, sub_g in base.groupby("gestion"):
    check(f"P3: ordenada por ocupacion y las celdas no bajan al subir la ocupacion ({g})",
          sub_g["ocupacion_sostenible_pct"].is_monotonic_increasing and sub_g["gana_temporal"].is_monotonic_increasing)
piv = base.pivot(index="ocupacion_sostenible_pct", columns="gestion", values="gana_temporal")
check("P3: autogestionado gana en al menos tantas celdas como tercerizada",
      bool((piv["autogestionado"] >= piv["tercerizada"]).all()))
check("P3: una vacancia que no esta en la tabla no inventa filas", T.p3_vacancia(p3, 99.0).empty)
check("P3: un nombre y un color por gestion",
      T.GESTIONES == {"tercerizada": ("Tercerizada", T.COLORES["principal"]),
                      "autogestionado": ("Autogestionada", T.COLORES["secundario"])})

# --- Pestana 5: supuestos y alcance -------------------------------------------------
sens = T.cargar_sensibilidad()
check("sensibilidad: 22 escenarios", len(sens) == 22, str(len(sens)))
b0 = sens[sens["parametro"] == "base"].iloc[0]
check("sensibilidad: la base da el mismo P1 que el embudo (18 y 4)",
      (b0["n_p1"], b0["n_p1_con_entrada"]) == (emb[2][1], emb[3][1]), str((b0["n_p1"], b0["n_p1_con_entrada"])))
check("sensibilidad: marca como base las 6 filas con los supuestos de la base", int(sens["es_base"].sum()) == 6,
      str(int(sens["es_base"].sum())))
check("sensibilidad: las filas marcadas como base dan lo mismo que la base",
      (sens.loc[sens["es_base"], ["n_p1", "n_p1_con_entrada"]] == [b0["n_p1"], b0["n_p1_con_entrada"]]).all().all())
check("sensibilidad: una etiqueta distinta por escenario", sens["escenario"].is_unique, str(list(sens["escenario"])))
check("sensibilidad: etiquetas con coma decimal",
      "Vacancia 4%" in set(sens["escenario"]) and "Margen 0,5 pp" in set(sens["escenario"]), str(list(sens["escenario"])))
peor = sens[sens["parametro"] == "extremo desfavorable"].iloc[0]
check("sensibilidad: en el extremo desfavorable ninguna pasa P1 con entrada", peor["n_p1_con_entrada"] == 0)

fu = T.fuentes()
check("fuentes: una fila por fuente externa versionada", len(fu) == 7, str(len(fu)))
check("fuentes: todas con fecha de descarga", fu["descarga"].notna().all() and (fu["descarga"] != "").all())
check("fuentes: Inside Airbnb con su snapshot", fu.set_index("fuente").loc["Inside Airbnb", "periodo"] == "2026-06-29",
      str(fu.set_index("fuente").get("periodo")))

print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
