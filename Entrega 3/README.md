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

La carpeta contiene la **base heredada de la 2da entrega, depurada y verificada**: el
pipeline corre acá y reproduce las cifras de referencia (ver [Reproducir](#reproducir)).
Sobre esa base ya está hecha la **fusión espacial**: distancia de cada aviso a subte,
tren y Metrobús, y una medida de accesibilidad que combina las tres redes (ver
[Accesibilidad al transporte](#accesibilidad-al-transporte)). El resto se registra en
la tabla [Qué se construye en esta entrega](#qué-se-construye-en-esta-entrega).

---

## Procedencia de cada archivo

### Traído de la 2da entrega

Todo sale de la carpeta `Entrega 2/` del commit `24e09b6`, que es la versión corregida
de la 2da pre-entrega, y son solo archivos versionados. El código, los datos y la
configuración se copiaron en una sola operación, al crear esta carpeta. El catálogo de
fuentes se trajo después, cuando la fusión espacial lo hizo necesario (ver
**Documentación**, abajo). La columna "Estado" indica qué cambió desde que se trajo.

**Código (`src/`)**

| Archivo | Estado |
|---|---|
| `src/limpieza.py` | Sin cambios |
| `src/variables.py` | Sin cambios |
| `src/kpis.py` | Lee `dataset_espacial.csv` (salida de `espacial.py`) en lugar de `dataset_variables.csv`, para que la matriz final lleve las columnas de accesibilidad. Sin cambios en el cálculo. En el docstring, el apartado sobre las dummies de RegEx se atribuye a la 2da entrega, que es la que lo hizo |
| `src/modelo_alquiler.py` | Se quitó el `main()`, un punto de entrada heredado de la 1ra entrega que no usaba nadie: aplicaba vacancia 8% y gastos 12% (no los de `supuestos.py`), escribía archivos que el pipeline no usa y pisaba `ranking_barrios.csv`. Ahora es un módulo que solo invoca `kpis.py`. El docstring deja de citar un error de ~11,5%, que no es el vigente (11,2%) |
| `src/supuestos.py` | Se quitaron constantes que ningún script ni notebook leía (`TOP_BARRIOS_HEATMAP` y tres `SCATTER_*`). La fecha de consulta y el umbral de completitud de las predictoras pasan a comentario: estaban declarados como constantes, pero nada los leía. Se agregó el radio de caminata de 800 m (sección 4b2), que usa `espacial.py` |
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
| `data/processed/` — `dataset_analitico.csv`, `ranking_barrios.csv`, `modelo_alquiler.joblib`, `auditoria_calidad.csv`, `sensibilidad_supuestos.csv`, `reporte_limpieza.txt`, `reporte_regex.txt`, `reporte_kpis.txt` | **Regenerados en esta carpeta** por `limpieza.py`, `variables.py`, `espacial.py` y `kpis.py`. El contenido es idéntico al de la 2da entrega, salvo tres diferencias: `dataset_analitico.csv` suma las 8 columnas de accesibilidad (las 98 heredadas coinciden columna por columna); los reportes cambian la fecha de corrida; y en el ranking puede cambiar el orden de Almagro y Villa Devoto, que empatan en 7,31% de rentabilidad bruta |
| `data/processed/` — `sesgo_precio_barrio.csv`, `sesgo_representacion_comuna.csv`, `reporte_sesgo.txt`, `temporal_vs_tradicional.csv`, `reporte_temporal.txt` | Sin cambios: copiados, no regenerados |
| `data/processed/DICCIONARIO_DATOS.md` | El encabezado deja de presentar la matriz como "de la 2da pre-entrega". Se agregaron la sección 9 (las 8 columnas de accesibilidad), el paso de `espacial.py` en el linaje y una advertencia de uso sobre qué no mide una distancia |

**Configuración**

| Archivo | Estado |
|---|---|
| `requirements.txt` | Versiones exactas en lugar de mínimas. Se agregó `openpyxl`: `fuentes_externas.py` lo importa para leer los cuadros de IDECBA y del Colegio, y no estaba declarado |
| `.gitignore` | Se agregó `dataset_espacial.csv`, el intermedio nuevo del pipeline |

**Documentación**

| Archivo | Estado |
|---|---|
| `informe/FUENTES_EXTERNAS.md` | Traído **en un segundo paso**, al incorporar las capas espaciales: no estaba en la copia inicial. Sale del mismo commit `24e09b6` y era idéntico al de la 2da entrega al traerlo. Se trajo en lugar de escribir un catálogo nuevo para que las fuentes 1 a 5, cuyas tablas sí están en `data/external/`, sigan documentadas en esta carpeta. Cambios: las fichas 6 a 9 (subte, tren, Metrobús, espacios verdes) reemplazan a la ficha "planificada" de transporte; se suma la sección sobre qué mide la distancia y qué no; el IPC pasa a ser la ficha 10, y las referencias al contexto apuntan al README de la 2da entrega |

### No traído

Los notebooks, los gráficos y el informe de hallazgos de la 2da entrega **no se
copiaron**. Esta entrega tiene los suyos, y conserva solo los gráficos y hallazgos que
cambian la decisión del inversor.

### Construido en esta entrega

| Archivo | Qué es |
|---|---|
| `src/espacial.py` | Fusión espacial y medida de accesibilidad. El cálculo de distancias (BallTree con métrica haversine, y la distancia a un polígono medida contra sus vértices) **se adaptó de `enriquecimiento.py`, del repositorio de trabajo del grupo** (`LladhonM/Analitica-Descriptiva`, commit `2f407b2`). Es nuevo: el Metrobús, la medida combinada, las capas versionadas, los reportes de cobertura y heterogeneidad, y que los parques excluyan los canteros centrales |
| `src/test_espacial.py` | 52 tests de la fusión espacial, con negativos |
| `data/external/transporte_estaciones.csv` | Bocas de subte, estaciones de tren y paradas de Metrobús, con fuente y fecha de descarga |
| `data/external/espacios_verdes.csv`, `espacios_verdes_vertices.csv` | Plazas y parques, y los vértices de sus polígonos |
| `data/processed/reporte_espacial.txt` | Log de `espacial.py`: capas, cobertura del dato, distancias, acceso por comuna y heterogeneidad por barrio |
| `README.md` | Este archivo |

Las capas se bajaron de Buenos Aires Data el 27-10-2026 y son idénticas, byte a byte, a
las que usaba `enriquecimiento.py`: se volvieron a descargar de la fuente oficial, con
fecha, en lugar de copiarse.

## Qué se construye en esta entrega

| # | Qué se entrega | Origen del pedido | Estado |
|---|---|---|---|
| 1 | Fusión espacial: distancia de cada aviso a subte, tren y Metrobús, y una medida de accesibilidad que combine los tres modos. Con eso, H2 deja de ser "no evaluable" | Devolución de la 2da entrega, prioridad 1 | Hecho: capas, medida y cobertura (ver [Accesibilidad al transporte](#accesibilidad-al-transporte)). El contraste de H2 va con los tests de la fila 2 |
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

## Accesibilidad al transporte

La devolución de la 2da entrega pidió no cerrar H2 con el subte solo, porque no cubre el
sur ni el oeste de la Ciudad. `espacial.py` mide, para cada aviso, la distancia a la
red de subte, a la de tren y a la de Metrobús, y las combina en una medida.

### La medida, en una frase

> **`dist_transporte_m`: los metros, en línea recta, hasta la estación más cercana de
> cualquiera de las tres redes masivas de la Ciudad (subte, tren o Metrobús).**

Es el mínimo de las tres distancias, sin pesos. Lo que un inquilino paga todos los días
es la caminata hasta la red: una vez adentro, cualquiera de las tres lo conecta con el
resto de la Ciudad. Se descartaron dos alternativas:

- **Un índice ponderado** exigiría pesar cada modo por su frecuencia, y no hay un dato
  de frecuencia por estación que se pueda unir. Los pesos serían inventados.
- **Contar cuántos modos hay cerca** confunde un conteo con una tasa: tener tres redes a
  300 m no da el triple de acceso que tener una.

Las distancias por modo (`dist_subte_m`, `dist_tren_m`, `dist_metrobus_m`) quedan como
columnas, junto con `modo_cercano` y `estacion_cercana`.

### Qué agrega la combinación frente al subte solo

Porcentaje de los avisos de cada comuna con una estación a menos de 800 m, que son
10 minutos a pie (`supuestos.RADIO_CAMINATA_M`):

| Comuna | Avisos | Subte | Tren | Metrobús | **Combinada** | La red más cercana no es el subte |
|---|---|---|---|---|---|---|
| 4 (sur) | 412 | 39,1% | 23,8% | 63,8% | **74,5%** | 85,4% |
| 8 (sur) | 197 | 0,0% | 29,4% | 55,8% | **72,1%** | 100,0% |
| 9 (oeste) | 395 | 2,0% | 18,2% | 37,0% | **45,6%** | 96,2% |
| 10 (oeste) | 616 | 6,5% | 38,3% | 69,6% | **70,3%** | 99,7% |
| 11 (oeste) | 902 | 0,0% | 47,5% | 56,0% | **75,3%** | 100,0% |
| Toda la Ciudad | 12.090 | 62,2% | | | **88,4%** | 51,8% |

Con el subte solo, las comunas 8 y 11 aparecían sin acceso a la red: ningún aviso tenía
una boca a 800 m. Con las tres redes, el 72,1% y el 75,3% tiene una estación a esa
distancia. En toda la Ciudad, la combinación pone dentro del radio a 3.164 avisos que el
subte dejaba afuera (26,2%). Tabla completa, con las 15 comunas, en
`data/processed/reporte_espacial.txt`.

### Lo que la medida no mide

**Una distancia en línea recta no es accesibilidad real.** La medida:

- **no ve barreras**: un aviso a 400 m de una estación en línea recta puede estar a
  1.500 m caminando si en el medio hay vías, una autopista o el Riachuelo;
- **no ve la frecuencia**: una estación de tren con un tren por hora no equivale a un
  subte cada cuatro minutos, y en la medida valen lo mismo;
- **no ve el destino**: estar cerca de una estación no dice adónde se llega desde ella
  ni en cuánto tiempo;
- **no incluye el Premetro**, que sirve a Villa Soldati y Villa Lugano. No está en
  las capas de subte del portal, así que en el sur la medida exagera la distancia a la
  red.

Por eso se la lee como una **cota inferior del esfuerzo de llegar a la red**, no como una
medida de qué tan bien conectado está un inmueble. Medir tiempo de viaje requeriría la
red de calles y los horarios de cada servicio, que este trabajo no integra.

### Nivel territorial

La medida es **por aviso, no por barrio**. En 20 de los 44 barrios con al menos 30
avisos conviven avisos a menos y a más de 800 m de la red, así que un promedio barrial
les asignaría a todos el mismo acceso. En Mataderos, el 10% más cercano está a 461 m o
menos y el 10% más lejano, a 2.358 m o más. Los resúmenes por zona se informan por
comuna y como tasas, porque la cartera de RE/MAX no pesa lo mismo en cada comuna.

### Cobertura del dato

7 de los 12.097 avisos (0,06%) no tienen coordenadas y quedan sin distancia, como nulo,
nunca como cero. **No se concentran en el sur**: hay 1 en Villa Lugano (comuna 8), 2 en
la comuna 10 (Floresta y Villa Real) y 4 en Palermo. Como tasa, el máximo es 0,51%, en
la comuna 8, que equivale a 1 aviso de 198. No sesgan la medida.

Las fuentes de cada capa, sus fechas y sus limitaciones están en
[`informe/FUENTES_EXTERNAS.md`](informe/FUENTES_EXTERNAS.md), fichas 6 a 9.

---

## Reproducir

Python 3.13. Desde esta carpeta:

```bash
py -m pip install -r requirements.txt

py src/limpieza.py --tc 1500             # crudo -> dataset limpio + auditoría
py src/variables.py                      # RegEx sobre el texto -> dummies
py src/espacial.py                       # distancias a subte, tren, Metrobús y plazas
py src/kpis.py                           # modelo de alquiler -> los 4 KPIs
py src/test_variables.py                 # motor RegEx, sin red
py src/test_supuestos.py                 # supuestos.py contra el pipeline
py src/test_fuentes.py                   # joins con fuentes externas, sin red
py src/test_eda.py                       # estadística de eda.py, sin datos
py src/test_espacial.py                  # fusión espacial, sin red
```

`limpieza.py`, `variables.py`, `espacial.py` y `kpis.py` reconstruyen `data/processed/`
a partir de `data/raw/dataset_maestro.csv`. Los intermedios (`dataset_limpio.csv`,
`dataset_excluidos.csv`, `dataset_variables.csv`, `dataset_espacial.csv`) no se
versionan.

`espacial.py` usa las capas versionadas de `data/external/`, así que corre sin red. Con
`--descargar` vuelve a bajarlas de Buenos Aires Data a `data/external/raw/` (no
versionado; el archivo de espacios verdes pesa 15 MB) y rehace las capas con la fecha
del día.

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
│   ├── external/       tablas fechadas de las fuentes externas y capas espaciales
│   └── reference/      ranking de barrios de la 1ra entrega, para comparar
├── informe/            FUENTES_EXTERNAS.md
├── src/                pipeline, supuestos y tests
├── requirements.txt
└── README.md
```

Las carpetas de notebooks, gráficos y tablero se agregan cuando se crean.
