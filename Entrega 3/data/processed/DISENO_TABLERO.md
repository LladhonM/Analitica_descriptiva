# Diseño del tablero

Especificación del tablero en Streamlit: paleta, estructura, visualizaciones, filtros y
dinámica. Complementa a `GUIA_TABLERO.md`, que define **qué datos** usar y cómo leerlos;
este documento define **cómo se muestran**. Ante cualquier duda sobre columnas, cifras o
limitaciones, manda `GUIA_TABLERO.md`.

> Pregunta del tablero: **Tengo entre USD 80.000 y 200.000: ¿conviene comprar para
> alquilar, y si compro, qué?**

---

## 1. Paleta de colores

La paleta base del grupo (`#FFD275`, `#778472`, `#C5D5EA`, `#30343F`) se usa para la
**interfaz**. Para los **datos** se agregan tres tonos más profundos de los mismos matices,
porque el amarillo y el celeste originales tienen un contraste de ~1,4:1 sobre blanco (el
mínimo para marcas de un gráfico es 3:1) y el verde y el celeste se perciben casi grises.
Los tonos de datos se validaron en fondo claro y oscuro, incluida la separación para
daltonismo.

| Rol | Color | Uso |
|---|---|---|
| Texto y títulos | `#30343F` | Todo el texto; botones principales; franja del encabezado (con texto blanco) |
| Fondo | `#FFFFFF` | Página |
| Fondo secundario | `#E8EEF7` | Barra lateral, tarjetas de KPI y etiquetas de limitaciones (celeste base aclarado) |
| Acento | `#FFD275` | **Solo** la banda de retorno 7,10–7,60% (área sombreada). Nunca para texto |
| Contexto | `#778472` | Marcas del "resto de propiedades"; texto secundario grande |
| Dato principal | `#2F68B0` | Neta central, serie principal; borde izquierdo de las tarjetas de KPI |
| Dato de alerta | `#C08A1E` | Escenario pesimista, candidatas P1 "a verificar" |
| Dato secundario | `#4A7F3A` | Segunda serie (p. ej. gestión autogestionada en P3) |
| Selección | `#00A676` | Propiedad elegida en todas las vistas (P2, mapa, ficha). Solo para eso |

**Estilo de la interfaz**
- **Franja del encabezado**: fondo `#30343F`, texto blanco (`#FFFFFF`).
- **Tarjetas de KPI**: fondo `#E8EEF7` y borde izquierdo de 4 px en `#2F68B0`, sin borde
  en los otros lados.

**Escala divergente** (posición respecto de la banda, para el mapa y clasificaciones):

| Categoría | Color |
|---|---|
| Debajo del piso (< 7,10%) | `#2F68B0` |
| Dentro de la banda (7,10–7,60%) | `#B9BCC4` |
| Sobre el techo (> 7,60%) | `#C08A1E` |

**Reglas de color**
- Un color sigue a la entidad, no a su posición: si un filtro cambia las series, las que
  quedan no se repintan.
- La identidad nunca depende solo del color: con dos series o más hay leyenda o etiqueta
  directa.
- El texto va en `#30343F` (o `#778472` si es secundario y grande), nunca en el color de
  la serie.

**Tema de Streamlit** (`tablero/.streamlit/config.toml`):

```toml
[theme]
base = "light"
primaryColor = "#30343F"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#E8EEF7"
textColor = "#30343F"
```

Conviene definir los colores de datos una sola vez (por ejemplo, un diccionario `COLORES`
en `tablero/datos.py`) y no repetir los hex en cada gráfico.

---

## 2. Estructura

Una página con barra lateral de filtros, un encabezado fijo y **cinco pestañas**. Cada
pestaña responde una pregunta del inversor; el tablero no replica los notebooks.

### Encabezado (visible en todas las pestañas)

Compacto, en tres líneas:

- **Franja** de fondo `#30343F` con texto blanco: el título corto *"¿Conviene comprar
  para alquilar?"* y, en la misma franja y en tamaño chico, el contador de alcance:
  *"Mostrando N de 9.203 propiedades · cartera RE/MAX · relevada el 16 y 17-08-2026"*.
  N responde a los filtros.
- **Subtítulo** de una línea con la pregunta completa del tablero.
- **Fila de tres etiquetas** con las limitaciones obligatorias (`GUIA_TABLERO.md`),
  siempre visibles, cada una con su explicación completa en un tooltip:
  1. *"Precios de publicación"*: son precios de publicación, no de cierre.
  2. *"Una sola inmobiliaria, ~8% más barata"*: es la cartera de una sola inmobiliaria,
     que publica ~8% más barato que el mercado; las rentabilidades probablemente están
     del lado alto.
  3. *"Cada rentabilidad es una banda"*: cada rentabilidad es una banda, no un número.

### Pestañas

| # | Pestaña | Pregunta que responde |
|---|---|---|
| 1 | ¿Conviene comprar? | ¿La propiedad típica le gana a la renta fija en dólares? |
| 2 | ¿Dónde? | ¿Qué barrios rinden más y por qué? |
| 3 | ¿Qué comprar? | ¿Qué propiedades vale la pena verificar? |
| 4 | ¿Tradicional o temporal? | ¿Alquilar por noche cambia la respuesta? |
| 5 | Supuestos y alcance | ¿Cuánto depende todo de los supuestos? ¿Qué no se puede afirmar? |

---

## 3. Visualizaciones

**Reglas para todas las vistas**
- Ninguna neta sin su banda (`neta_min_pct` a `neta_max_pct`).
- Ningún gráfico de rentabilidad sin la franja 7,10–7,60% sombreada en `#FFD275`.
- Medidas de resumen: **medianas**, no promedios.
- La banda y el presupuesto salen de `supuestos.py` (`S.RETORNO_MINIMO_BANDA`,
  `S.PRESUPUESTO_USD`); los nombres de barrio, de `eda.nombre_barrio()`. Ningún número
  escrito a mano en la app.
- Gráficos con Plotly, con tooltip al pasar el mouse. Grilla y ejes discretos.

### Pestaña 1 · ¿Conviene comprar?

- **Cuatro tarjetas de KPI** (responden a los filtros):
  - Neta mediana, con el rango mediano `neta_min_pct`–`neta_max_pct` dentro de la
    tarjeta, debajo del valor, en gris y sin flecha (nunca la neta sola).
  - TIR a 5 años mediana (con costos de entrada).
  - % de propiedades con neta sobre el piso de la banda.
  - Distancia en pp de la neta mediana al piso.
- **Histograma de la neta** (o de la TIR, según la métrica elegida) con la banda
  sombreada. Es el gráfico central del tablero.
- **Etapas del universo de decisión** (*"¿Cuántas pasan cada vara?"*): universo → neta
  central sobre el techo → P1 (neta pesimista sobre el techo) → TIR pesimista sobre el
  techo. Sin filtros: 4.484 → 227 → 18 → 4. **Barras horizontales** en escala lineal (no
  embudo, no logarítmica), con etiquetas cortas de etapa y el valor **afuera** de la barra
  en formato *"cantidad · % del universo"* (p. ej. *"18 · 0,4%"*), para que los valores
  chicos se lean. Debajo, una sola línea: *"Las que pasan P1 no son una recomendación:
  hay que verificar por qué son baratas."*
- El histograma y las etapas van lado a lado (columnas 3:2).

### Pestaña 2 · ¿Dónde?

Disposición: el **mapa primero, a todo el ancho**; debajo, los **puntos por barrio** y la
**dispersión H1** lado a lado. Es la única pestaña con scroll (sección 6).

- **Puntos por barrio** desde `ranking_barrios.csv` (solo barrios con 30 ventas o más):
  neta y TIR medianas, ordenadas, con la banda sombreada. Los barrios elegidos en el
  filtro se resaltan y el resto queda atenuado; la tabla en sí no se filtra.
- **Mapa** de propiedades (`latitud`, `longitud`) coloreado con la escala divergente.
  Los 7 avisos sin coordenadas se informan en una nota.
- **Dispersión H1**: m² del barrio contra rentabilidad bruta. Muestra la palanca más
  fuerte del análisis (-0,98 pp por cada USD 500/m²).

### Pestaña 3 · ¿Qué comprar?

Solo con `universo_decision = True`.

- **Tabla P1 "a verificar"** (`p1_comprar`): barrio, precio, superficie, neta pesimista,
  `m2_relativo_celda` y link al aviso (`url`). Encabezado obligatorio: *"Cuestan ~30%
  menos por m² que su celda: verificar por qué antes de decidir."* Nunca rotularla como
  "comprar".
- **Gráfico de rangos de la frontera P2** (`p2_no_dominada`): una barra horizontal de
  `neta_min_pct` a `neta_max_pct` por propiedad, con la banda de referencia,
  **ordenada por ancho de banda (más angosta primero), nunca por rentabilidad**. Nota:
  *"Entre estas propiedades ninguna le gana con claridad a otra."*
- **Ficha de la propiedad seleccionada** (el link lleva al aviso relevado; si ya no está
  publicado, RE/MAX abre su portada, y el tooltip lo avisa): título, barrio, precio, superficie, alquiler
  estimado con su rango p10–p90, costos de entrada, neta como banda, TIR 5 años,
  distancia y modo de transporte, días de publicación típicos y link al aviso.

### Pestaña 4 · ¿Tradicional o temporal?

- **Líneas** desde `decision_p3.csv`: cantidad de celdas (de 47) donde gana el temporal
  según la ocupación sostenible, una línea por tipo de gestión (tercerizada en
  `#2F68B0`, autogestionada en `#4A7F3A`). Líneas verticales de referencia en 18,6%
  (Inside Airbnb) y 53% (prensa), rotuladas.
- **Selector de vacancia** del alquiler tradicional (valores de la tabla).
- Conclusión en texto: tradicional, salvo autogestión con evidencia de más de la mitad
  del año ocupado.

### Pestaña 5 · Supuestos y alcance

- **Barras de sensibilidad** desde `decision_sensibilidad.csv`: cuántas propiedades pasan
  P1 (y P1 con entrada) en cada uno de los 22 escenarios, con la base marcada.
- **Limitaciones completas**: las tres del encabezado, más casas y PH fuera de las
  recomendaciones, sin apreciación, sin costos de salida, sin riesgo legal, liquidez de
  toda la Ciudad y no causalidad.
- **Fuentes y fecha de los datos**, con remisión a `informe/FUENTES_EXTERNAS.md`.

---

## 4. Filtros

En la barra lateral, todos juntos, con un botón para restablecerlos.

| Filtro | Columna | Control | Default |
|---|---|---|---|
| Presupuesto | `venta_usd` | Slider de rango | 80.000–200.000 (`S.PRESUPUESTO_USD`) |
| Tipo | `tipo_familia` | Selector | Departamento |
| Comuna | `comuna` | Multiselect | Todas |
| Barrio | `barrio` | Multiselect (acotado por la comuna elegida) | Todos |
| Ambientes | `ambientes` | Multiselect | Todos |
| Superficie | `superficie_rango` | Multiselect | Todos |
| Antigüedad | `antiguedad_rango` | Multiselect | Todos |
| Métrica | — | Radio: Neta / TIR 5 años | Neta |
| Restablecer | — | Botón | — |

**Fuera de los filtros, a propósito**
- La banda de retorno: es una línea de referencia fija, no un filtro.
- Amenities, cochera y demás atributos: no cambian la decisión (`GUIA_TABLERO.md`).

---

## 5. Dinámica

- **Qué responde a los filtros.** Las vistas que leen `dataset_analitico.csv` (pestaña 1,
  mapa y dispersión de la 2, toda la 3) se filtran. Las que leen tablas precalculadas
  (ranking de barrios, P3, sensibilidad) no, y cada una lo indica con la nota *"Esta
  vista no responde a los filtros."*
- **Estados vacíos.** Si los filtros dejan 0 propiedades: un mensaje (`st.info`) en lugar
  de los gráficos. Si quedan menos de 30: advertencia de que la mediana es poco
  confiable.
- **Casas y PH.** Si se eligen: advertencia de que el modelo casi no tiene alquileres
  observados de ellos, y las secciones P1 y P2 se ocultan.
- **Selección.** Clic en una fila de las tablas P1 o P2 abre su ficha y resalta la
  propiedad en `#00A676` en el mapa (selección de filas de `st.dataframe`): la propiedad
  elegida va encima, más gruesa y sin borde; el resto se atenúa. Destildar la fila, hacer
  clic de nuevo sobre la elegida o afuera de las barras la deselecciona: P2, el mapa y la
  ficha vuelven a su estado sin selección. Elegir en P1 o en P2 vacía la selección del otro.
- **Rendimiento.** El CSV se lee una sola vez con `st.cache_data`, solo con las columnas
  de `GUIA_TABLERO.md`, aplicando el filtro `operacion = "venta"` y
  `estimacion_confiable = 1`.
- **Organización del código.** Todo el tablero vive en `tablero/`. `app.py` solo arma la
  interfaz. La carga, el filtrado y las medianas van en `tablero/datos.py`, con su test
  (`tablero/test_tablero.py`); `datos.py` importa `supuestos` y `eda` de `src/`. Los KPIs
  no se recalculan: se usan las columnas ya materializadas.
- **Ejecución.** Desde `Entrega 3/tablero/`: `streamlit run app.py`. Streamlit lee el tema
  de `.streamlit/config.toml` en la carpeta desde donde se ejecuta, por eso se corre desde
  `tablero/`. `streamlit` y `plotly` están en `requirements.txt` y las instrucciones en el
  README.

---

## 6. Reglas de diseño de pantalla

Valen para todas las pestañas.

- **Layout ancho** (`st.set_page_config(layout="wide")`), con el padding superior del
  contenido reducido a ~1rem.
- **Cada pestaña entra sin scroll en 1440×900**: lo principal arriba, el detalle debajo.
  Excepción: la pestaña 2 (*¿Dónde?*), que con tres gráficos muestra primero el mapa a todo
  el ancho y deja los otros dos debajo, con scroll.
- **Gráficos lado a lado** en columnas (`st.columns`) y dentro de recuadros con borde
  (`st.container(border=True)`), con márgenes de Plotly chicos.
- **Explicaciones en tooltips** (`help=` o ⓘ junto al título), no en párrafos.
- **No repetir en texto** lo que ya dice una tarjeta o un gráfico.
- **Los valores chicos siempre con etiqueta legible** fuera de la barra.
- **Solo quedan como texto visible las advertencias que exige `GUIA_TABLERO.md`**: las
  limitaciones del encabezado, el "verificar, no comprar" de P1 y el no ordenar P2 por
  rentabilidad, en una sola línea cada una. Los estados de la sección 5 (sin
  propiedades, pocas observaciones, casas y PH) también se muestran.

---

## Verificación antes de entregar

- Sin filtros, los números coinciden con `informe/INFORME_HALLAZGOS.md` (neta mediana
  5,65%, 19,4% sobre el piso, embudo 4.484 → 227 → 18 → 4, TIR mediana 4,27%).
- Cada filtro cambia el contador N y las vistas que deben cambiar, y no cambia las que no.
- Los estados vacíos y de pocas observaciones muestran su mensaje.
- Ninguna neta aparece sin su banda ni ningún gráfico de rentabilidad sin la franja.
- Cada pestaña entra sin scroll en 1440×900, salvo la 2 (mapa a todo el ancho arriba, scroll
  para el resto).
- Capturas de las vistas principales para la entrega final.
