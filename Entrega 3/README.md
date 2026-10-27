# Validación, análisis avanzado y decisión — mercado inmobiliario de CABA

**TP Integrador · 82.04 Analítica Descriptiva (ITBA) · Grupo 2 · 3ra pre-entrega**

Tercera etapa del análisis de rentabilidad inmobiliaria para un pequeño inversor
particular que, con USD 80.000 a 200.000, evalúa comprar **una** unidad en CABA para
alquilarla. Esta entrega valida formalmente las hipótesis, completa la fusión espacial,
y resuelve y evalúa la decisión del inversor, con un tablero orientado a él.

La 1ra y la 2da entrega están en sus propias carpetas y no se modifican. Esta carpeta es
autónoma: tiene su propio pipeline, sus datos y sus tests, y no lee nada fuera de ella.

---

## Estado

Hoy la carpeta contiene la **base heredada de la 2da entrega, depurada y verificada**:
el pipeline corre en esta carpeta y reproduce las cifras de referencia (ver
[Reproducir](#reproducir)). Lo nuevo de esta entrega se construye sobre esa base y se
registra en la tabla [Qué se construye en esta entrega](#qué-se-construye-en-esta-entrega).

---

## Procedencia de cada archivo

### Traído de la 2da entrega

Todo lo que sigue se copió en una sola operación desde la carpeta `Entrega 2/` del
commit `24e09b6`, que es la versión corregida de la 2da pre-entrega. Se copiaron solo
archivos versionados. La columna "Estado" indica qué cambió al traerlo.

**Código (`src/`)**

| Archivo | Estado |
|---|---|
| `src/limpieza.py` | Sin cambios |
| `src/variables.py` | Sin cambios |
| `src/kpis.py` | Sin cambios de lógica. En el docstring, el apartado sobre las dummies de RegEx se atribuye a la 2da entrega, que es la que lo hizo |
| `src/modelo_alquiler.py` | Se quitó el `main()`, un punto de entrada heredado de la 1ra entrega que no usaba nadie: aplicaba vacancia 8% y gastos 12% (no los de `supuestos.py`), escribía archivos que el pipeline no usa y pisaba `ranking_barrios.csv`. Ahora es un módulo que solo invoca `kpis.py`. El docstring deja de citar un error de ~11,5%, que no es el vigente (11,2%) |
| `src/supuestos.py` | Se quitaron constantes que ningún script ni notebook leía (`TOP_BARRIOS_HEATMAP` y tres `SCATTER_*`). La fecha de consulta y el umbral de completitud de las predictoras pasan a comentario: estaban declarados como constantes, pero nada los leía |
| `src/eda.py` | Se quitaron un import sin uso (`matplotlib.pyplot`) y un color que no se usaba (`BUENO`) |
| `src/temporal.py` | Se quitó un import sin uso (`numpy`). `lado_remax()` acepta la ruta del dataset como parámetro, con el mismo valor por defecto |
| `src/reporte.py` | Se quitó un import sin uso. **Su texto es el informe de la 2da entrega**: se reescribe con los hallazgos de esta, y hasta entonces no forma parte del pipeline |
| `src/sesgo.py` | Sin cambios |
| `src/fuentes_externas.py` | Sin cambios |
| `src/test_fuentes.py` | Resuelve las rutas desde la ubicación del archivo: antes solo corría desde la raíz de la entrega |
| `src/test_supuestos.py` | Sin cambios |
| `src/test_variables.py` | Sin cambios |
| `src/test_eda.py` | Sin cambios |

**Datos (`data/`)**

| Archivo | Estado |
|---|---|
| `data/raw/dataset_maestro.csv` | Sin cambios. Es el crudo del scraping de la 1ra entrega (14.867 avisos, 16-08-2026) |
| `data/external/` (7 tablas y `reporte_fuentes.txt`) | Sin cambios. Tablas agregadas y fechadas de IDECBA, Colegio de Escribanos, Inside Airbnb y Censo 2022 |
| `data/reference/` (`ranking_barrios_entrega1.csv`, `LEEME.md`) | Sin cambios |
| `data/processed/` — `dataset_analitico.csv`, `ranking_barrios.csv`, `modelo_alquiler.joblib`, `auditoria_calidad.csv`, `sensibilidad_supuestos.csv`, `reporte_limpieza.txt`, `reporte_regex.txt`, `reporte_kpis.txt` | **Regenerados en esta carpeta** por `limpieza.py`, `variables.py` y `kpis.py`. El contenido es idéntico al de la 2da entrega. Solo cambian la fecha de corrida en los reportes y el orden de Almagro y Villa Devoto en el ranking, que empatan en 7,31% de rentabilidad bruta |
| `data/processed/` — `sesgo_precio_barrio.csv`, `sesgo_representacion_comuna.csv`, `reporte_sesgo.txt`, `temporal_vs_tradicional.csv`, `reporte_temporal.txt` | Sin cambios: copiados, no regenerados |
| `data/processed/DICCIONARIO_DATOS.md` | El encabezado deja de presentar la matriz como "de la 2da pre-entrega": es la misma matriz, y las columnas nuevas se documentan ahí cuando entren al pipeline |

**Configuración**

| Archivo | Estado |
|---|---|
| `requirements.txt` | Versiones exactas en lugar de mínimas. Se agregó `openpyxl`: `fuentes_externas.py` lo importa para leer los cuadros de IDECBA y del Colegio, y no estaba declarado |
| `.gitignore` | Sin cambios |

### No traído

Los notebooks, los gráficos y el informe de la 2da entrega **no se copiaron**. Esta
entrega tiene los suyos, y conserva solo los gráficos y hallazgos que cambian la
decisión del inversor.

### Construido en esta entrega

Todo archivo que no figura en las tablas de arriba es nuevo de la 3ra entrega. Hoy es
solo este `README.md`; lo que se construye se lista en la tabla siguiente.

## Qué se construye en esta entrega

| # | Qué se entrega | Origen del pedido | Estado |
|---|---|---|---|
| 1 | Fusión espacial: distancia de cada aviso a subte, tren y Metrobus, y una medida de accesibilidad que combine los tres modos. Con eso, H2 deja de ser "no evaluable" | Devolución de la 2da entrega, prioridad 1 | Pendiente |
| 2 | Tests formales de H1 a H4, con p-valor, tamaño del efecto, intervalo y lectura de si cambian la decisión | Devolución, prioridad 2 | Pendiente |
| 3 | Función de decisión prescriptiva para P1 (comprar o no), P2 (qué propiedad) y P3 (tradicional o temporal), **implementada y evaluada** | Devolución, prioridad 3; consigna de la 3ra entrega | Pendiente |
| 4 | ABL segmentado por barrio, superficie y tipo de propiedad, y su efecto sobre la rentabilidad neta | Devolución, prioridad 4 | Pendiente |
| 5 | Costos de entrada, refacción, liquidez y riesgo legal, con fuente y fecha en `supuestos.py` | Devolución, prioridad 5 | Pendiente |
| 6 | Síntesis de atributos (PCA/MCA) y micro-mercados | Plan de la 2da entrega | Pendiente |
| 7 | Revisión del modelo de alquiler con las variables espaciales y contra una referencia simple | Plan de la 2da entrega | Pendiente |
| 8 | Tablero para el inversor (Power BI) | Consigna de la 3ra entrega | Pendiente |
| 9 | Depuración del repositorio: código sin uso, referencias a versiones anteriores, versiones fijas, tests independientes del directorio | Devolución, prioridad 6 | Hecho (ver [Procedencia](#procedencia-de-cada-archivo)) |

### Alcance corregido respecto del plan de la 2da entrega

El README de la 2da entrega cierra con un "Plan para lo pendiente" que ubica la
**función de decisión prescriptiva** y el **tablero para el inversor** en la entrega
final. La consigna vigente los pide en esta, la 3ra pre-entrega, y esta entrega los
incluye (filas 3 y 8). Esa tabla no se modifica porque la 2da entrega ya está
corregida; el alcance que vale es el de esta sección.

---

## Reproducir

Python 3.13. Desde esta carpeta:

```bash
py -m pip install -r requirements.txt

py src/limpieza.py --tc 1500             # crudo -> dataset limpio + auditoría
py src/variables.py                      # RegEx sobre el texto -> dummies
py src/kpis.py                           # modelo de alquiler -> los 4 KPIs
py src/test_variables.py                 # motor RegEx, sin red
py src/test_supuestos.py                 # supuestos.py contra el pipeline
py src/test_fuentes.py                   # joins con fuentes externas, sin red
py src/test_eda.py                       # estadística de eda.py, sin datos
```

`limpieza.py`, `variables.py` y `kpis.py` reconstruyen `data/processed/` a partir de
`data/raw/dataset_maestro.csv`. Los intermedios (`dataset_limpio.csv`,
`dataset_excluidos.csv`, `dataset_variables.csv`) no se versionan.

**Cifras de referencia.** Una corrida correcta da exactamente estas cifras, las mismas de
la 2da entrega. Si alguna cambia, cambió el pipeline o una dependencia:

| Cifra | Valor |
|---|---|
| Dataset limpio | 12.097 filas |
| Ventas con estimación confiable | 9.203 |
| Rentabilidad bruta mediana | 7,01% |
| Rentabilidad neta mediana | 5,67% |
| Repago mediano | 171 meses |
| R² del modelo de alquiler (log, fuera de muestra) | 0,848 |
| Error relativo mediano | 11,2% |

---

## Estructura

```
Entrega 3/
├── data/
│   ├── raw/            dataset_maestro.csv, crudo sin modificar
│   ├── processed/      dataset_analitico.csv, reportes, DICCIONARIO_DATOS.md
│   ├── external/       tablas agregadas y fechadas de las fuentes externas
│   └── reference/      ranking de barrios de la 1ra entrega, para comparar
├── src/                pipeline, supuestos y tests
├── requirements.txt
└── README.md
```

Las carpetas de notebooks, gráficos, informe y tablero se agregan cuando se crean.
