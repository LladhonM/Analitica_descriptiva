# Guía de datos para el tablero

Para quien arma el tablero en Streamlit, que vive en `tablero/`. El archivo es `dataset_analitico.csv`, de 128
columnas, y casi todo lo que el tablero necesita ya viene calculado: **conviene que la
app solo filtre y muestre, sin recalcular KPIs**. Si un número del tablero no coincide
con el informe, el error está en el tablero. El significado completo de cada columna está
en `DICCIONARIO_DATOS.md`.

## El propósito, en una frase

> Tengo entre USD 80.000 y 200.000: ¿conviene comprar para alquilar, y si compro, qué?

Todo filtro o gráfico que no sirva a esa pregunta sobra.

## Cómo leer el archivo

El archivo pesa 30 MB y pandas lo lee en menos de un segundo. La carga está en
`tablero/datos.py`, y `tablero/app.py` la envuelve con `st.cache_data` para leerla una sola
vez. Las rutas salen de la ubicación de `datos.py`, así que no dependen de la carpeta desde
donde se corre la app:

```python
# tablero/datos.py (resumen)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # Entrega 3/
sys.path.insert(0, os.path.join(RAIZ, "src"))
import eda
import supuestos as S

DATASET = os.path.join(RAIZ, "data", "processed", "dataset_analitico.csv")

def cargar(ruta=DATASET):
    df = pd.read_csv(ruta, encoding="utf-8-sig", usecols=COLUMNAS, low_memory=False)
    df = df[(df["operacion"] == "venta") & (df["estimacion_confiable"] == 1)].copy()
    for c in BOOLEANAS:
        df[c] = df[c].fillna(False).astype(bool)
    df["barrio_nombre"] = df["barrio"].map(eda.nombre_barrio)
    return df.reset_index(drop=True)

# tablero/app.py
@st.cache_data
def cargar():
    return T.cargar()
```

- **`encoding="utf-8-sig"`**: el CSV tiene BOM. Sin eso, la primera columna se llama
  `﻿id_aviso`.
- **`usecols`** con las columnas de la tabla de abajo, más `operacion` y
  `estimacion_confiable`, que usa el filtro: deja afuera los textos largos, que son la
  mayor parte del peso.
- **Las booleanas tienen nulos** en las filas donde no aplican (alquileres, ventas sin
  estimación confiable), así que pandas las lee como texto. El `fillna(False)` las
  vuelve booleanas.
- **No copiar números a mano en la app.** La banda de retorno sale de
  `S.RETORNO_MINIMO_BANDA` (7,10% a 7,60%) y el presupuesto de `S.PRESUPUESTO_USD`. El
  nombre de cada barrio para mostrar, con tildes, sale de `eda.nombre_barrio(barrio)`:
  en el dataset están en minúscula y sin tildes, porque así se unen con las otras fuentes.
- Una fila por aviso. Para todo lo de rentabilidad: **`operacion = "venta"` y
  `estimacion_confiable = 1`**, que son 9.203 filas.
- Para las recomendaciones: **`universo_decision = True`**, que son 4.484 propiedades
  dentro del presupuesto y del soporte del modelo.
- Las medidas de resumen son **medianas**, no promedios: los precios y las
  rentabilidades tienen cola larga y el promedio queda por encima de casi todos.

## Columnas para el tablero

| Para qué | Columnas |
|---|---|
| Identificar y enlazar | `id_aviso`, `url`, `titulo` |
| Filtros | `barrio`, `comuna`, `tipo_familia`, `superficie_rango`, `ambientes`, `dormitorios`, `antiguedad_rango`, `venta_usd`, `en_presupuesto` |
| Mapa | `latitud`, `longitud` (7 avisos sin coordenadas) |
| Precio | `venta_usd`, `venta_m2_usd`, `sup_total_m2`, `expensas_usd` |
| Alquiler estimado | `alquiler_est_usd_mes`, `alquiler_p10_usd_mes`, `alquiler_p90_usd_mes` |
| KPIs | `rent_bruta_pct`, `rent_neta_pct`, `meses_repago`, `rent_bruta_min`, `rent_bruta_max`, `tir_5a_pct` |
| Costos | `costos_entrada_pct`, `abl_pct`, `a_reciclar`, `refaccion_usd` |
| Decisión | `universo_decision`, `en_soporte_modelo`, `neta_min_pct`, `neta_max_pct`, `tir_5a_min_pct`, `p1_comprar`, `p1_comprar_con_entrada`, `p2_no_dominada`, `m2_relativo_celda` |
| Temporal (P3) | `p3_ocupacion_equilibrio_pct`, `p3_ocupacion_airbnb_pct` |
| Contexto | `dist_transporte_m`, `modo_cercano`, `amenities`, `cochera_txt`, `dias_publicacion_ambientes` |

La vara de comparación es la **banda de retorno mínimo: 7,10% a 7,60%** anual en
dólares (ON de YPF 2031 y Pampa 2037). Conviene fijarla como línea de referencia en todos
los gráficos de rentabilidad, no como un filtro.

Tablas chicas que sirven tal cual (se leen igual, con `utf-8-sig`):

| Archivo | Para qué |
|---|---|
| `ranking_barrios.csv` | Neta, bruta y TIR medianas por barrio (barrios con 30 o más ventas) |
| `temporal_vs_tradicional.csv` | P3 por barrio × dormitorios |
| `decision_p3.csv` | Celdas donde gana el temporal, según la ocupación y la gestión |
| `decision_sensibilidad.csv` | Cuánto cambian P1 y P2 con cada supuesto |

## Columnas internas: no usar

- **`precio_m2`**: mezcla USD por m² en ventas con pesos por m² en alquileres. Usar
  `venta_m2_usd`.
- **`precio_valor`, `precio_moneda`, `expensas_valor`, `expensas_moneda`, `precio_usd`**:
  son los precios crudos antes de convertir.
- **Las `*_imputada`, `completitud_aviso` y `tiene_detalles`**: son trazabilidad de la
  limpieza.
- **`descripcion`, `detalles`, `barrio_raw`, `direccion`, `calle`, `piso_txt`,
  `sup_declarada_txt`**: son texto crudo.
- **`log_sup`, `n_alq_barrio`, `n_alq_celda_tipo`, `alquiler_est_m2`, `gastos_pct`,
  `abl_ars_mes`, `alquiler_post_refaccion_usd_mes`**: son insumos de cálculos que ya
  están hechos.
- **Las 35 dummies sueltas del texto** (`pileta`, `sum`, `luminoso`, etc.): para el
  tablero alcanza con `amenities` y `cochera_txt`. Las demás no cambian la decisión.
- **`dueno_directo`**: vale 0 en todas las filas.

## Lo que el tablero tiene que mostrar en pantalla

Estas tres limitaciones van **visibles en la página principal**, no en una nota al pie.
La consigna evalúa que el tablero "comunique el alcance y las limitaciones de los datos".

1. **Son precios de publicación, no de cierre.** Tanto la venta como el alquiler son
   precios pedidos. El precio de cierre suele ser menor.
2. **Es la cartera de una sola inmobiliaria, que publica más barato que el mercado.**
   Contra IDECBA, RE/MAX publica alrededor de 8% más barato en promedio, y 9% en los
   usados (`informe/INFORME_HALLAZGOS.md`, hallazgo 6). Las rentabilidades
   probablemente están del lado alto.
3. **Cada rentabilidad es una banda, no un número.** El alquiler es una estimación. Su
   banda del percentil 10 al 90 contiene al 82% de los alquileres reales: mostrar
   siempre `neta_min_pct` a `neta_max_pct` junto a la neta, nunca la neta sola.

Y dos que conviene tener a un clic:

- **Las casas y los PH no se recomiendan.** El modelo casi no tiene alquileres
  observados de ellos (`en_soporte_modelo = False`).
- **No incluye apreciación, costos de salida ni riesgo legal.**

## Para no inducir interpretaciones erróneas

- **No ordenar `p2_no_dominada` por rentabilidad.** Esas propiedades no se distinguen
  entre sí. Si hace falta un orden, usar el ancho de la banda, de más angosta a más
  ancha.
- **`p1_comprar` significa "verificar", no "comprar".** Las que pasan cuestan alrededor
  de 30% menos por m² que su celda (`m2_relativo_celda`), y hay que ver por qué antes
  de cualquier decisión.
- **Una barra de neta sin la línea de 7,10% a 7,60% no dice nada.** El hallazgo central es
  que la propiedad típica queda debajo de esa línea.
- **Los barrios con pocas ventas engañan.** Para comparar barrios, usar
  `ranking_barrios.csv`, que solo incluye barrios con 30 ventas o más.
