#!/usr/bin/env python
"""
app.py — Tablero: ¿conviene comprar para alquilar, y si compro, que?

Solo arma la interfaz; la carga, los filtros y las medianas estan en datos.py.
Diseño en data/processed/DISENO_TABLERO.md; datos en GUIA_TABLERO.md.

Uso, desde Entrega 3/tablero/:
    streamlit run app.py
"""

import html

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import datos as T
import eda
import supuestos as S

PISO, TECHO = S.RETORNO_MINIMO_BANDA
C = T.COLORES
TODOS = "todos"            # None en un selectbox es "sin eleccion"; por eso un valor propio
MIN_CONFIABLE = 30          # menos propiedades: la mediana es poco confiable
METRICAS = {"Neta": ("rent_neta_pct", "Rentabilidad neta (% anual)"),
            "TIR 5 años": ("tir_5a_pct", "TIR a 5 años, con costos de entrada (% anual)")}

st.set_page_config(page_title="¿Conviene comprar para alquilar?", layout="wide")


@st.cache_data
def cargar():
    return T.cargar()


@st.cache_data
def cargar_ranking():
    return T.cargar_ranking(cargar())


def num(x: float, dec: int = 0) -> str:
    """Formato argentino: punto de miles, coma decimal."""
    return f"{x:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def pct(x: float, dec: int = 2) -> str:
    return f"{num(x, dec)}%"


def rgba(hex_color: str, alfa: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alfa})"


# --- Estado de los filtros --------------------------------------------------------
def valores_por_defecto() -> dict:
    f = T.Filtros()
    return {"presupuesto": tuple(int(v) for v in f.presupuesto), "tipo": f.tipo,
            "comunas": [], "barrios": [], "ambientes": [], "superficies": [],
            "antiguedades": [], "metrica": "Neta"}


def restablecer() -> None:
    for clave, valor in valores_por_defecto().items():
        st.session_state[clave] = valor


df = cargar()
for clave, valor in valores_por_defecto().items():
    st.session_state.setdefault(clave, valor)
st.session_state.setdefault("seleccion", None)     # id_aviso elegido en la pestana 3
# Streamlit no deja escribir la seleccion de una tabla o un grafico: para vaciar uno se le
# cambia la key. La version de cada uno va en su key.
st.session_state.setdefault("version_p1", 0)
st.session_state.setdefault("version_p2", 0)


def clave(widget: str) -> str:
    return f"{widget}_{st.session_state['version_' + widget[-2:]]}"


def elegir(id_aviso, vaciar: tuple) -> None:
    """Fija (o borra, con None) la seleccion y vacia los widgets indicados."""
    st.session_state["seleccion"] = id_aviso
    for w in vaciar:
        st.session_state[f"version_{w}"] += 1


def elegir_de_p1() -> None:
    filas = st.session_state[clave("tabla_p1")].selection.rows
    elegir(st.session_state["_ids_p1"][filas[0]] if filas else None, vaciar=("p2",))


def elegir_de_p2() -> None:
    # Solo cuenta la traza de las barras (la 0). Un clic afuera, un doble clic o un clic
    # sobre la barra ya elegida deseleccionan.
    puntos = [p for p in st.session_state[clave("grafico_p2")].selection.points
              if p.get("curve_number") == 0]
    nueva = st.session_state["_ids_p2"][puntos[0]["point_index"]] if puntos else None
    if nueva == st.session_state["seleccion"]:
        nueva = None
    # Tambien se rehace el grafico: si no, Plotly suma su propio atenuado de seleccion al nuestro.
    elegir(nueva, vaciar=("p1", "p2"))


# --- Barra lateral ----------------------------------------------------------------
with st.sidebar:
    st.header("Filtros")
    paso = 5_000
    lo = int(df["venta_usd"].min()) // paso * paso
    hi = -(-int(df["venta_usd"].max()) // paso) * paso
    st.slider("Presupuesto (USD)", min_value=lo, max_value=hi, step=paso, key="presupuesto",
              format="%d")
    st.selectbox("Tipo", [*T.TIPOS, TODOS], key="tipo",
                 format_func=lambda t: "Todos" if t == TODOS else T.TIPOS[t])
    st.multiselect("Comuna", T.opciones(df, "comuna"), key="comunas",
                   format_func=lambda c: f"Comuna {c}", placeholder="Todas")
    # El barrio se acota por la comuna: se descartan los elegidos que quedaron afuera.
    barrios = T.barrios_de(df, tuple(st.session_state["comunas"]))
    st.session_state["barrios"] = [b for b in st.session_state["barrios"] if b in barrios]
    st.multiselect("Barrio", barrios, key="barrios", format_func=eda.nombre_barrio,
                   placeholder="Todos")
    st.multiselect("Ambientes", T.opciones(df, "ambientes"), key="ambientes",
                   format_func=lambda a: f"{int(a)}", placeholder="Todos")
    st.multiselect("Superficie (m²)", T.opciones(df, "superficie_rango"), key="superficies",
                   placeholder="Todas")
    st.multiselect("Antigüedad (años)", T.opciones(df, "antiguedad_rango"), key="antiguedades",
                   placeholder="Todas")
    st.radio("Métrica", list(METRICAS), key="metrica", horizontal=True)
    st.button("Restablecer", on_click=restablecer, width="stretch")

ss = st.session_state
filtros = T.Filtros(presupuesto=ss["presupuesto"], tipo=None if ss["tipo"] == TODOS else ss["tipo"], comunas=tuple(ss["comunas"]),
                    barrios=tuple(ss["barrios"]), ambientes=tuple(ss["ambientes"]),
                    superficies=tuple(ss["superficies"]), antiguedades=tuple(ss["antiguedades"]))
vista = T.filtrar(df, filtros)


# --- Estilos ----------------------------------------------------------------------
# Pantalla compacta (DISENO_TABLERO.md, "Reglas de diseño de pantalla"): cada pestana
# entra sin scroll en 1440x900.
st.markdown(f"""
<style>
.block-container {{ padding-top: 1rem; padding-bottom: 1rem; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stAppDeployButton"] {{ display: none; }}
.franja {{ background: {C["texto"]}; color: {C["fondo"]}; border-radius: 6px;
           padding: 0.55rem 1rem; display: flex; align-items: baseline;
           justify-content: space-between; flex-wrap: wrap; gap: 0.25rem 1rem; }}
.franja .titulo {{ color: {C["fondo"]}; font-size: 1.45rem; font-weight: 700; }}
.franja .contador {{ font-size: 0.8rem; opacity: 0.9; }}
.subtitulo {{ margin: 0.35rem 0 0.3rem; font-size: 0.95rem; }}
.etiquetas {{ display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.2rem; }}
.etiqueta {{ background: {C["fondo_2"]}; border-radius: 999px; padding: 0.15rem 0.7rem;
             font-size: 0.8rem; cursor: help; position: relative; outline: none; }}
.etiqueta:hover::after, .etiqueta:focus::after {{
    content: attr(data-tip); position: absolute; left: 0; top: calc(100% + 6px); z-index: 1000;
    width: 320px; padding: 0.5rem 0.7rem; border-radius: 6px; background: {C["texto"]};
    color: {C["fondo"]}; font-size: 0.8rem; line-height: 1.35; white-space: normal;
    box-shadow: 0 2px 8px rgba(0,0,0,0.15); }}
.etiqueta:focus {{ box-shadow: 0 0 0 2px {C["principal"]}; }}
[data-testid="stMetric"] {{ background: {C["fondo_2"]}; border-left: 4px solid {C["principal"]};
                            border-radius: 4px; padding: 0.5rem 0.9rem; }}
[data-testid="stMetricValue"] {{ font-size: 1.7rem; }}
.ficha-titulo {{ font-weight: 600; font-size: 0.85rem !important; margin-bottom: 0.3rem !important;
                 border-left: 4px solid {C["seleccion"]}; padding-left: 0.5rem; }}
.ficha {{ display: grid; grid-template-columns: max-content 1fr; gap: 0.1rem 0.8rem; margin: 0 0 0.4rem; }}
.ficha dt, .ficha dd {{ font-size: 0.8rem !important; line-height: 1.35; margin: 0 !important; padding: 0; }}
.limitaciones {{ margin: 0; padding-left: 1.1rem; }}
.limitaciones li {{ font-size: 0.8rem !important; line-height: 1.35; margin-bottom: 0.25rem !important; }}
.fuentes {{ width: 100%; border-collapse: collapse; margin: 0 !important; }}
.fuentes td, .fuentes th {{ font-size: 0.78rem !important; line-height: 1.3; padding: 0.15rem 0.5rem 0.15rem 0 !important;
                           border: none !important; border-bottom: 1px solid {C["fondo_2"]} !important; }}
.fuentes th {{ text-align: left; color: {C["contexto"]}; font-weight: 400; }}
.fuentes td:nth-child(n+2) {{ white-space: nowrap; }}
.ficha dt {{ color: {C["contexto"]}; font-weight: 400; }}
</style>
""", unsafe_allow_html=True)


# --- Encabezado -------------------------------------------------------------------
lo_p, hi_p = S.PRESUPUESTO_USD
LIMITACIONES = [
    ("Precios de publicación",
     "Son precios de publicación, no de cierre. La venta y el alquiler son precios pedidos; "
     "el precio de cierre suele ser menor."),
    ("Una sola inmobiliaria, ~8% más barata",
     "Es la cartera de una sola inmobiliaria, que publica más barato que el mercado: contra "
     "IDECBA, RE/MAX publica alrededor de 8% más barato (9% en los usados). Las rentabilidades "
     "probablemente están del lado alto."),
    ("Cada rentabilidad es una banda",
     "Cada rentabilidad es una banda, no un número. El alquiler es una estimación: su banda "
     "del percentil 10 al 90 contiene al 82% de los alquileres reales."),
]
# Tooltip propio (CSS) y no el atributo title: el nativo tarda, no sale con clic ni en pantallas
# tactiles y no se parece al resto de los tooltips del tablero.
etiquetas = "".join(f'<span class="etiqueta" tabindex="0" data-tip="{html.escape(t, quote=True)}">'
                    f'{html.escape(e)} ⓘ</span>' for e, t in LIMITACIONES)
st.markdown(
    f'<div class="franja"><span class="titulo">¿Conviene comprar para alquilar?</span>'
    f'<span class="contador">Mostrando {num(len(vista))} de {num(len(df))} propiedades · cartera RE/MAX · '
    f'relevada el {T.fechas_relevamiento(df)}</span></div>'
    f'<p class="subtitulo">Tengo entre USD {num(lo_p)} y {num(hi_p)}: ¿conviene comprar para '
    f'alquilar, y si compro, qué?</p>'
    f'<div class="etiquetas">{etiquetas}</div>',
    unsafe_allow_html=True)


# --- Graficos ---------------------------------------------------------------------
ALTO = 340
SIN_BARRA = {"displayModeBar": False}


def estilo(fig: go.Figure, margen_derecho: int = 10, alto: int = ALTO) -> go.Figure:
    fig.update_layout(height=alto, margin=dict(l=8, r=margen_derecho, t=24, b=8),
                      plot_bgcolor=C["fondo"], paper_bgcolor=C["fondo"],
                      font=dict(color=C["texto"]), showlegend=False)
    fig.update_xaxes(showgrid=False, linecolor=C["en_banda"], ticks="outside")
    fig.update_yaxes(gridcolor=C["fondo_2"], zeroline=False)
    return fig


def histograma(v, columna: str, etiqueta: str) -> go.Figure:
    serie = v[columna].dropna()
    x0, x1 = serie.quantile(0.005), serie.quantile(0.995)
    recortada = serie.clip(x0, x1)
    pico = np.histogram(recortada, bins=np.arange(np.floor(x0), x1 + 0.25, 0.25))[0].max()
    fig = go.Figure(go.Histogram(
        x=recortada, xbins=dict(size=0.25), marker_color=C["principal"],
        hovertemplate="%{x} %<br>%{y} propiedades<extra></extra>"))
    fig.add_vrect(x0=PISO, x1=TECHO, fillcolor=C["acento"], opacity=0.55, layer="below", line_width=0,
                  annotation_text=f"banda {pct(PISO)}–{pct(TECHO)}",
                  annotation_position="top right", annotation_font_color=C["texto"])
    mediana = serie.median()
    fig.add_vline(x=mediana, line_dash="dash", line_color=C["texto"], line_width=1,
                  annotation_text=f"mediana {pct(mediana)}", annotation_position="top left",
                  annotation_font_color=C["texto"])
    fig.update_xaxes(title=etiqueta, range=[min(x0, PISO) - 0.5, max(x1, TECHO) + 0.5])
    fig.update_yaxes(title="propiedades", range=[0, pico * 1.15])
    return estilo(fig)


ETAPAS_CORTAS = ["Universo", "Neta > techo", "Pesimista > techo (P1)", "TIR pesimista > techo"]


def barras_etapas(etapas) -> go.Figure:
    """Barras horizontales en escala lineal; la etiqueta afuera deja leer el 18 y el 4."""
    cantidades = [n for _, n in etapas]
    universo = cantidades[0]
    textos = [f"{num(n)} · {pct(n / universo * 100, 1) if universo else '–'}" for n in cantidades]
    # Las dos ultimas etapas son candidatas "a verificar": color de alerta.
    colores = [C["principal"], C["principal"], C["alerta"], C["alerta"]]
    fig = go.Figure(go.Bar(
        y=ETAPAS_CORTAS, x=cantidades, orientation="h", marker_color=colores,
        text=textos, textposition="outside", cliponaxis=False,
        textfont_color=C["texto"], customdata=[e for e, _ in etapas],
        hovertemplate="%{customdata}: %{x:,} propiedades<extra></extra>"))
    for etapa in ETAPAS_CORTAS:
        fig.add_annotation(x=0, y=etapa, text=etapa, xanchor="left", yshift=27, showarrow=False,
                           font=dict(color=C["texto"], size=12))
    fig.update_layout(separators=",.", bargap=0.55)
    fig.update_yaxes(autorange="reversed", showticklabels=False, showgrid=False)
    fig.update_xaxes(visible=False, range=[0, max(universo, 1) * 1.02])
    return estilo(fig, margen_derecho=95)


ALTO_2 = 470                 # ranking y H1, lado a lado debajo del mapa
ALTO_MAPA = 460              # el mapa va primero y a todo el ancho


def puntos_barrio(rk, elegidos: tuple) -> go.Figure:
    """Neta (con su banda) y TIR medianas por barrio; los elegidos en el filtro, resaltados."""
    resaltado = rk["barrio"].isin(elegidos) if elegidos else pd.Series(True, index=rk.index)
    fig = go.Figure()
    fig.add_vrect(x0=PISO, x1=TECHO, fillcolor=C["acento"], opacity=0.55, layer="below", line_width=0)
    for grupo, opacidad in ((~resaltado, 0.25), (resaltado, 1.0)):
        sub = rk[grupo]
        if sub.empty:
            continue
        leyenda = opacidad == 1.0
        xs, ys = [], []
        for nombre, lo, hi in zip(sub["barrio_nombre"], sub["neta_min"], sub["neta_max"]):
            xs += [lo, hi, None]
            ys += [nombre, nombre, None]
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=C["principal"], width=2),
                                 opacity=opacidad * 0.45, name="Banda neta", showlegend=leyenda,
                                 hoverinfo="skip"))
        fig.add_trace(go.Scatter(
            x=sub["rent_neta"], y=sub["barrio_nombre"], mode="markers", opacity=opacidad,
            marker=dict(color=C["principal"], size=8), name="Neta", showlegend=leyenda,
            customdata=sub[["neta_min", "neta_max", "n_ventas"]],
            hovertemplate="%{y}: neta %{x:.2f}% (banda %{customdata[0]:.2f}% a %{customdata[1]:.2f}%)"
                          "<br>%{customdata[2]} ventas<extra></extra>"))
        fig.add_trace(go.Scatter(
            x=sub["tir_5a"], y=sub["barrio_nombre"], mode="markers", opacity=opacidad,
            marker=dict(color=C["secundario"], size=7, symbol="diamond"), name="TIR 5 años",
            showlegend=leyenda, hovertemplate="%{y}: TIR %{x:.2f}%<extra></extra>"))
    # El orden del eje es el del ranking (por neta), no el de aparicion de las trazas.
    nombres = list(rk["barrio_nombre"])
    marcados = [f"<b>{n}</b>" if r and elegidos else n for n, r in zip(nombres, resaltado)]
    fig.update_yaxes(categoryorder="array", categoryarray=nombres, tickvals=nombres, ticktext=marcados,
                     tickfont=dict(size=11), showgrid=False)
    fig.update_xaxes(title="% anual (mediana)", showgrid=True, gridcolor=C["fondo_2"])
    estilo(fig, alto=ALTO_2)
    # La leyenda va en el hueco de abajo a la derecha (los barrios caros no llegan a la banda).
    fig.update_layout(showlegend=True, separators=",.", margin=dict(l=8, r=10, t=8, b=8),
                      legend=dict(x=1, xanchor="right", y=0, yanchor="bottom", itemwidth=30,
                                  bgcolor="rgba(255,255,255,0.9)", font=dict(size=11)))
    return fig


def mapa(v, columna: str, metrica: str, seleccion=None) -> go.Figure:
    con = v.dropna(subset=["latitud", "longitud"])
    pos = T.posicion_banda(con[columna])
    fig = go.Figure()
    # Primero la mayoria (debajo del piso), arriba las que pasan: si no, las tapa.
    for clave, (nombre, color) in T.POSICIONES.items():
        sub = con[pos == clave]
        fig.add_trace(go.Scattermap(
            lat=sub["latitud"], lon=sub["longitud"], mode="markers", name=f"{nombre} · {num(len(sub))}",
            marker=dict(size=6, color=color, opacity=0.8),
            customdata=np.column_stack([sub["barrio_nombre"], sub["venta_usd"], sub[columna],
                                        sub["neta_min_pct"], sub["neta_max_pct"]]),
            hovertemplate="%{customdata[0]} · USD %{customdata[1]:,.0f}<br>"
                          f"{metrica} " "%{customdata[2]:.2f}% · banda de la neta "
                          "%{customdata[3]:.2f}% a %{customdata[4]:.2f}%<extra></extra>"))
    elegida = con[con["id_aviso"] == seleccion]
    if not elegida.empty:
        # Scattermap no tiene borde de marcador: un circulo blanco 4 px mas grande hace de borde
        # de 2 px. Va al final, asi queda encima; el doble de grande que el resto (6 px).
        for tam, color, nombre in ((16, C["fondo"], None), (12, C["seleccion"], "Propiedad elegida")):
            fig.add_trace(go.Scattermap(lat=elegida["latitud"], lon=elegida["longitud"], mode="markers",
                                        marker=dict(size=tam, color=color), name=nombre,
                                        showlegend=nombre is not None, hoverinfo="skip"))
    fig.update_layout(height=ALTO_MAPA, margin=dict(l=0, r=0, t=0, b=0), separators=",.",
                      map=dict(style="carto-positron", center=dict(lat=-34.603, lon=-58.445), zoom=10.9),
                      legend=dict(orientation="v", x=0.01, y=0.99, yanchor="top", bgcolor="rgba(255,255,255,0.85)",
                                  font=dict(size=11, color=C["texto"])),
                      paper_bgcolor=C["fondo"])
    return fig


def dispersion_h1(h: dict) -> go.Figure:
    b = h["barrios"]
    fig = go.Figure()
    fig.add_hrect(y0=PISO, y1=TECHO, fillcolor=C["acento"], opacity=0.55, layer="below", line_width=0,
                  annotation_text=f"banda {pct(PISO)}–{pct(TECHO)}", annotation_position="top right",
                  annotation_font_color=C["texto"])
    x = np.array([b["m2"].min(), b["m2"].max()])
    fig.add_trace(go.Scatter(x=x, y=h["ordenada"] + h["pendiente_m2"] * x, mode="lines",
                             line=dict(color=C["contexto"], dash="dash", width=1.5), hoverinfo="skip"))
    fig.add_trace(go.Scatter(
        x=b["m2"], y=b["bruta"], mode="markers", marker=dict(color=C["principal"], size=9),
        customdata=b[["barrio_nombre", "n"]],
        hovertemplate="%{customdata[0]}: USD %{x:,.0f}/m² · bruta %{y:.2f}%<br>%{customdata[1]} ventas"
                      "<extra></extra>"))
    fig.update_xaxes(title="USD por m² (mediana del barrio)")
    fig.update_yaxes(title="Rentabilidad bruta (% anual, mediana)")
    fig.update_layout(separators=",.")
    return estilo(fig, alto=ALTO_2)


AVISO_VIEJO = (f"Aviso de RE/MAX relevado el {T.fechas_relevamiento(df)}. Si ya se vendió o "
               "se dio de baja, el link abre la portada de RE/MAX.")
ANCHO_BARRA_P2 = 0.85          # en unidades del eje: 1 - bargap
ALTO_3 = 540                 # rangos de la frontera P2: 140 barras en una pantalla


def rangos_p2(fr, seleccion) -> go.Figure:
    """Una barra de neta_min a neta_max por propiedad, ordenadas por ancho de banda."""
    elegida = (fr["id_aviso"] == seleccion).to_numpy()
    hay_elegida = bool(elegida.any())
    # Con una elegida, el resto se atenua sin perder su color.
    alfa = 0.35 if hay_elegida else 1.0
    colores = np.where(fr["p1_comprar"], rgba(C["alerta"], alfa), rgba(C["principal"], alfa))
    fig = go.Figure()
    # Con 140 barras encima, la franja sola no se ve: se marcan tambien sus bordes por arriba.
    fig.add_vrect(x0=PISO, x1=TECHO, fillcolor=C["acento"], opacity=0.55, layer="below", line_width=0)
    for x in (PISO, TECHO):
        fig.add_vline(x=x, line_color=C["alerta"], line_width=1, line_dash="dot", layer="above")
    fig.add_annotation(x=TECHO, y=1, yref="paper", yanchor="bottom", xanchor="left", showarrow=False,
                       text=f"banda {pct(PISO)}–{pct(TECHO)}", font=dict(color=C["texto"], size=11))
    # Una sola traza clickeable: el indice del punto es la fila de fr. La leyenda va aparte.
    fig.add_trace(go.Bar(
        y=np.arange(len(fr)), x=fr["ancho"], base=fr["neta_min_pct"], orientation="h",
        marker=dict(color=colores),
        customdata=np.column_stack([fr["barrio_nombre"], fr["venta_usd"], fr["sup_total_m2"],
                                    fr["neta_min_pct"], fr["neta_max_pct"], fr["ancho"]]),
        hovertemplate="%{customdata[0]} · USD %{customdata[1]:,.0f} · %{customdata[2]:.0f} m²<br>"
                      "neta %{customdata[3]:.2f}% a %{customdata[4]:.2f}% "
                      "(ancho %{customdata[5]:.2f} pp)<extra></extra>",
        showlegend=False))
    if hay_elegida:
        # Traza aparte, encima y mas gruesa (sin borde: en barras finas tapa el relleno).
        i = int(np.flatnonzero(elegida)[0])
        fila = fr.iloc[i]
        fig.add_trace(go.Bar(y=[i], x=[fila["ancho"]], base=[fila["neta_min_pct"]], orientation="h",
                             width=[ANCHO_BARRA_P2 * 2.5], marker_color=C["seleccion"], showlegend=False,
                             hovertemplate=f"{html.escape(fila['barrio_nombre'])} (elegida)<extra></extra>"))
        fig.add_annotation(x=fila["neta_max_pct"], y=i, text="Elegida", xanchor="left", xshift=4,
                           showarrow=False, font=dict(color=C["texto"], size=11))
    leyenda = [("A verificar (P1)", C["alerta"]), ("Resto de la frontera", C["principal"])]
    if hay_elegida:
        leyenda.append(("Propiedad elegida", C["seleccion"]))
    for nombre, color in leyenda:
        fig.add_trace(go.Bar(x=[None], y=[None], orientation="h", marker_color=color, name=nombre,
                             hoverinfo="skip"))
    estilo(fig, alto=ALTO_3)
    # overlay: con el modo por defecto (group) la traza de la elegida parte cada fila en dos,
    # las barras se corren y los clics caen en el hueco.
    fig.update_layout(bargap=1 - ANCHO_BARRA_P2, barmode="overlay", separators=",.", showlegend=True,
                      clickmode="event+select",
                      margin=dict(l=8, r=10, t=24, b=8),
                      legend=dict(x=1, xanchor="right", y=0, yanchor="bottom", bgcolor="rgba(255,255,255,0.9)",
                                  font=dict(size=11)))
    fig.update_yaxes(autorange="reversed", showticklabels=False, showgrid=False,
                     title="de la banda más angosta (arriba) a la más ancha")
    fig.update_xaxes(title="Neta anual (%): de la pesimista a la optimista", showgrid=True,
                     gridcolor=C["fondo_2"])
    return fig


def ficha_html(f) -> str:
    """La ficha de la propiedad elegida: todo lo que hace falta para ir a verificarla."""
    e = html.escape
    filas = [
        ("Barrio", e(f["barrio_nombre"])),
        ("Precio", f"USD {num(f['venta_usd'])} · {num(f['sup_total_m2'])} m² · "
                   f"USD {num(f['venta_m2_usd'])}/m² ({num((f['m2_relativo_celda'] - 1) * 100)}% "
                   "contra su celda)"),
        ("Alquiler estimado", f"USD {num(f['alquiler_est_usd_mes'])}/mes (p10–p90: "
                              f"{num(f['alquiler_p10_usd_mes'])} a {num(f['alquiler_p90_usd_mes'])})"),
        ("Costos de entrada", f"{pct(f['costos_entrada_pct'])} del precio"),
        ("Neta", f"<b>{pct(f['rent_neta_pct'])}</b> (banda {pct(f['neta_min_pct'])} a "
                 f"{pct(f['neta_max_pct'])})"),
        ("TIR 5 años", f"{pct(f['tir_5a_pct'])} (pesimista {pct(f['tir_5a_min_pct'])})"),
        ("Transporte", f"{e(str(f['modo_cercano']).capitalize())} a {num(f['dist_transporte_m'])} m"),
        ("Publicación típica", f"{num(f['dias_publicacion_ambientes'])} días"),
    ]
    cuerpo = "".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in filas)
    return (f'<p class="ficha-titulo">{e(str(f["titulo"]))} · '
            f'<a href="{e(str(f["url"]), quote=True)}" target="_blank">ver aviso ↗</a></p>'
            f'<dl class="ficha">{cuerpo}</dl>')


ALTO_4 = 500


@st.cache_data
def cargar_p3():
    return T.cargar_p3()


@st.cache_data
def ocupacion_airbnb():
    return T.ocupacion_airbnb()


def lineas_p3(sub, ocupacion_ia: float) -> go.Figure:
    """Celdas (de 47) donde gana el temporal segun la ocupacion, una linea por gestion."""
    celdas = int(sub["celdas"].iloc[0])
    # Etiquetas directas donde las lineas estan mas separadas (al final se juntan en 47). La
    # de arriba va a la izquierda de su tramo de subida, a media altura (arriba estan los
    # rotulos de las referencias); la de abajo, debajo y a la derecha de su punto.
    piv = sub.pivot(index="ocupacion_sostenible_pct", columns="gestion", values="gana_temporal")
    x_etiqueta = (piv.max(axis=1) - piv.min(axis=1)).idxmax()
    arriba = piv.loc[x_etiqueta].idxmax()
    fig = go.Figure()
    for gestion, (nombre, color) in T.GESTIONES.items():
        g = sub[sub["gestion"] == gestion]
        fig.add_trace(go.Scatter(
            x=g["ocupacion_sostenible_pct"], y=g["gana_temporal"], mode="lines+markers", name=nombre,
            line=dict(color=color, width=2.5), marker=dict(color=color, size=7),
            hovertemplate=f"{nombre}: con %{{x:.0f}}% de ocupación gana en %{{y}} de {celdas} celdas"
                          "<extra></extra>"))
        if gestion == arriba:
            medio = (g["gana_temporal"] - celdas * 0.45).abs().idxmin()
            fig.add_annotation(x=g.loc[medio, "ocupacion_sostenible_pct"], y=g.loc[medio, "gana_temporal"],
                               text=nombre, showarrow=False, xanchor="right", xshift=-8,
                               font=dict(color=color, size=12))
        else:
            fig.add_annotation(x=x_etiqueta, y=piv.loc[x_etiqueta, gestion], text=nombre, showarrow=False,
                               xanchor="left", xshift=8, yanchor="top", yshift=-4,
                               font=dict(color=color, size=12))
    for x, texto in ((ocupacion_ia, f"Inside Airbnb<br>{pct(ocupacion_ia, 1)}"),
                     (S.OCUPACION_REF_PCT, f"Prensa<br>{pct(S.OCUPACION_REF_PCT, 0)}")):
        fig.add_vline(x=x, line_dash="dash", line_color=C["contexto"], line_width=1.5)
        fig.add_annotation(x=x, y=1, yref="paper", text=texto, showarrow=False, xanchor="left", xshift=4,
                           yanchor="top", align="left", font=dict(color=C["texto"], size=11))
    estilo(fig, margen_derecho=20, alto=ALTO_4)
    fig.update_xaxes(title="Ocupación sostenible del alquiler temporal (% del año)", ticksuffix="%",
                     range=[min(ocupacion_ia, sub["ocupacion_sostenible_pct"].min()) - 4,
                            sub["ocupacion_sostenible_pct"].max() + 3])
    fig.update_yaxes(title=f"Celdas donde gana el temporal (de {celdas})", range=[-1, celdas + 2])
    fig.update_layout(separators=",.")
    return fig


ALTO_5 = 560

# README, "Limitaciones", y el informe (causalidad). Las tres primeras son las del encabezado.
LIMITACIONES_COMPLETAS = [
    ("Precios de publicación, no de cierre", "del lado de la venta y del alquiler."),
    ("Una sola inmobiliaria", "RE/MAX publica alrededor de 8% más barato que el mercado y está sesgada en "
                              "cobertura geográfica: las rentabilidades probablemente están del lado alto."),
    ("Cada rentabilidad es una banda", "el alquiler es estimado; su banda p10–p90 contiene al 82% de los "
                                       "alquileres reales."),
    ("Casas y PH fuera de las recomendaciones", "hay muy pocos alquileres observados."),
    ("Sin apreciación, costos de salida ni riesgo legal", "la TIR supone reventa al mismo precio en "
                                                          "dólares; el riesgo legal no tiene fuente."),
    ("Liquidez de toda la Ciudad", "el tiempo de publicación de IDECBA es por ambientes, no por barrio ni "
                                   "por propiedad."),
    ("No es causalidad", "comparar dentro del estrato controla por zona, tamaño y tipología, no por todo."),
]


@st.cache_data
def cargar_sensibilidad():
    return T.cargar_sensibilidad()


@st.cache_data
def cargar_fuentes():
    return T.fuentes()


def barras_sensibilidad(s) -> go.Figure:
    """Cuantas pasan P1 y P1 con entrada en cada escenario; los iguales a la base, marcados."""
    fig = go.Figure()
    for i in np.flatnonzero(s["es_base"].to_numpy()):
        fig.add_hrect(y0=i - 0.5, y1=i + 0.5, fillcolor=C["fondo_2"], line_width=0, layer="below")
    for col, nombre, color in (("n_p1", "Pasan P1 (neta pesimista)", C["alerta"]),
                               ("n_p1_con_entrada", "P1 con costos de entrada (TIR pesimista)", C["principal"])):
        fig.add_trace(go.Bar(
            y=np.arange(len(s)), x=s[col], orientation="h", name=nombre, marker_color=color,
            text=s[col], textposition="outside", cliponaxis=False, textfont=dict(color=C["texto"], size=12),
            customdata=s["escenario"], hovertemplate="%{customdata}: %{x} propiedades<extra>" + nombre + "</extra>"))
    marcas = [f"<b>{e}</b>" if b else e for e, b in zip(s["escenario"], s["es_base"])]
    estilo(fig, margen_derecho=30, alto=ALTO_5)
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.05, showlegend=True,
                      legend=dict(orientation="h", x=0, y=1.0, yanchor="bottom", font=dict(size=11)),
                      margin=dict(l=8, r=30, t=30, b=8))
    fig.update_yaxes(tickvals=np.arange(len(s)), ticktext=marcas, autorange="reversed", showgrid=False,
                     tickfont=dict(size=11))
    fig.update_xaxes(title="Propiedades que pasan", showgrid=True, gridcolor=C["fondo_2"])
    return fig


# --- Pestanas ---------------------------------------------------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["¿Conviene comprar?", "¿Dónde?", "¿Qué comprar?",
                                        "¿Tradicional o temporal?", "Supuestos y alcance"])

with tab1:
    k = T.kpis(vista)
    if k["n"] == 0:
        st.info("Ninguna propiedad cumple estos filtros. Probá ampliarlos o tocá **Restablecer**.")
    else:
        if k["n"] < MIN_CONFIABLE:
            st.warning(f"Quedan {k['n']} propiedades: con menos de {MIN_CONFIABLE} la mediana es "
                       "poco confiable.")
        sin_soporte = filtros.tipo in T.SIN_SOPORTE

        c1, c2, c3, c4 = st.columns(4)
        # La banda va en la tarjeta, en gris y sin flecha: GUIA_TABLERO.md pide no mostrar
        # nunca la neta sola.
        banda = f"{pct(k['neta_min_mediana'])} a {pct(k['neta_max_mediana'])}"
        c1.metric("Neta mediana", pct(k["neta_mediana"]), delta=f"banda {banda}",
                  delta_color="off", delta_arrow="off", height="stretch",
                  help="Rentabilidad neta anual mediana. La banda es la mediana de la neta con el "
                       "alquiler en sus percentiles 10 y 90: cada rentabilidad es una banda, no un número.")
        c2.metric("TIR a 5 años mediana", pct(k["tir_mediana"]), height="stretch",
                  help="Tasa interna de retorno a 5 años, con los costos de entrada de la compra.")
        c3.metric("Neta sobre el piso", pct(k["pct_sobre_piso"], 1), height="stretch",
                  help=f"Propiedades con neta de {pct(PISO)} o más, el piso de la banda de retorno mínimo.")
        c4.metric("Distancia al piso", f"{num(k['pp_al_piso'], 2)} pp", height="stretch",
                  help=f"Neta mediana menos el piso de {pct(PISO)} que paga la renta fija en dólares "
                       "(ON de YPF 2031 y Pampa 2037).")

        g1, g2 = st.columns([3, 2])
        columna, etiqueta = METRICAS[ss["metrica"]]
        with g1, st.container(border=True):
            st.markdown(f"**Distribución de la {ss['metrica'].lower()}**",
                        help=f"Cada barra cuenta propiedades por su {etiqueta.split(' (')[0].lower()} "
                             "central; la de cada una es una banda, no un número. La franja amarilla "
                             f"es la banda de retorno mínimo, {pct(PISO)} a {pct(TECHO)}: lo que paga "
                             "la renta fija en dólares (ON de YPF 2031 y Pampa 2037).")
            st.plotly_chart(histograma(vista, columna, etiqueta), width="stretch", config=SIN_BARRA)
        with g2, st.container(border=True):
            if sin_soporte:
                st.warning(f"El modelo casi no tiene alquileres observados de {T.TIPOS[filtros.tipo]}: "
                           "sus rentabilidades son extrapolaciones y no entran en las recomendaciones.")
            else:
                st.markdown("**¿Cuántas pasan cada vara?**",
                            help="Solo departamentos dentro del presupuesto y del soporte del modelo. "
                                 "Universo → neta central sobre el techo de la banda → neta pesimista "
                                 "sobre el techo (P1) → TIR pesimista, con costos de entrada, sobre "
                                 "el techo. El porcentaje es sobre el universo.")
                st.plotly_chart(barras_etapas(T.embudo(vista)), width="stretch", config=SIN_BARRA)
                st.caption("Las que pasan P1 no son una recomendación: hay que verificar por qué son baratas.")

with tab2:
    # El mapa primero y a todo el ancho; debajo, ranking y H1 lado a lado. Esta pestana
    # tiene scroll a proposito (DISENO_TABLERO.md, seccion 6).
    with st.container(border=True):
        columna, etiqueta = METRICAS[ss["metrica"]]
        st.markdown(f"**{ss['metrica']} de cada propiedad frente a la banda**",
                    help=f"Cada punto es una propiedad, coloreada según su {ss['metrica'].lower()} "
                         f"central: debajo del piso ({pct(PISO)}), dentro de la banda o sobre el techo "
                         f"({pct(TECHO)}). Al pasar el mouse se ve la banda de su neta.")
        if vista.empty:
            st.info("Ninguna propiedad cumple estos filtros.")
        else:
            st.plotly_chart(mapa(vista, columna, ss["metrica"], ss["seleccion"]), width="stretch",
                            config=SIN_BARRA)
            faltan = T.sin_coordenadas(vista)
            if faltan:
                st.caption(f"{faltan} {'aviso' if faltan == 1 else 'avisos'} sin coordenadas no "
                           f"{'aparece' if faltan == 1 else 'aparecen'} en el mapa.")
            else:
                st.caption("Todas las propiedades tienen coordenadas.")
    a, c = st.columns(2)
    with a, st.container(border=True):
        st.markdown("**Neta y TIR por barrio**",
                    help="Barrios con 30 ventas o más (`ranking_barrios.csv`), ordenados por neta "
                         "mediana. La línea fina es la banda mediana de la neta de cada barrio. Los "
                         "barrios elegidos en el filtro se resaltan; el resto queda atenuado.")
        st.plotly_chart(puntos_barrio(cargar_ranking(), filtros.barrios), width="stretch", config=SIN_BARRA)
        st.caption("Esta vista no responde a los filtros.")
    with c, st.container(border=True):
        st.markdown("**¿El m² caro rinde menos? (H1)**",
                    help="Un punto por barrio con 30 ventas o más con estos filtros: mediana del precio "
                         "del m² contra mediana de la rentabilidad bruta. La línea es la pendiente de "
                         "Theil-Sen. La bruta todavía no descuenta vacancia ni gastos; la franja es la "
                         "banda de retorno mínimo, que se compara con la neta.")
        hh = T.h1(vista)
        if np.isnan(hh["pendiente"]):
            st.info("Con estos filtros quedan menos de 3 barrios con 30 ventas o más: "
                    "no hay pendiente que estimar.")
        else:
            st.plotly_chart(dispersion_h1(hh), width="stretch", config=SIN_BARRA)
            st.caption(f"{num(hh['pendiente'], 2)} pp de bruta por cada USD 500/m² del barrio "
                       f"(IC 95% {num(hh['ic'][0], 2)} a {num(hh['ic'][1], 2)}).")

with tab3:
    universo = vista[vista["universo_decision"]]
    if filtros.tipo in T.SIN_SOPORTE:
        st.warning(f"El modelo casi no tiene alquileres observados de {T.TIPOS[filtros.tipo]}: "
                   "no entran en P1 ni en P2.")
    elif universo.empty:
        st.info("Ninguna propiedad del universo de la decisión cumple estos filtros.")
    else:
        p1 = T.p1_tabla(vista)
        fr = T.frontera_p2(vista)
        ss["_ids_p1"], ss["_ids_p2"] = list(p1["id_aviso"]), list(fr["id_aviso"])
        izq, der = st.columns([10, 11])
        with izq, st.container(border=True):
            st.markdown(f"**Frontera P2: {num(len(fr))} que nadie supera con claridad**",
                        help="Cada barra va de la neta pesimista a la optimista de una propiedad. Están "
                             "ordenadas por ancho de banda, nunca por rentabilidad: la de arriba es la "
                             "estimación más precisa, no la mejor. Con filtros se muestra la parte de la "
                             "frontera que los cumple. Clic en una barra para ver su ficha.")
            if fr.empty:
                st.info("Ninguna propiedad de la frontera cumple estos filtros.")
            else:
                st.plotly_chart(rangos_p2(fr, ss["seleccion"]), width="stretch", config=SIN_BARRA,
                                key=clave("grafico_p2"), on_select=elegir_de_p2, selection_mode="points")
                st.caption("Entre estas propiedades ninguna le gana con claridad a otra.")
        with der:
            with st.container(border=True):
                st.markdown("**A verificar (P1)**",
                            help=f"Departamentos del universo cuya neta pesimista supera el techo de la "
                                 f"banda ({pct(TECHO)}). No es una recomendación de compra. Clic en una "
                                 "fila para ver su ficha.")
                if p1.empty:
                    st.info("Ninguna propiedad pasa P1 con estos filtros.")
                else:
                    st.caption(f"⚠ Cuestan ~{T.descuento_p1(p1)}% menos por m² que su celda: verificar "
                               "por qué antes de decidir.")
                    tabla = pd.DataFrame({
                        "Barrio": p1["barrio_nombre"],
                        "USD": p1["venta_usd"].map(num),
                        "m²": p1["sup_total_m2"].map(num),
                        "Neta pes.": p1["neta_min_pct"].map(pct),
                        "vs. celda": ((p1["m2_relativo_celda"] - 1) * 100).map(lambda x: f"{num(x)}%"),
                        "Aviso": p1["url"],
                    })
                    st.dataframe(tabla, hide_index=True, width="stretch", height=212, key=clave("tabla_p1"),
                                 on_select=elegir_de_p1, selection_mode="single-row",
                                 column_config={
                                     # Anchos en px: con la ficha al lado, la tabla no puede scrollear en x.
                                     "Barrio": st.column_config.TextColumn(width=115),
                                     "USD": st.column_config.TextColumn(width=68),
                                     "m²": st.column_config.TextColumn(width=40),
                                     "Neta pes.": st.column_config.TextColumn(width=66, help="Neta pesimista: con el "
                                                                              "alquiler en su percentil 10."),
                                     "Aviso": st.column_config.LinkColumn(display_text="ver ↗", width=46,
                                                                         help=AVISO_VIEJO),
                                     "vs. celda": st.column_config.TextColumn(width=62,
                                         help="Precio del m² contra el mediano de su barrio y tramo de "
                                              "superficie. Por debajo de -30%, verificar por qué es barata.")})
            with st.container(border=True):
                elegida = T.fila(universo, ss["seleccion"])
                st.markdown("**Ficha de la propiedad**",
                            help="La publicación típica es la de toda la Ciudad para esa cantidad de "
                                 "ambientes (IDECBA): no distingue barrio ni propiedad. " + AVISO_VIEJO)
                if elegida is None:
                    st.caption("Elegí una fila de P1 o una barra de la frontera P2.")
                else:
                    st.markdown(ficha_html(elegida), unsafe_allow_html=True)

with tab4:
    p3 = cargar_p3()
    opciones_vac = T.vacancias(p3)
    st.session_state.setdefault("vacancia_p3", S.VACANCIA_PCT)
    izq, der = st.columns([3, 1.2])
    with der:
        with st.container(border=True):
            st.select_slider(
                "Vacancia del alquiler tradicional", options=opciones_vac, key="vacancia_p3",
                format_func=lambda v: f"{pct(v, 2 if v % 1 else 0)}" + (" (base)" if v == S.VACANCIA_PCT else ""),
                help="Meses sin inquilino por año en el alquiler tradicional. La base sale de "
                     "supuestos.py: un mes vacío cada contrato de dos años. Más vacancia le resta al "
                     "tradicional y acerca al temporal.")
        sub = T.p3_vacancia(p3, ss["vacancia_p3"])
        eq = T.equilibrio(sub)
        for gestion, (nombre, _) in T.GESTIONES.items():
            st.metric(f"Equilibrio · {nombre.lower()}", pct(eq[gestion], 1),
                      help=f"Ocupación mediana con la que el temporal empata al tradicional, con "
                           f"gestión {nombre.lower()}. Por debajo, conviene el tradicional.")
        st.markdown("**Conviene el tradicional**, salvo autogestión con evidencia de más de la mitad "
                    "del año ocupado.")
    with izq, st.container(border=True):
        st.markdown("**¿En cuántas celdas gana el temporal?**",
                    help="Cada celda es un barrio y una cantidad de dormitorios con datos de los dos "
                         "mercados. Para cada ocupación sostenible del temporal se cuentan las celdas "
                         "donde su neta supera a la del tradicional. Inside Airbnb estima la ocupación "
                         "desde las reseñas; la prensa (La Nación, 29-05-2025) informa 53% para CABA.")
        st.plotly_chart(lineas_p3(sub, ocupacion_airbnb()), width="stretch", config=SIN_BARRA)
        st.caption("Esta vista no responde a los filtros.")

with tab5:
    izq, der = st.columns([1.15, 1])
    with izq, st.container(border=True):
        st.markdown("**¿Cuánto cambian P1 con cada supuesto?**",
                    help="Cada fila cambia un supuesto respecto de la base, más los dos extremos que los "
                         "combinan. Las filas en negrita y con fondo son iguales a la base. P1 con costos "
                         "de entrada exige que también la TIR pesimista a 5 años supere el techo de la banda.")
        st.plotly_chart(barras_sensibilidad(cargar_sensibilidad()), width="stretch", config=SIN_BARRA)
        st.caption("Esta vista no responde a los filtros.")
    with der:
        with st.container(border=True):
            st.markdown("**Limitaciones**")
            st.markdown('<ul class="limitaciones">' + "".join(
                f"<li><b>{html.escape(t)}</b>: {html.escape(d)}</li>" for t, d in LIMITACIONES_COMPLETAS)
                + "</ul>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("**Fuentes y fecha de los datos**",
                        help="Período que cubre cada fuente y fecha de descarga, leídos de sus tablas en "
                             "data/external/.")
            fu = cargar_fuentes()
            filas = [("RE/MAX: avisos", T.fechas_relevamiento(df), T.fechas_relevamiento(df))] + [
                (r.fuente, r.periodo, r.descarga) for r in fu.itertuples()]
            st.markdown('<table class="fuentes"><tr><th>Fuente</th><th>Período</th><th>Descarga</th></tr>'
                        + "".join(f"<tr><td>{html.escape(a)}</td><td>{html.escape(b)}</td>"
                                  f"<td>{html.escape(c)}</td></tr>" for a, b, c in filas)
                        + "</table>", unsafe_allow_html=True)
            st.caption("Detalle de cada fuente en informe/FUENTES_EXTERNAS.md.")
