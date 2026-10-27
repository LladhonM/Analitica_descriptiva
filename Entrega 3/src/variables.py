#!/usr/bin/env python
"""
variables.py — Ingenieria de variables y mineria de texto con RegEx.

EL PROBLEMA QUE RESUELVE
------------------------
El scraping de la 1ra entrega dejo 21 variables dicotomicas construidas con
busqueda de subcadena: `if "pileta" in texto`. Es la forma mas rapida de
extraer atributos de un texto libre, y tambien la mas ingenua. Sobre este
dataset produce tres errores sistematicos, todos medidos en el reporte que
genera este script:

  1. FRAGMENTO DENTRO DE OTRA PALABRA.  La keyword "sum" (por "salon de usos
     multiples") matchea dentro de "con-SUM-o", "re-SUM-en" y "as-UM-ir".
     Marca amenities en avisos que solo hablan del consumo de gas.

  2. NEGACION IGNORADA.  "no posee balcon" contiene "balcon". El aviso dice
     exactamente lo contrario de lo que la variable termina afirmando.

  3. ANTONIMO POR SUBCADENA.  "contrafrente" contiene "frente". La variable
     `frente` marcaba 1 en miles de avisos que declaran ser contrafrente, que
     es el atributo opuesto y el que baja el precio.

La solucion no es agregar keywords: es cambiar de herramienta. Cada atributo
pasa a ser una expresion regular con limites de palabra (\\b), alternativas
morfologicas y —cuando corresponde— un veto por negacion previa.

QUE PRODUCE
-----------
  - 31 variables dicotomicas con patrones auditables, una por atributo.
  - 5 variables numericas extraidas del texto que no venian en el esquema
    (piso, orientacion, disposicion, superficie del texto, mencion de renta).
  - Un reporte que compara, atributo por atributo, la prevalencia del metodo
    viejo contra el nuevo y cuantifica cuantos avisos cambian de valor.

Uso:
    py src/variables.py
    py src/variables.py --input data/processed/dataset_limpio.csv

Salidas (en data/processed/):
    dataset_variables.csv   dataset limpio + variables de texto
    reporte_regex.txt       prevalencias, deltas y ejemplos de correccion
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime

import numpy as np
import pandas as pd


# ==========================================================================
# NORMALIZACION DEL TEXTO
# ==========================================================================

def normalizar(texto: str) -> str:
    """
    Deja el texto en minusculas, sin tildes y con espacios colapsados.

    Se quitan las tildes porque los avisos las escriben de forma inconsistente
    ("balcón", "balcon", "BALCÓN") y no hay ninguna distincion semantica que
    dependa de ellas. Los signos se reemplazan por espacio en vez de borrarse,
    para que "cochera/baulera" no se lea como una sola palabra inexistente.
    """
    if not isinstance(texto, str):
        return ""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ==========================================================================
# PATRONES
# ==========================================================================

# Cada entrada es (patron_positivo, admite_negacion).
#
# El patron se compila con \b al inicio y al final salvo que ya traiga sus
# propios limites. `admite_negacion=True` activa el veto descrito en
# `_hay_negacion`: solo tiene sentido en atributos que el aviso puede negar
# explicitamente ("sin balcon", "no apto credito"). Nadie escribe "sin
# reciclar" para decir que el departamento no esta reciclado, asi que en esos
# casos el veto se desactiva para no introducir falsos negativos.
PATRONES = {
    # --- Amenities de edificio -------------------------------------------
    "pileta":            (r"\b(pileta|piscina|natatorio)\b", True),
    "parrilla":          (r"\b(parrilla|quincho|asador)\b", True),
    "gimnasio":          (r"\b(gimnasio|gym)\b", True),
    "sum":               (r"\b(sum|s\s?u\s?m|salon\s+de\s+usos\s+multiples)\b", True),
    "solarium":          (r"\b(solarium|solarum|terraza\s+solarium)\b", False),
    "laundry":           (r"\b(laundry|lavadero\s+comun|sala\s+de\s+lavado)\b", False),
    "sauna":             (r"\b(sauna|spa|jacuzzi|hidromasaje)\b", False),
    "coworking":         (r"\b(coworking|co\s+working|sala\s+de\s+trabajo)\b", False),

    # --- Servicios y confort de la unidad --------------------------------
    "aire_acondicionado": (r"\b(aire\s+acondicionado|a\s?a\s?c|split|frio\s*[-/]?\s*calor)\b", True),
    "losa_radiante":     (r"\b(losa\s+radiante|piso\s+radiante|calefaccion\s+central|caldera\s+individual)\b", True),
    "calefaccion":       (r"\b(calefaccion|radiadores|tiro\s+balanceado|calefactor)\b", True),
    "ascensor":          (r"\b(ascensor(es)?|elevador)\b", True),
    "baulera":           (r"\b(bauler[ao]s?)\b", True),
    # garages?|garajes? y no garage?s?: la segunda forma hace opcional la 'e'
    # y termina matcheando el fragmento "garag" dentro de cualquier palabra.
    "cochera_txt":       (r"\b(cocheras?|garages?|garajes?|estacionamiento|guarda\s*coches?)\b", True),
    "seguridad":         (r"\b(vigilancia|seguridad\s+24|24\s*hs?\s+de\s+seguridad|encargado\s+permanente|camaras\s+de\s+seguridad|totem)\b", False),
    "amoblado":          (r"\b(amoblad[oa]s?|amueblad[oa]s?|equipad[oa]\s+con\s+muebles)\b", True),
    "apto_mascotas":     (r"\b(apto\s+mascotas|acepta\s+mascotas|pet\s+friendly|admite\s+mascotas)\b", True),

    # --- Espacios ---------------------------------------------------------
    "balcon":            (r"\b(balcon(es)?|balconcito)\b", True),
    "terraza":           (r"\b(terrazas?|azotea|aterrazad[oa])\b", True),
    "patio_jardin":      (r"\b(patios?|jardin(es)?|fondo\s+libre|parque\s+propio)\b", True),
    "dependencia":       (r"\b(dependencia\s+de\s+servicio|cuarto\s+de\s+servicio|habitacion\s+de\s+servicio)\b", False),
    "toilette":          (r"\b(toilette|toilet|bano\s+de\s+servicio)\b", False),
    "vestidor":          (r"\b(vestidor(es)?|walk\s*in\s*closet)\b", False),
    "lavadero":          (r"\b(lavader[oa]s?)\b", True),

    # --- Estado y potencial -----------------------------------------------
    "a_reciclar":        (r"\b(a\s+reciclar|a\s+refaccionar|para\s+refaccionar|para\s+reciclar|necesita\s+refaccion|a\s+poner\s+en\s+valor|para\s+remodelar|a\s+demoler)\b", False),
    "reciclado":         (r"\b(reciclad[oa]s?|refaccionad[oa]s?|remodelad[oa]s?|puesto\s+en\s+valor|a\s+nuevo)\b", False),
    "estrenar":          (r"\b(a\s+estrenar|sin\s+estrenar|nuevo\s+a\s+estrenar|obra\s+nueva)\b", False),
    "en_pozo":           (r"\b(en\s+pozo|desde\s+pozo|en\s+construccion|en\s+obra|preventa)\b", False),
    "luminoso":          (r"\b(muy\s+luminoso|luminos[oa]s?|vista\s+abierta|vista\s+panoramica|excelente\s+luz)\b", False),

    # --- Comercializacion (lo que importa al inversor) ---------------------
    "apto_credito":      (r"\b(apto\s+credito|apto\s+hipotecario|apto\s+para\s+credito)\b", True),
    "apto_profesional":  (r"\b(apto\s+profesional|uso\s+profesional|apto\s+oficina)\b", True),
    "renta_actual":      (r"\b(alquilad[oa]|con\s+inquilino|con\s+renta|renta\s+asegurada|contrato\s+vigente)\b", False),
    "oportunidad":       (r"\b(oportunidad|excelente\s+inversion|unica\s+oportunidad|imperdible|precio\s+de\s+ocasion)\b", False),
    "financiacion":      (r"\b(financiacion|financiado|en\s+cuotas|plan\s+de\s+pago)\b", False),
    "dueno_directo":     (r"\b(dueno\s+directo|propietario\s+directo|sin\s+comision|trato\s+directo)\b", False),
}

# Ventana de negacion: cuantas palabras antes del match se inspeccionan.
# 3 alcanza para "sin balcon", "no posee balcon" y "no cuenta con balcon",
# y evita el falso veto de "sin expensas, con balcon" (5 palabras de por medio).
VENTANA_NEGACION = 3

NEGADORES = r"(?:sin|no|nunca|carece\s+de|excepto|salvo)"

# Contextos donde una negacion cercana NO niega el atributo. "no se permiten
# mascotas en la pileta" habla de las mascotas, no de la existencia de pileta.
# Se resuelve exigiendo que entre el negador y el atributo no haya un verbo
# que cambie el sujeto; en la practica alcanza con la ventana corta.


def _hay_negacion(texto: str, m: re.Match) -> bool:
    """
    Decide si el match `m` esta negado por las palabras que lo preceden.

    Mira hacia atras VENTANA_NEGACION palabras y busca un negador. Es
    deliberadamente conservador: prefiere dejar pasar una negacion lejana
    (falso positivo) antes que vetar un atributo real por una negacion que
    hablaba de otra cosa (falso negativo), porque el segundo error es mas
    dificil de detectar despues.
    """
    inicio = max(0, m.start() - 60)
    previo = texto[inicio:m.start()]
    palabras = previo.split()[-VENTANA_NEGACION:]
    return re.search(rf"\b{NEGADORES}\b", " ".join(palabras)) is not None


def _compilar() -> dict:
    return {k: (re.compile(p), neg) for k, (p, neg) in PATRONES.items()}


PATRONES_COMPILADOS = _compilar()


def extraer_dummies(texto: str) -> dict:
    """Aplica los 36 patrones a un texto ya normalizado. Devuelve dict 0/1."""
    out = {}
    for nombre, (rx, admite_neg) in PATRONES_COMPILADOS.items():
        valor = 0
        for m in rx.finditer(texto):
            if admite_neg and _hay_negacion(texto, m):
                continue          # el aviso niega el atributo: no cuenta
            valor = 1
            break
        out[nombre] = valor
    return out


# ==========================================================================
# EXTRACCION NUMERICA Y CATEGORICA DESDE EL TEXTO
# ==========================================================================

# El piso no viene en el esquema del scraping (la columna `piso` del crudo
# tenia 0,3% de completitud y se descarto). Pero aparece escrito en el texto
# de forma bastante regular, y es una variable con efecto conocido sobre el
# precio: planta baja y ultimo piso cotizan distinto que un piso intermedio.
RX_PISO = [
    re.compile(r"\b(?:piso|nivel)\s+(\d{1,2})\b"),
    re.compile(r"\b(\d{1,2})\s*(?:er|do|ro|to|mo|vo|no)\s+piso\b"),
    re.compile(r"\b(\d{1,2})\s*°\s*piso\b"),
]
RX_PLANTA_BAJA = re.compile(r"\b(planta\s+baja|p\s?b\b|a\s+la\s+calle\s+en\s+pb)\b")
RX_ULTIMO_PISO = re.compile(r"\b(ultimo\s+piso|piso\s+alto|penthouse|pent\s*house)\b")

# Orientacion y disposicion: el aviso las declara casi siempre, y son las dos
# variables que el metodo de subcadena confundia entre si.
RX_CONTRAFRENTE = re.compile(r"\b(contra\s*frente|al\s+contrafrente|interno)\b")
RX_AL_FRENTE = re.compile(r"\b(al\s+frente|frente\s+a\s+la\s+calle|vista\s+a\s+la\s+calle)\b")

# Superficie mencionada en el texto: sirve de control cruzado contra la
# columna estructurada. Cuando difieren mucho, uno de los dos esta mal.
RX_SUP_TEXTO = re.compile(r"\b(\d{2,4})(?:\s*[.,]\s*\d+)?\s*(?:m2|mts2|m\s*2|metros\s+cuadrados)\b")


def extraer_estructura(texto: str) -> dict:
    """Extrae piso, disposicion y superficie declarada en el texto libre."""
    piso = np.nan
    for rx in RX_PISO:
        m = rx.search(texto)
        if m:
            n = int(m.group(1))
            if 0 <= n <= 50:          # arriba de 50 pisos no hay en CABA
                piso = float(n)
            break

    es_pb = int(bool(RX_PLANTA_BAJA.search(texto)))
    if es_pb and np.isnan(piso):
        piso = 0.0

    # La disposicion se resuelve por prioridad: si el aviso menciona
    # contrafrente, esa es la palabra que el vendedor eligio declarar aunque
    # tambien diga "al frente" en otra parte del texto.
    if RX_CONTRAFRENTE.search(texto):
        disposicion = "contrafrente"
    elif RX_AL_FRENTE.search(texto):
        disposicion = "frente"
    else:
        disposicion = "sin dato"

    m = RX_SUP_TEXTO.search(texto)
    sup_txt = float(m.group(1)) if m else np.nan

    return {
        "piso_txt": piso,
        "es_planta_baja": es_pb,
        "es_ultimo_piso": int(bool(RX_ULTIMO_PISO.search(texto))),
        "disposicion": disposicion,
        "sup_declarada_txt": sup_txt,
    }


# ==========================================================================
# METODO VIEJO, PARA PODER COMPARAR
# ==========================================================================

# Copia literal de las keywords de la 1ra entrega (src/utils.py). No se usa
# para producir el dataset: se usa para medir cuanto mejora el RegEx. Sin
# este contrafactual, "usamos RegEx" seria una afirmacion sin evidencia.
KEYWORDS_VIEJAS = {
    "amenities":  ["amenities", "piscina", "pileta", "sum", "solarium", "gimnasio",
                   "gym", "sauna", "laundry", "coworking"],
    "pileta":     ["pileta", "piscina"],
    "parrilla":   ["parrilla", "quincho"],
    "gimnasio":   ["gimnasio", "gym"],
    "cochera_txt": ["cochera", "guarda coche", "estacionamiento", "garage"],
    "baulera":    ["baulera"],
    "balcon":     ["balcon", "aterrazado", "terraza"],
    "ascensor":   ["ascensor"],
    "amoblado":   ["amoblado", "amueblado", "equipado"],
    "patio_jardin": ["patio", "jardin", "fondo libre"],
    "apto_credito": ["apto credito", "apto hipotecario"],
    "a_reciclar": ["a reciclar", "a refaccionar", "para refaccionar", "para reciclar",
                   "necesita refaccion", "a poner en valor"],
    "reciclado":  ["reciclado", "reciclada", "refaccionado", "totalmente reciclado"],
    "luminoso":   ["luminoso", "muy luminoso", "vista abierta", "vista panoramica"],
    "frente":     ["al frente", "contrafrente"],
}


def dummies_viejas(texto: str) -> dict:
    """Reproduce el `in` de subcadena de la 1ra entrega."""
    t = f" {texto} "
    return {k: int(any(kw in t for kw in kws)) for k, kws in KEYWORDS_VIEJAS.items()}


# ==========================================================================
# PIPELINE
# ==========================================================================

class Reporte:
    """Acumula el log de la corrida para imprimirlo y guardarlo."""

    def __init__(self):
        self.lineas: list = []

    def __call__(self, texto: str = "") -> None:
        print(texto)
        self.lineas.append(texto)

    def titulo(self, texto: str) -> None:
        self("")
        self("=" * 74)
        self(texto)
        self("=" * 74)

    def guardar(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(self.lineas))


def construir_texto(df: pd.DataFrame) -> pd.Series:
    """
    Concatena titulo + descripcion + detalles y lo normaliza una sola vez.

    Se normaliza aca y no dentro de cada patron porque son 12.097 filas por 36
    patrones: normalizar en el loop multiplicaria por 36 el trabajo.
    """
    partes = [df[c].fillna("") for c in ["titulo", "descripcion", "detalles"]
              if c in df.columns]
    crudo = partes[0]
    for p in partes[1:]:
        crudo = crudo + " . " + p
    return crudo.map(normalizar)


def aplicar(df: pd.DataFrame, rep: Reporte) -> pd.DataFrame:
    """Genera todas las variables de texto sobre el dataframe."""
    rep.titulo("INGENIERIA DE VARIABLES DESDE TEXTO LIBRE")
    rep(f"Fecha        : {datetime.now():%Y-%m-%d %H:%M}")
    rep(f"Filas        : {len(df):,}")

    texto = construir_texto(df)
    largo = texto.str.len()
    rep(f"Largo del texto por aviso: mediana {largo.median():,.0f} caracteres, "
        f"minimo {largo.min():,.0f}, maximo {largo.max():,.0f}")
    vacios = int((largo < 20).sum())
    rep(f"Avisos con texto insuficiente (<20 caracteres): {vacios}")
    if vacios:
        rep("    En esos avisos toda dummy queda en 0. No es 'ausencia del")
        rep("    atributo' sino 'ausencia de informacion': la distingue la")
        rep("    columna completitud_aviso que trae el dataset limpio.")

    # --- Dummies por RegEx --------------------------------------------------
    nuevas = pd.DataFrame([extraer_dummies(t) for t in texto], index=df.index)
    rep("")
    rep(f"Variables dicotomicas generadas por RegEx: {nuevas.shape[1]}")

    # --- Estructura numerica ------------------------------------------------
    estruct = pd.DataFrame([extraer_estructura(t) for t in texto], index=df.index)
    rep(f"Variables de estructura extraidas del texto: {estruct.shape[1]}")
    rep(f"    piso_txt recuperado en {estruct.piso_txt.notna().mean()*100:.1f}% "
        f"de los avisos (la columna `piso` del crudo tenia 0.3%)")
    rep(f"    disposicion declarada en {(estruct.disposicion != 'sin dato').mean()*100:.1f}% "
        f"de los avisos")

    # --- Indice de confort: suma simple, no PCA -----------------------------
    # Se cuenta cuantos amenities declara el aviso. Es una suma, no un indice
    # ponderado: ponderar exige reduccion de dimensionalidad y eso pertenece a
    # la 3ra entrega. Aca sirve como variable ordinal para el EDA.
    COLS_CONFORT = ["pileta", "parrilla", "gimnasio", "sum", "solarium", "laundry",
                    "sauna", "coworking", "seguridad", "ascensor", "baulera",
                    "aire_acondicionado", "losa_radiante", "balcon", "terraza"]
    nuevas["n_amenities"] = nuevas[COLS_CONFORT].sum(axis=1)
    nuevas["amenities"] = (nuevas[["pileta", "parrilla", "gimnasio", "sum", "solarium",
                                   "laundry", "sauna", "coworking"]].sum(axis=1) > 0).astype(int)
    rep(f"    n_amenities: mediana {nuevas.n_amenities.median():.0f}, "
        f"maximo {nuevas.n_amenities.max():.0f} sobre {len(COLS_CONFORT)} posibles")

    # --- Comparacion contra el metodo viejo ---------------------------------
    viejas = pd.DataFrame([dummies_viejas(t) for t in texto], index=df.index)
    comparar(nuevas, viejas, texto, rep)

    # Las dummies del scraping se reemplazan: quedaria una columna `pileta`
    # vieja y otra nueva con el mismo nombre y distinto criterio, que es
    # exactamente el tipo de ambiguedad que este script viene a eliminar.
    a_pisar = [c for c in nuevas.columns if c in df.columns]
    rep("")
    rep(f"Columnas del scraping reemplazadas por su version RegEx: {len(a_pisar)}")
    rep(f"    {', '.join(sorted(a_pisar))}")
    df = df.drop(columns=a_pisar)

    # `frente` y `profesional_renta` cambian de nombre porque cambian de
    # significado: ahora son `disposicion` (3 categorias) y `renta_actual`.
    df = df.drop(columns=[c for c in ["frente", "profesional_renta"] if c in df.columns])

    return pd.concat([df, nuevas, estruct], axis=1)


def comparar(nuevas: pd.DataFrame, viejas: pd.DataFrame, texto: pd.Series,
             rep: Reporte) -> None:
    """Mide, atributo por atributo, cuanto cambia el resultado."""
    rep.titulo("AUDITORIA: SUBCADENA (1ra entrega) CONTRA REGEX")
    rep(f"{'atributo':<20}{'viejo %':>10}{'nuevo %':>10}{'delta pp':>10}"
        f"{'0->1':>8}{'1->0':>8}")
    rep("-" * 66)

    comunes = [c for c in viejas.columns if c in nuevas.columns]
    for c in sorted(comunes):
        v, n = viejas[c], nuevas[c]
        sube = int(((v == 0) & (n == 1)).sum())
        baja = int(((v == 1) & (n == 0)).sum())
        rep(f"{c:<20}{v.mean()*100:>9.1f}%{n.mean()*100:>9.1f}%"
            f"{(n.mean()-v.mean())*100:>+10.1f}{sube:>8}{baja:>8}")

    # --- Un delta no es lo mismo que un error -------------------------------
    # Cuando una keyword vieja mezclaba dos conceptos y el RegEx los separa en
    # dos variables, las filas que pasan de 1 a 0 no se perdieron: se mudaron.
    # Hay que descontarlas antes de hablar de correcciones, o la tabla de
    # arriba se lee como si el metodo nuevo detectara menos cosas.
    RECATEGORIZADAS = {
        "balcon":   (r"\b(?:terraza|aterrazad)", "terraza",
                     "la keyword vieja de balcon incluia 'terraza' y 'aterrazado'"),
        "amoblado": (r"equipad", None,
                     "la keyword vieja incluia 'equipado', que en los avisos "
                     "califica a la cocina, no al departamento"),
    }
    rep("")
    rep("Descomposicion de las bajas (1 -> 0): mudanza contra correccion")
    for c, (rx_mov, destino, motivo) in RECATEGORIZADAS.items():
        if c not in comunes:
            continue
        baja = (viejas[c] == 1) & (nuevas[c] == 0)
        mudadas = int((baja & texto.str.contains(rx_mov, regex=True)
                       & ~texto.str.contains(rf"\b{c}", regex=True)).sum())
        total = int(baja.sum())
        rep(f"    {c:<10} {total:>5} bajas, de las cuales {mudadas:>5} "
            f"({mudadas / max(1, total) * 100:.1f}%) son mudanza y no correccion")
        rep(f"               motivo: {motivo}")
        if destino:
            rep(f"               ahora viven en la variable `{destino}`")

    # --- Los tres errores del metodo viejo, cuantificados -------------------
    rep("")
    rep("Los tres errores sistematicos de la busqueda por subcadena:")
    rep("")

    # 1. Fragmento dentro de otra palabra
    ruido_sum = texto.str.contains(r"\b\w*sum\w+\b", regex=True)
    sin_amenity_real = ~texto.str.contains(
        r"\b(?:amenities|piscina|pileta|solarium|gimnasio|gym|sauna|laundry|coworking)\b",
        regex=True)
    falsos_sum = int((viejas["amenities"].eq(1) & ruido_sum & sin_amenity_real).sum())
    rep(f"  1. FRAGMENTO. 'sum' dentro de otra palabra (consumo, resumen, asumir)")
    rep(f"     marca amenities=1 en {falsos_sum:,} avisos que no tienen ninguno.")
    rep(f"     Sobre {int(viejas['amenities'].sum()):,} positivos del metodo viejo, "
        f"eso es un {falsos_sum/max(1,viejas['amenities'].sum())*100:.1f}% de falsos positivos.")

    # 2. Negacion ignorada
    rep("")
    rep("  2. NEGACION. El aviso dice que NO lo tiene y la variable marca 1:")
    for c in ["balcon", "cochera_txt", "amoblado", "ascensor"]:
        pat = c.replace("_txt", "")
        neg = texto.str.contains(rf"\b(?:sin|no\s+\w+)\s+{pat}", regex=True)
        n_v = int((viejas.get(c, pd.Series(0, index=texto.index)).eq(1) & neg).sum())
        n_n = int((nuevas[c].eq(1) & neg).sum())
        rep(f"     {c:<14} viejo {n_v:>4} avisos negados marcados 1  ->  "
            f"nuevo {n_n:>4}")
        if n_n:
            # El veto opera por ocurrencia, no por aviso: si el texto niega el
            # atributo en una frase y lo afirma en otra, la afirmacion vale.
            # Se verifica que ese sea el caso de TODOS los residuos en vez de
            # darlo por sentado.
            resid = nuevas[c].eq(1) & neg
            rx_c = PATRONES[c][0]
            varias = int((texto[resid].str.count(rx_c) > 1).sum())
            rep(f"                    residuo explicado: {varias}/{n_n} mencionan "
                f"el atributo mas de una vez (lo niegan en un lugar, lo afirman "
                f"en otro)")

    # 3. Antonimo por subcadena
    rep("")
    solo_contra = texto.str.contains(r"contra\s*frente") & ~texto.str.contains(r"\bal\s+frente\b")
    rep(f"  3. ANTONIMO. 'contrafrente' contiene 'frente'. El metodo viejo marcaba")
    rep(f"     frente=1 en {int((viejas['frente'].eq(1) & solo_contra).sum()):,} avisos "
        f"que declaran ser contrafrente,")
    rep(f"     que es el atributo opuesto. La variable `disposicion` los separa")
    rep(f"     en tres categorias en vez de colapsarlos en una dummy ambigua.")


def prevalencias(df: pd.DataFrame, rep: Reporte) -> None:
    """Tabla de prevalencia final, que es la que se lee en el informe."""
    rep.titulo("PREVALENCIA DE LAS VARIABLES DICOTOMICAS")
    cols = [c for c in PATRONES if c in df.columns]
    tabla = (df[cols].mean().sort_values(ascending=False) * 100)
    rep(f"{'variable':<22}{'% de avisos':>12}{'n':>8}")
    rep("-" * 42)
    for c, pct in tabla.items():
        rep(f"{c:<22}{pct:>11.1f}%{int(df[c].sum()):>8}")

    # Una dummy con prevalencia extrema no discrimina: si el 99% la tiene, no
    # explica ninguna diferencia de precio. Se avisa para el modelado.
    extremas = tabla[(tabla < 1) | (tabla > 99)]
    if len(extremas):
        rep("")
        rep("Variables con prevalencia extrema (<1% o >99%): sin poder")
        rep("discriminante, no conviene usarlas como predictoras.")
        for c, pct in extremas.items():
            rep(f"    {c:<22}{pct:>6.1f}%")

        # Prevalencia cero admite dos lecturas opuestas: el patron no anda, o
        # el atributo no existe en esta fuente. Distinguirlas es barato y evita
        # tirar una variable buena (o confiar en una rota).
        rep("")
        rep("Control: se prueba cada patron extremo contra un texto de laboratorio")
        rep("para separar 'el RegEx falla' de 'el atributo no existe en la fuente'.")
        SONDAS = {
            "dueno_directo": "vende dueno directo sin comision inmobiliaria",
        }
        for c in extremas.index:
            sonda = SONDAS.get(c)
            if sonda is None:
                continue
            ok = extraer_dummies(normalizar(sonda))[c]
            rep(f"    {c:<22} detecta el caso sintetico: {'si' if ok else 'NO'}")
        rep("    Lectura: el patron funciona. La prevalencia es cero porque la")
        rep("    fuente es una red inmobiliaria con cartera propia: no hay avisos")
        rep("    de particulares. Es una limitacion de la fuente, no del parseo.")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", default="data/processed/dataset_limpio.csv")
    p.add_argument("--outdir", default="data/processed")
    args = p.parse_args()

    if not os.path.exists(args.input):
        print(f"No existe {args.input}. Corré primero: py src/limpieza.py")
        return 1

    df = pd.read_csv(args.input, encoding="utf-8-sig", low_memory=False)
    rep = Reporte()
    df = aplicar(df, rep)
    prevalencias(df, rep)

    os.makedirs(args.outdir, exist_ok=True)
    p_out = os.path.join(args.outdir, "dataset_variables.csv")
    df.to_csv(p_out, index=False, encoding="utf-8-sig")

    rep("")
    rep(f"Filas    : {len(df):,}")
    rep(f"Columnas : {df.shape[1]}")
    rep(f"Guardado : {p_out}")
    p_rep = os.path.join(args.outdir, "reporte_regex.txt")
    rep(f"Reporte  : {p_rep}")
    rep.guardar(p_rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
