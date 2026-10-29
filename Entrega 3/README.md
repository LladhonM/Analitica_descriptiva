# Validación, análisis avanzado y decisión — mercado inmobiliario de CABA

**TP Integrador · 82.04 Analítica Descriptiva (ITBA) · Grupo 2 · 3ra pre-entrega**

Tercera etapa del análisis de rentabilidad inmobiliaria para un pequeño inversor
particular que, con USD 80.000 a 200.000, evalúa comprar **una** unidad en CABA para
alquilarla. Esta entrega valida formalmente las hipótesis, completa la fusión espacial,
y resuelve y evalúa la decisión del inversor, con un tablero orientado a él.

La 1ra y la 2da entrega están en sus propias carpetas y no se modifican. Esta carpeta es
autónoma: tiene su propio pipeline, sus datos y sus tests, y no lee nada fuera de ella.

---

## Hallazgos, en cinco líneas

El desarrollo, con cada cifra calculada en vivo, está en
[`informe/INFORME_HALLAZGOS.md`](informe/INFORME_HALLAZGOS.md), ordenado por cuánto cambia
la decisión del inversor.

1. **Para la propiedad típica, la decisión es no comprar.** La neta mediana (5,65%)
   queda debajo de la banda de retorno mínimo (7,10% a 7,60%). Con los costos de entrada,
   la TIR a 5 años baja a 4,27%. Solo 18 de 4.484 propiedades superan el techo en el
   escenario pesimista, y 4 con costos de entrada.
2. **No hay una "mejor propiedad".** Solo el 7% de los pares de propiedades se distingue
   con la banda de error. P2 devuelve una lista corta de 140, no un ranking.
3. **El barrio es la palanca más fuerte**: cada USD 500 más de m² resta alrededor de un
   punto de rentabilidad (H1). Las torres nuevas con amenities rinden menos: cuestan un
   tercio más por m² y se alquilan solo un sexto más.
4. **El temporal no rescata la inversión**, salvo para quien lo autogestione con más de
   la mitad del año ocupado.
5. **La cercanía al transporte ya está en el precio del barrio**: hasta 1 km no se
   paga, y más allá el m² vale alrededor de 7% menos (H2, reformulada).

---

## Estado

La carpeta contiene la **base heredada de la 2da entrega, depurada y verificada**: el
pipeline corre acá desde el crudo y reproduce las cifras de referencia (ver
[Reproducir](#reproducir)). Sobre esa base están hechas:

- la **fusión espacial** y la medida de accesibilidad (ver
  [Accesibilidad al transporte](#accesibilidad-al-transporte));
- la **magnitud y forma de H2** (ver [H2](#h2-precio-del-m²-y-distancia-a-la-red));
- el **ABL segmentado** y los **costos de entrada y refacción**, que cambian el KPI 2 y
  suman la TIR a 5 años (ver [Costos del propietario](#costos-del-propietario-antes-y-después));
- la **revisión del modelo de alquiler** y la banda cuantílica del KPI 4 (ver
  [Modelo de alquiler](#modelo-de-alquiler));
- los **tests formales de H1 a H4** (ver [Hipótesis](#hipótesis-los-tests-formales));
- la **síntesis de atributos (PCA y MCA) y los micro-mercados**, como análisis
  informativo que no entra al modelo (ver [Síntesis de atributos](#síntesis-de-atributos-y-micro-mercados));
- la **función de decisión** para P1 a P3, implementada y evaluada (ver
  [Función de decisión](#función-de-decisión));
- el **informe de hallazgos**, regenerado con todo lo anterior;
- el **dataset para el tablero**, con su diccionario y una guía de qué columnas usar
  ([`data/processed/GUIA_TABLERO.md`](data/processed/GUIA_TABLERO.md)).

Falta el **tablero**, que arma otro integrante del grupo con este dataset. La revisión
del modelo no cambió el alquiler estimado, así que los KPIs 1 a 3 quedan fijos; el KPI 4
sí cambió. El resto se registra en la tabla
[Qué se construye en esta entrega](#qué-se-construye-en-esta-entrega).

---

## Cómo leer el trabajo: los notebooks

Los notebooks cuentan el análisis en orden y guían la lectura. Cada uno responde una
pregunta del inversor; los scripts de `src/` hacen las cuentas y los notebooks las
recorren, con cada gráfico entre su pregunta y su lectura. Están guardados con sus
salidas, así que se leen sin ejecutar nada.

| Notebook | La pregunta | Gráficos |
|---|---|---|
| [`01_accesibilidad`](notebooks/01_accesibilidad.ipynb) | ¿Qué tan conectada está cada propiedad a la red de transporte, y el mercado lo paga en el precio? Capas, medida, cobertura y forma de H2 | 01 a 03 |
| [`02_costos_del_propietario`](notebooks/02_costos_del_propietario.ipynb) | ¿Cuánto le queda al inversor después de los costos, y le gana a una ON? ABL segmentado, costos de entrada, TIR, refacción y sensibilidad | 04 y 05 |
| [`03_modelo_alquiler`](notebooks/03_modelo_alquiler.ipynb) | ¿Cuánto se puede confiar en el alquiler estimado? Comparación contra una referencia, qué paga el mercado y la banda del KPI 4 | 06 a 08 |
| [`04_validacion`](notebooks/04_validacion.ipynb) | ¿Qué hipótesis se sostienen con un contraste formal, con qué magnitud, y cuáles cambian la decisión? | 09 y 10 |
| [`05_sintesis_atributos`](notebooks/05_sintesis_atributos.ipynb) | ¿Se pueden resumir los 29 atributos del aviso en pocos ejes, y hay tipos de propiedad que rinden distinto en el mismo barrio y tamaño? PCA, MCA, micro-mercados y por qué no entran al modelo | 11 y 12 |
| [`06_decision`](notebooks/06_decision.ipynb) | ¿Conviene comprar, qué propiedad, y tradicional o temporal? La función de decisión para P1 a P3, cuánto distingue y cuánto depende de los supuestos | 13 a 15 |

La limpieza, la minería de texto y el EDA de la 2da entrega no se repiten: están en sus
notebooks 01 a 03, y esta carpeta parte de su resultado.

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
| `src/kpis.py` | Lee `dataset_espacial.csv` (salida de `espacial.py`) en lugar de `dataset_variables.csv`. **El KPI 2 usa el ABL de cada propiedad** (`costos.py`) en lugar de un porcentaje plano; `--gastos` vuelve al plano. Suma costos de entrada, refacción y TIR a 5 años, el antes y el después, y una segunda grilla de sensibilidad (ABL × costos de entrada × vacancia). Calcula la banda cuantílica del KPI 4 y guarda el `.joblib` con metadata: versión de scikit-learn, fecha, hash de los datos de entrenamiento, predictoras y métricas. El modelo de alquiler no cambia. En el docstring, el apartado sobre las dummies de RegEx se atribuye a la 2da entrega |
| `src/modelo_alquiler.py` | Se quitó el `main()`, un punto de entrada heredado de la 1ra entrega que no usaba nadie: aplicaba vacancia 8% y gastos 12% (no los de `supuestos.py`), escribía archivos que el pipeline no usa y pisaba `ranking_barrios.csv`. El docstring deja de citar un error de ~11,5%, que no es el vigente (11,2%). `calcular_rentabilidad` acepta gastos por propiedad. **El ranking de barrios se ordena por neta y no por bruta**, con desempate por nombre: con el ABL segmentado ya no es lo mismo, y el orden ya no cambia entre corridas. **La banda del KPI 4 es nueva**: regresión cuantílica calibrada por grupo de evidencia (`banda_cuantilica`) en lugar del error mediano del tramo. `entrenar_y_validar` devuelve sus métricas para la metadata del `.joblib`. El Ridge no cambia |
| `src/supuestos.py` | Se quitaron constantes que ningún script ni notebook leía (`TOP_BARRIOS_HEATMAP` y tres `SCATTER_*`); la fecha de consulta y el umbral de completitud pasan a comentario. Nuevas secciones: radio de caminata y tramos de H2 (4b2), criterio para reemplazar el modelo (`MEJORA_MINIMA_R2`), nivel de significación de los tests (`ALFA`), ABL segmentado (3b2), costos de entrada (3e), refacción (3f) y riesgo legal como limitación (3g) y la función de decisión (4d: soporte del modelo, margen por liquidez y grillas de sensibilidad). **Se corrigieron dos errores heredados del ABL**: el ejemplo de ARS 43.994 es con coeficiente geográfico 1,75 y no 1,25, y la fuente no dice que una VFH de 15 a 25 millones sea "el rango de un 2 ambientes usado" |
| `src/eda.py` | Se quitaron un import sin uso (`matplotlib.pyplot`), un color que no se usaba (`BUENO`) y tres funciones que solo usaban los notebooks de la 2da entrega y su informe (`leer_asimetria`, `cobertura_estratos`, `resumir_efecto`) |
| `src/temporal.py` | Se quitó un import sin uso (`numpy`). `lado_remax()` acepta la ruta del dataset como parámetro. La neta tradicional y los fijos del temporal usan el ABL mediano de cada celda en lugar del plano, para que P3 use los mismos gastos que el KPI 2 |
| `src/reporte.py` | **Reescrito con los hallazgos de esta entrega**, ordenados por cuánto cambian la decisión: la función de decisión, los costos de entrada, el modelo y su banda, los tests formales, los micro-mercados, el temporal, el sesgo de la cartera y H2. Solo quedan los hallazgos que cambian la decisión, y se listan los de la 2da que no siguen. Las cifras de los tests salen de `validacion.resumen_hipotesis`. Vuelve a ser parte del pipeline |
| `src/sesgo.py` | Sin cambios |
| `src/fuentes_externas.py` | Sin cambios |
| `src/test_fuentes.py` | Resuelve las rutas desde la ubicación del archivo: antes solo corría desde la raíz de la entrega |
| `src/test_supuestos.py` | Verifica el contrato nuevo del KPI 2 (gastos de cada propiedad = 10,24% + su ABL), la tabla de coeficientes geográficos (48 barrios, entre 0 y 2), la escala del Impuesto Inmobiliario y los rangos de los costos de entrada. Incluye un negativo: con el gasto plano, la neta del dataset no coincide |
| `src/test_variables.py` | Sin cambios |
| `src/test_eda.py` | Sin los tests de esas tres funciones. Los del efecto estratificado verifican `efecto_estratificado` con `mediana_ponderada`, que es lo que usan el informe y el notebook 02 |

**Datos (`data/`)**

| Archivo | Estado |
|---|---|
| `data/raw/dataset_maestro.csv` | Sin cambios. Es el crudo del scraping de la 1ra entrega (14.867 avisos, 16-08-2026) |
| `data/external/` (7 tablas y `reporte_fuentes.txt`) | Sin cambios. Tablas agregadas y fechadas de IDECBA, Colegio de Escribanos, Inside Airbnb y Censo 2022 |
| `data/reference/` (`ranking_barrios_entrega1.csv`, `LEEME.md`) | Sin cambios |
| `data/processed/` — `auditoria_calidad.csv`, `reporte_limpieza.txt`, `reporte_regex.txt` | **Regenerados en esta carpeta** por `limpieza.py` y `variables.py`. Contenido idéntico al de la 2da entrega; los reportes cambian la fecha de corrida |
| `data/processed/` — `dataset_analitico.csv`, `ranking_barrios.csv`, `modelo_alquiler.joblib`, `sensibilidad_supuestos.csv`, `reporte_kpis.txt` | **Regenerados con contenido nuevo** por `espacial.py` y `kpis.py`. `dataset_analitico.csv` suma 17 columnas (accesibilidad, costos y percentiles del alquiler) y pierde `error_estimacion`; `rent_neta_pct` usa el ABL segmentado y `rent_bruta_min` / `rent_bruta_max` salen de la banda cuantílica; el resto de las columnas heredadas no cambia. El ranking se ordena por neta. La sensibilidad suma la grilla B |
| `data/processed/` — `temporal_vs_tradicional.csv`, `reporte_temporal.txt` | **Regenerados** por `temporal.py`, con el ABL segmentado |
| `data/processed/` — `sesgo_precio_barrio.csv`, `sesgo_representacion_comuna.csv`, `reporte_sesgo.txt` | **Regenerados** por `sesgo.py` en la corrida completa. Contenido idéntico al de la 2da entrega: `sesgo.py` no usa la neta; el reporte cambia la fecha de corrida |
| `data/processed/DICCIONARIO_DATOS.md` | El encabezado deja de presentar la matriz como "de la 2da pre-entrega". Se agregaron la sección 8.1 (ABL, costos y TIR), la 9 (accesibilidad), la 10 (función de decisión), los pasos nuevos del linaje, la fórmula nueva de `rent_neta_pct` y cuatro advertencias de uso |

**Configuración**

| Archivo | Estado |
|---|---|
| `requirements.txt` | Versiones exactas en lugar de mínimas. Se agregó `openpyxl`: `fuentes_externas.py` lo importa para leer los cuadros de IDECBA y del Colegio, y no estaba declarado |
| `.gitignore` | Se agregó `dataset_espacial.csv`, el intermedio nuevo del pipeline, y el comentario registra que `decision.py` también escribe en el dataset analítico |

**Documentación**

| Archivo | Estado |
|---|---|
| `informe/FUENTES_EXTERNAS.md` | Traído **en un segundo paso**, al incorporar las capas espaciales: no estaba en la copia inicial. Sale del mismo commit `24e09b6` y era idéntico al de la 2da entrega al traerlo. Se trajo en lugar de escribir un catálogo nuevo para que las fuentes 1 a 5, cuyas tablas sí están en `data/external/`, sigan documentadas en esta carpeta. Cambios: las fichas 6 a 9 (subte, tren, Metrobús, espacios verdes) reemplazan a la ficha "planificada" de transporte; se suma la sección sobre qué mide la distancia y qué no; el IPC pasa a ser la ficha 10, y las referencias al contexto apuntan al README de la 2da entrega |

### No traído

Los notebooks, los gráficos y el informe de hallazgos de la 2da entrega **no se
copiaron**. Esta entrega tiene los suyos (ver [Cómo leer el trabajo](#cómo-leer-el-trabajo-los-notebooks)),
y conserva solo los gráficos y hallazgos que cambian la decisión del inversor.

### Construido en esta entrega

| Archivo | Qué es |
|---|---|
| `src/espacial.py` | Fusión espacial y medida de accesibilidad. El cálculo de distancias (BallTree con métrica haversine, y la distancia a un polígono medida contra sus vértices) **se adaptó de `enriquecimiento.py`, del repositorio de trabajo del grupo** (`LladhonM/Analitica-Descriptiva`, commit `2f407b2`). Es nuevo: el Metrobús, la medida combinada, las capas versionadas, los reportes de cobertura y heterogeneidad, y que los parques excluyan los canteros centrales |
| `src/test_espacial.py` | 52 tests de la fusión espacial, con negativos |
| `src/accesibilidad.py` | H2: pendiente con y sin barrio fijo, perfil por tramos de distancia, radio de influencia y réplica del antecedente del repositorio de trabajo |
| `src/test_accesibilidad.py` | 8 tests de H2, sobre datos sintéticos con la respuesta conocida: el barrio fijo elimina la centralidad pura y el perfil recupera una penalidad plantada |
| `src/costos.py` | Fórmulas del ABL segmentado (Ley 6927), costos de entrada, refacción y TIR a 5 años. Los números están en `supuestos.py` |
| `src/test_costos.py` | 38 tests. El ABL se valida contra un oráculo externo: los siete ejemplos que calcula Roomix con la Ley 6927 |
| `data/processed/h2_perfil_distancia.csv`, `reporte_h2.txt` | Salida de `accesibilidad.py` |
| `data/processed/antes_despues_kpis.csv` | Neta mediana, barrios sobre el piso y top 5, antes y después del ajuste |
| `src/comparacion_modelos.py` | El modelo de alquiler contra una referencia simple, con variables espaciales y contra gradient boosting, fuera de muestra en tres semillas, y la cobertura de la banda anterior contra la nueva (`cobertura_banda.csv`) |
| `src/test_modelo.py` | 25 tests: la calibración conformal sobre un caso sintético, la metadata del `.joblib` (con su hash contra los datos de entrada) y la coherencia de la banda |
| `data/processed/comparacion_modelos.csv`, `cobertura_banda.csv`, `reporte_comparacion_modelos.txt` | Salida de `comparacion_modelos.py` |
| `notebooks/01_accesibilidad.ipynb`, `02_costos_del_propietario.ipynb`, `03_modelo_alquiler.ipynb` | Los notebooks de esta entrega (ver [Cómo leer el trabajo](#cómo-leer-el-trabajo-los-notebooks)) |
| `src/validacion.py` | Las piezas de los tests formales: Spearman por permutación, Holm, errores agrupados, Van Elteren y la pendiente con efectos fijos de celda con su bootstrap. `resumen_hipotesis` repite los cuatro tests con las semillas del notebook 04 para el informe |
| `src/test_validacion.py` | 19 tests de esas piezas contra oráculos independientes (scipy, la regresión con dummies, HC1), con negativos |
| `notebooks/04_validacion.ipynb` | Los tests formales de H1 a H4 |
| `src/sintesis.py` | PCA sobre las dummies, MCA con la corrección de Benzécri, micro-mercados por k-medias con su estabilidad, y la prima de cada grupo con precios observados |
| `src/test_sintesis.py` | 18 tests: el MCA contra el chi-cuadrado de scipy y la fórmula de transición, los micro-mercados contra grupos plantados y la prima contra una prima plantada, con negativos |
| `notebooks/05_sintesis_atributos.ipynb` | La síntesis de atributos y los micro-mercados |
| `src/decision.py` | La función de decisión: P1, P2 y P3, su evaluación y su sensibilidad. Agrega 14 columnas al dataset analítico |
| `src/test_decision.py` | 25 tests: la frontera y los pares de P2 contra la comparación de todos los pares, la neta central contra `kpis.py`, la ocupación de equilibrio contra `temporal.py`, con negativos |
| `notebooks/06_decision.ipynb` | La función de decisión |
| `data/processed/decision_sensibilidad.csv`, `decision_p3.csv`, `reporte_decision.txt` | Salida de `decision.py` |
| `informe/INFORME_HALLAZGOS.md` | El informe de esta entrega, que emite `reporte.py` |
| `data/processed/GUIA_TABLERO.md` | Para quien arma el tablero: qué columnas usar y cuáles son internas, y las limitaciones que van en pantalla |
| `graficos/01` a `15` | Los gráficos que guardan los notebooks |
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
| 1 | Fusión espacial: distancia de cada aviso a subte, tren y Metrobús, y una medida de accesibilidad que combine los tres modos. Con eso, H2 deja de ser "no evaluable" | Devolución de la 2da entrega, prioridad 1 | Hecho: capas, medida, cobertura, y magnitud y forma de H2 (ver [H2](#h2-precio-del-m²-y-distancia-a-la-red)). El contraste con p-valor va con los tests de la fila 2 |
| 2 | Tests formales de H1 a H4, con p-valor, tamaño del efecto, intervalo y lectura de si cambian la decisión | Devolución, prioridad 2 | Hecho (ver [Hipótesis](#hipótesis-los-tests-formales)) |
| 3 | Función de decisión prescriptiva para P1 (comprar o no), P2 (qué propiedad) y P3 (tradicional o temporal), **implementada y evaluada** | Devolución, prioridad 3; consigna de la 3ra entrega | Hecho (ver [Función de decisión](#función-de-decisión)) |
| 4 | ABL segmentado por barrio, superficie y tipo de propiedad, y su efecto sobre la rentabilidad neta | Devolución, prioridad 4 | Hecho (ver [Costos del propietario](#costos-del-propietario-antes-y-después)) |
| 5 | Costos de entrada, refacción, liquidez y riesgo legal, con fuente y fecha en `supuestos.py` | Devolución, prioridad 5 | Hecho: entrada y refacción con fuente; riesgo legal como limitación declarada. La liquidez sigue siendo la del tiempo de publicación de IDECBA (ficha 5 del catálogo) |
| 6 | Síntesis de atributos (PCA/MCA) y micro-mercados | Plan de la 2da entrega | Hecho, como análisis informativo: no entra al modelo (ver [Síntesis de atributos](#síntesis-de-atributos-y-micro-mercados)) |
| 7 | Revisión del modelo de alquiler con las variables espaciales y contra una referencia simple | Plan de la 2da entrega; devolución | Hecho (ver [Modelo de alquiler](#modelo-de-alquiler)) |
| 8 | Tablero para el inversor (Power BI) | Consigna de la 3ra entrega | A cargo de otro integrante del grupo. De este lado está hecho el insumo: el dataset final, el diccionario y [`GUIA_TABLERO.md`](data/processed/GUIA_TABLERO.md) |
| 9 | Depuración del repositorio: código sin uso, referencias a versiones anteriores, versiones fijas, tests independientes del directorio | Devolución, prioridad 6 | Hecho (ver [Procedencia](#procedencia-de-cada-archivo)) |
| 10 | Informe de hallazgos con lo nuevo, conservando solo lo que cambia la decisión | Devolución, prioridad 7 | Hecho ([`informe/INFORME_HALLAZGOS.md`](informe/INFORME_HALLAZGOS.md)) |

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

## H2: precio del m² y distancia a la red

> **H2.** El precio del m² decrece con la distancia al transporte, y existe un radio de
> influencia a partir del cual el beneficio se diluye.

`py src/accesibilidad.py` estima la **magnitud y la forma** de la relación con el método
declarado desde la 1ra entrega: regresión de log(USD/m²) sobre la distancia, **con efectos
fijos de barrio**. Base: 10.743 avisos de venta. El contraste formal está en la sección
[Hipótesis](#hipótesis-los-tests-formales): la versión lineal no se sostiene y H2 se
reformula como un escalón a 1 km.

**Sin el barrio se mide centralidad.** Sin efectos fijos, cada kilómetro hasta la red
resta 12,9% al m². Con el barrio fijo, la pendiente baja a −6,2% por km, y la distancia
agrega **0,0018 de R²** a un modelo donde el barrio solo explica 0,422.

**La forma: plana hasta 1 km, con un escalón después.** Efecto sobre el m² contra los
avisos a menos de 300 m de la red, con barrio fijo y controles del inmueble (tipo,
superficie, antigüedad, a reciclar, amenities, cochera):

| Distancia a la red (m) | 300-600 | 600-1.000 | 1.000-1.500 | 1.500+ |
|---|---|---|---|---|
| Avisos | 3.658 | 2.023 | 512 | 163 |
| Todos los tipos | +2,3% | −0,6% | **−6,0%** | −7,2% |
| Solo departamentos | +2,3% | −0,6% | **−6,2%** | −1,6% |

Los controles importan. Sin ellos, el tramo de 1.500 m o más daba −16,0%, pero el 64% de
esos avisos son casas y PH (contra 12% a menos de 300 m), que tienen otro precio del m²
por razones que no son la distancia. El escalón robusto es el de 1 a 1,5 km.

**Radio de influencia: entre 600 y 1.000 m.** Un modelo con quiebre ajusta mejor con
umbral de 600 m (−8,1% por km más allá), pero la diferencia de R² entre el mejor y el
peor umbral es de 0,001: el quiebre se lee como un rango, no como un número. El perfil
por tramos lo ubica a partir de 1 km.

**Por modo, con controles,** el efecto viene del subte (−6,1% a más de 1,5 km). Ni el tren
(−0,9%) ni el Metrobús (−1,3%) penalizan la lejanía, y estar a 300-1.500 m del tren
no vale menos que estar al lado.

**El antecedente no se replica en sus términos.** En el repositorio de trabajo había
aparecido una correlación intra-barrio negativa con la distancia al subte a más de 1 km.
Con estos datos, el Spearman entre el precio descontado el promedio del barrio y la
distancia al subte es **0,000** en los 3.375 avisos a más de 1 km.

**Lectura.** La primera mitad del enunciado propuesto se sostiene: *la accesibilidad ya
está incorporada en el precio del barrio*. Dentro del barrio, estar a 300 m o a 1 km de
la red no cambia el m². La segunda mitad se sostiene con una precisión: *salvo donde el
transporte escasea*, entendido como el aviso y no el barrio. El 6% de los avisos a más
de 1 km de las tres redes cotiza alrededor de 6% menos que sus comparables del mismo
barrio. Para P2, esto significa que el inversor no paga una prima por estar más cerca de
una estación dentro de su barrio, y que el descuento lejos de la red es chico y está
concentrado en pocos avisos.

---

## Costos del propietario: antes y después

### ABL segmentado

El ABL dejó de ser un 3,80% plano del alquiler. Ahora se calcula por propiedad con la
**Ley Tarifaria 2026** (Ley 6927, anexo, arts. 41 a 45):

- el Impuesto Inmobiliario, con su escala progresiva;
- la Tasa ABL, con el **coeficiente geográfico de cada barrio**;
- el recargo, el mínimo y el tope.

La base es la Valuación Fiscal Homogénea (VFH), que AGIP no publica por partida. Se
aproxima como `proporción × USD/m² mediano del barrio y tipo × superficie`, que sigue
cómo la define el Código Fiscal (art. 288: parte del valor de mercado por m² de la zona,
con tope en el 20% del valor de mercado). Así queda segmentado por barrio, superficie y
tipo de propiedad.

La proporción **no tiene fuente publicada**: es una estimación propia. Se calibra en
14,99% para que la unidad de referencia (2 ambientes, 40 a 60 m²) siga pagando 3,80%. De
ese modo el ajuste **redistribuye** el ABL sin cambiar su nivel, y el nivel se prueba
aparte con la proporción en el tope legal del 20%. La fórmula reproduce al peso los
siete ejemplos que calcula Roomix con la misma ley (`test_costos.py`).

| ABL como % del alquiler, por quintil de rentabilidad bruta (base confiable) | Q1 (rinde menos) | Q2 | Q3 | Q4 | Q5 (rinde más) |
|---|---|---|---|---|---|
| Plano (2da entrega) | 3,80% | 3,80% | 3,80% | 3,80% | 3,80% |
| Segmentado | 4,65% | 4,29% | 3,99% | 3,62% | 3,19% |

El plano les cobraba de menos a las unidades que rinden poco y de más a las que rinden
mucho, como había advertido la devolución.

### Costos de entrada y refacción

Con fuente y fecha en `supuestos.py`, secciones 3e y 3f. El escenario base usa el
**piso de cada rango publicado**, así que el efecto que se informa es un mínimo.

| Costo | Base | Alto | Fuente |
|---|---|---|---|
| Comisión inmobiliaria del comprador | 3% | 4% | CUCICBA, 09-01-2026 (Ley 2340, mod. Ley 5859) |
| Escribano | 1% | 2% | La Nación, 01-05-2026 |
| Certificados, informes e inscripción | 0,2% | 0,4% | La Nación, 01-05-2026 |
| Impuesto de Sellos, mitad del comprador | 1,35% hasta ARS 226,1 millones; 1,75% arriba | ídem | Ley 6927, anexo, art. 34; reparto por mitades: La Nación, 01-05-2026 |
| **Total, mediana** | **5,55%** | **7,75%** | |
| Refacción de una unidad a reciclar | Baño USD 5.573 + cocina USD 6.220 + pintura | Integral, ARS 1.350.000/m² + IVA | Reporte Inmobiliario (enero de 2026) y Sui Color, vía La Nación, 30-03-2026; RenovArqui, febrero de 2026 |

Ninguna fuente aclara si la comisión y el escribano llevan IVA, así que no se sumó. Una
guía de Roomix sobre refacción quedó afuera: no cita fuente, y su refacción integral de
un 50 m² sale más barata que el baño y la cocina de Reporte Inmobiliario.

**La refacción y el descuento de H3.** Las unidades a reciclar cotizan 23,3% más barato
por m² que sus comparables, lo mismo que en la 2da entrega y recalculado en la misma
corrida. Sobre el precio de la unidad, ese descuento equivale a 30,3%. La refacción
mínima cuesta una mediana de 13,5% del precio y el descuento la cubre en el 94% de las
unidades: ahí el descuento sí es una oportunidad. La integral cuesta 83,4% y no la cubre
en ninguna. Refaccionada, la unidad se alquila 14,4% más según el modelo. Ese beneficio
entra en la TIR, para no cobrar la obra sin su efecto.

**Riesgo legal: limitación declarada, sin número.** Juicios de desalojo, inquilinos que
no pagan, cambios de régimen como los de la Ley 27.551 y el DNU 70/2023. No hay una
fuente que publique su frecuencia o su costo para CABA, y estimarlo sería peor que no
tenerlo. No entra en ningún KPI, y todo resultado de este trabajo es optimista en esa
medida.

### TIR a 5 años

Los costos de entrada se pagan una vez y no vuelven al vender, así que no se pueden
restar de una rentabilidad anual. Se suma una columna, `tir_5a_pct`.

> **TIR a 5 años:** la tasa anual que iguala lo que se pone al comprar (precio, costos
> de entrada y refacción) con lo que se recibe (5 años de alquiler neto y la reventa al
> mismo precio en dólares).

Es la cifra comparable con la banda de retorno mínimo, que es la TIR de una ON a un
plazo parecido. Sin costos de entrada es igual a la neta. No incluye apreciación,
costos de salida ni meses de obra sin alquiler.

### Antes y después

Base: 9.203 ventas con estimación confiable; barrios con al menos 30 ventas. Piso de la
banda de retorno mínimo: 7,10%.

| | Mediana | Barrios sobre el piso | Top 5 del ranking |
|---|---|---|---|
| **Antes**: neta, ABL plano | 5,67% | 1 (Constitución) | Constitución, San Cristóbal, San Telmo, Balvanera, Liniers |
| Neta, ABL segmentado | **5,65%** | 1 (Constitución) | Constitución, San Cristóbal, San Telmo, Liniers, Balvanera |
| TIR a 5 años, ABL segmentado + costos de entrada | **4,27%** | **0** | Constitución, San Telmo, San Cristóbal, Liniers, San Nicolás |

- **El ABL segmentado redistribuye, pero no mueve la conclusión.** La neta mediana
  baja 0,02 pp y el ranking casi no cambia (Spearman 0,996 contra el plano): sube Villa
  Urquiza 2 puestos y bajan San Nicolás, Retiro y Villa Luro uno cada uno. Constitución
  pasa de 8,17% a 8,35%, porque su ABL baja: es barato, y el plano le cobraba de más.
- **Los costos de entrada sí la mueven.** Restan 1,38 pp por año en el horizonte, y
  ningún barrio supera el piso. Constitución, el único que lo superaba, queda en una
  TIR de 6,44%. El hallazgo central se refuerza: **la propiedad mediana no le gana a una
  ON en dólares, y con los costos de comprar la distancia al piso pasa de 1,45 a 2,83
  puntos.**
- **P3 casi no cambia.** Con el ABL de cada celda en los dos modos, la ocupación de
  equilibrio mediana del temporal pasa de 65,3% a 65,5% (de 51,5% a 51,7%
  autogestionado), y con 53% de ocupación el temporal gana en 2 de 47 celdas, antes 3.

### Sensibilidad

La grilla de la 2da entrega (vacancia × gastos planos) se conserva. Se suma una grilla B:
vacancia (4% a 12%) × definición del ABL (plano, segmentado, segmentado con la VFH en el
tope legal) × costos de entrada (sin, base, alto), con 45 escenarios en
`sensibilidad_supuestos.csv`.

- **Nivel:** la mediana va de 3,33% a 5,78%.
- **Piso:** los barrios sobre el piso van de 0 a 2. Ninguno lo supera en un escenario
  con costos de entrada.
- **Ranking:** la definición del ABL lo mueve hasta un Spearman de 0,996, y los costos
  de entrada, hasta 0,991.

Ninguna definición reordena el ranking de manera apreciable, aunque el quinto puesto
cambia entre escenarios (el top 5 es idéntico al base en 10 de 45). Todas las que suman
costos de entrada dejan a toda la Ciudad debajo de la vara.

---

## Modelo de alquiler

La devolución difirió a esta entrega la revisión del modelo, y la consigna pide
compararlo con una referencia razonable y evaluarlo fuera de muestra. Desarrollo
completo en el [notebook 03](notebooks/03_modelo_alquiler.ipynb).

### La tabla comparativa

`py src/comparacion_modelos.py`: validación cruzada de 5 particiones, repetida con tres
semillas (42, la del modelo vigente, 7 y 2026). Promedio de las tres, con el rango
entre corchetes:

| Modelo | R² en log | Error relativo mediano | Error, < 35 m² | Error, 100+ m² |
|---|---|---|---|---|
| Mediana de barrio × tramo de superficie (referencia) | 0,751 [0,743, 0,755] | 15,05% | 12,5% | 22,7% |
| **Ridge vigente, 21 predictoras** | **0,847 [0,846, 0,848]** | **11,42%** | 11,1% | 17,0% |
| Ridge + variables espaciales | 0,847 [0,846, 0,848] | 11,56% | 10,9% | 17,1% |
| Gradient boosting, mismas variables, afinado | 0,844 [0,842, 0,849] | 11,41% | 9,4% | 19,2% |

**La decisión.** El Ridge le gana a la referencia con claridad: casi diez puntos de R²
y casi cuatro de error. Ninguna alternativa le gana a él. Las variables espaciales no
agregan (coherente con H2: la accesibilidad ya está en el barrio, que es predictora), y
el boosting empata dentro del rango de las semillas. El criterio se declaró antes de
mirar el resultado (`supuestos.MEJORA_MINIMA_R2`): una alternativa reemplaza al Ridge
solo si mejora el R² en 0,01 en todas las semillas. **El Ridge se queda, y el alquiler
estimado y los KPIs 1 a 3 no cambian.** Sus coeficientes se leen como cuánto paga el
mercado por cada característica, y esa lectura es parte del producto para el inversor.

**Las variables espaciales.** Son las seis distancias de `espacial.py`: al subte, al
tren, al Metrobús, a la red más cercana de las tres, y a la plaza y al parque más
cercanos. Se probaron solo en la variante "Ridge + espaciales": el modelo vigente nunca
las incluyó y sigue con las 21 predictoras de la 2da entrega. No se eliminaron del
trabajo: siguen como columnas del dataset, se usan para H2 y quedan disponibles para el
tablero.

### La banda del KPI 4

Hasta la 2da entrega, la banda de cada propiedad era su estimación más y menos el error
mediano de su tramo de superficie. Ahora son los **percentiles 10 y 90** de su alquiler:
una regresión cuantílica con las variables del Ridge, calibrada por grupo de evidencia
del barrio con *conformalized quantile regression* (Romano, Patterson y Candès, 2019).

| Banda | Alquileres observados dentro, fuera de muestra |
|---|---|
| 2da entrega: estimación ± error mediano del tramo | 50,1% |
| Regresión cuantílica sola | 77,5% |
| **Regresión cuantílica calibrada** | **81,6%** (objetivo 80%; entre 80% y 84% en cada grupo de evidencia) |

**Esto no mejora la estimación puntual del alquiler, que no cambia.** Mejora lo que se
sabe sobre cuánta confianza merece. La banda anterior prometía una precisión que no
tenía: por construcción, dejaba afuera a la mitad. La nueva es más ancha (3,45 puntos de
rentabilidad bruta en la mediana, 4,92 en las unidades de más de 100 m²) y dos de cada
tres propiedades tienen una banda que contiene la rentabilidad mediana del mercado. Es
el insumo del criterio de P2 en la función de decisión.

Un resultado que no era el esperado: los barrios con menos de 10 alquileres no se
predicen peor fuera de muestra (la banda sin calibrar los cubría en 80,7%), así que su
banda no necesita ser mucho más ancha. El ancho depende más del tamaño de la propiedad
que de cuántos datos hay en su barrio.

### El modelo guardado

`modelo_alquiler.joblib` guarda, además del pipeline y la banda, la versión de
scikit-learn, la fecha de entrenamiento, el hash SHA-256 de los datos de entrenamiento,
la lista de predictoras y las métricas de validación. `test_modelo.py` verifica que el
hash coincida con los alquileres de entrada: si no, el modelo es de otra corrida.

---

## Hipótesis: los tests formales

Los cuatro tests que la 2da entrega dejó declarados, ejecutados en el
[notebook 04](notebooks/04_validacion.ipynb). Con 9.203 ventas casi cualquier efecto da
significativo, así que cada test cierra con el p-valor, el tamaño del efecto en
unidades del inversor, un intervalo del 95% y si cambia la decisión. α = 0,05, fijado
antes de correrlos (`supuestos.ALFA`).

| Hipótesis | Test | H₀ | Efecto | IC 95% | ¿Cambia la decisión? |
|---|---|---|---|---|---|
| **H1** — la rentabilidad cae con el precio del m² del barrio | Spearman unilateral, p por permutación; repetido en 5 tramos de superficie con Holm | Se rechaza (p < 0,001), también en los 5 tramos | −0,98 pp de bruta por cada USD 500/m² del barrio (ρ = −0,90) | [−1,16, −0,81] pp | **Sí**: el barrio es la palanca más fuerte |
| **H2** — el precio del m² cae con la distancia al transporte | Regresión con efectos fijos de barrio y controles, errores agrupados por barrio | Lineal: **no se rechaza** (p = 0,081). Escalón a 1 km: se rechaza (p = 0,002) | −6,7% del m² a más de 1 km de la red | [−10,9, −2,3]% | Poco: afecta al 6% de los avisos |
| **H3** — las unidades a reciclar cotizan con descuento | Van Elteren, celdas barrio × superficie | Se rechaza (p < 0,001), en precio y en rentabilidad | −23,3% del m²; +1,12 pp de bruta | [−26,8, −19,2]%; [+0,74, +1,52] pp | Sí, si la refacción es mínima |
| **H4** — la antigüedad pesa más en venta que en alquiler | Wald sobre dos regresiones con efectos fijos de celda, bootstrap por celdas | Se rechaza (p < 0,001) | −5,7% del m² de venta y −2,6% del alquiler por década: +0,23 pp de bruta por década | +2,4% a +4,3% relativo por década | Poco: menos de 1 pp en 40 años |

**H2 se reformula.** Con los errores agrupados por barrio, la pendiente lineal no es
significativa; con el error común habría salido muy significativa (t = −4,07 contra
−1,42). La versión que los datos sostienen es: *dentro del barrio, la distancia a la red
no cambia el precio del m² hasta 1 km; más allá, el m² vale alrededor de 7% menos.*

**Supuestos verificados.** Los precios tienen cola derecha larga, así que H1 y H3 usan
tests de rangos y H2 y H4 trabajan sobre el logaritmo. Los errores de H2 se agrupan por
barrio y el bootstrap de H4 remuestrea celdas: los avisos de un mismo barrio o celda no
son independientes. H4 usa solo antigüedad observada. Las piezas estadísticas están en
`src/validacion.py` y se verifican contra scipy en `src/test_validacion.py`.

---

## Síntesis de atributos y micro-mercados

El plan de la 2da entrega dejó para esta "PCA/MCA sobre las dummies y clustering de
propiedades". Desarrollo completo en el [notebook 05](notebooks/05_sintesis_atributos.ipynb).

**Los ejes.** PCA sobre las 29 dummies físicas del aviso, y MCA sobre las mismas más tipo,
tramo de superficie, tramo de antigüedad y disposición. Los dos métodos encuentran los
mismos ejes. Con la corrección de Benzécri, tres resumen el 98% de la inercia:

| Eje | Inercia corregida | Qué es | Contra lo que el dataset ya tiene |
|---|---|---|---|
| D1 | 70% | Edificio nuevo con amenities | Correlación 0,95 con `n_amenities` |
| D2 | 21% | Tamaño y categoría | 0,86 con el logaritmo de la superficie |
| D3 | 7% | PH o casa contra departamento clásico | 0,56 con ser PH o casa |

**Los micro-mercados.** k-medias sobre esos tres ejes da cuatro grupos muy estables (ARI
de 0,98 o más en submuestras del 80%), que conviven dentro de casi todos los barrios:

| Micro-mercado | Avisos | m² de venta mediano | Bruta mediana |
|---|---|---|---|
| Departamento estándar: 47 m², edificio viejo, casi sin amenities | 47% | USD 1.907 | 7,2% |
| Torre con amenities: 2 años de antigüedad, casi la mitad a estrenar o en pozo | 19% | USD 2.774 | 6,2% |
| Departamento clásico grande: 92 m², con dependencia y cochera | 18% | USD 2.122 | 6,6% |
| PH y casas: 166 m², con patio | 16% | USD 1.207 | 8,8% |

**El hallazgo, con precios observados.** Contra un departamento estándar del mismo barrio,
tamaño y tipo, la torre con amenities cuesta **33% más por m²** (IC 95% [30, 37]) y se
alquila solo **17% más** (IC 95% [12, 23]): rinde alrededor de 0,9 puntos menos. Se mide
con precios y alquileres publicados, no con la rentabilidad estimada, porque el numerador
de esa rentabilidad sale de un modelo que ya usa estas dummies. Precisa el hallazgo de la
2da entrega: lo que rinde menos es el paquete "edificio nuevo con amenities", no solo la
amenity.

**Por qué no entra al modelo de alquiler.** Se probó con la validación del
[notebook 03](notebooks/03_modelo_alquiler.ipynb). La tabla muestra la peor de las tres
semillas:

| Variante | Mejora de R² sobre el Ridge vigente |
|---|---|
| 3 componentes en lugar de las 14 dummies | −0,0075 |
| Ridge vigente + 3 componentes | +0,0059 |
| Ridge vigente + micro-mercado | +0,0008 |
| Las 29 dummies, como techo | +0,0082 |

Ninguna variante alcanza el 0,01 de `supuestos.MEJORA_MINIMA_R2`, que es el mismo
criterio que dejó afuera a las variables espaciales. Además:

- reemplazar las dummies por componentes pierde R² y la lectura de los coeficientes como
  cuánto paga el mercado por cada característica;
- los ejes y los grupos se arman con variables que el modelo ya tiene.

**Queda como análisis informativo.** No cambia el alquiler estimado, los KPIs ni el
dataset.

---

## Función de decisión

`py src/decision.py` implementa las tres decisiones formuladas en la 2da entrega, con los
criterios que se declararon entonces, y las evalúa. Agrega 14 columnas al dataset
analítico, que son las que usa el tablero. Desarrollo completo en el
[notebook 06](notebooks/06_decision.ipynb).

| Decisión | Criterio | Resultado |
|---|---|---|
| **P1** — ¿comprar? | Neta del escenario pesimista (alquiler del percentil 10) sobre el techo de la banda de retorno (7,60%) | **No, para la propiedad típica.** Pasan 18 de 4.484 (0,4%), y 4 con costos de entrada. Las que pasan cuestan alrededor de 30% menos por m² que su celda: hay que verificar por qué |
| **P2** — ¿cuál? | A sobre B solo si sus bandas de neta no se superponen | **Una lista corta, no un ranking.** El 7,2% de los pares se distingue. 140 propiedades no están dominadas por ninguna; dentro de ellas se desempata por el ancho de la banda |
| **P3** — ¿tradicional o temporal? | El temporal, solo si la ocupación sostenible supera la de equilibrio | **Tradicional.** Equilibrio mediano de 65,5% con gestión tercerizada; autogestionado baja a 51,7% |

**El soporte del modelo, un filtro nuevo.** Sin él, P1 y P2 recomendaban casas de 6 a 10
ambientes con netas de 15% a 27%: el modelo les extrapolaba alquileres de hasta
USD 5.000, con 14 alquileres de casas y 44 de PH observados. Solo entran a las
recomendaciones las propiedades cuya celda tipo × tramo de superficie tiene 30
alquileres observados o más (`supuestos.MIN_ALQ_SOPORTE`). Quedan afuera 714 casas y PH
dentro del presupuesto.

**La evaluación.** En 22 escenarios que mueven un supuesto por vez, más dos extremos:

- **P1 es robusto en la conclusión:** pasan entre 3 y 51 propiedades, y con costos de
  entrada nunca más de 5. La lista sí cambia: con 1 punto de margen por liquidez quedan
  6, y con el piso de la banda en lugar del techo, 33.
- **La frontera de P2 casi no se mueve.** La vacancia y los gastos escalan todas las
  netas por igual y no cambian qué banda domina a cuál; solo el ABL plano la achica a
  92. Los pares distinguibles quedan entre 7% y 8% en todos los escenarios.
- **P3 no cambia de signo** con ninguna vacancia del tradicional.

---

## Decisiones metodológicas

Las que más pesan en los resultados, con dónde se justifican:

| Decisión | Por qué | Dónde |
|---|---|---|
| La accesibilidad es la distancia a la estación más cercana de las tres redes, sin pesos | Un índice ponderado necesitaría frecuencias por estación, que no se pueden unir | [Accesibilidad](#accesibilidad-al-transporte) |
| H2 con efectos fijos de barrio y errores agrupados por barrio | Sin el barrio se mide centralidad; con el error común, la pendiente parecía significativa y no lo es | [H2](#h2-precio-del-m²-y-distancia-a-la-red), notebook 04 |
| El ABL segmentado se calibra a la unidad de referencia | Aísla la redistribución de un cambio de nivel, que se prueba aparte con la VFH en el tope legal | [Costos](#costos-del-propietario-antes-y-después) |
| Los costos de entrada en el piso de cada rango, y la TIR a 5 años como cifra comparable | El efecto que se informa es un mínimo; un costo que se paga una vez no se resta de una renta anual | [Costos](#costos-del-propietario-antes-y-después) |
| Un modelo reemplaza al Ridge solo si mejora el R² en 0,01 en todas las semillas | Criterio declarado antes de comparar. Dejó afuera al boosting, a las variables espaciales y a la síntesis de atributos | [Modelo](#modelo-de-alquiler), notebooks 03 y 05 |
| La banda del KPI 4 es cuantílica y calibrada | La anterior cubría el 50% por construcción | [Banda](#la-banda-del-kpi-4) |
| α = 0,05 fijado antes, y cada test con su efecto en unidades del inversor | Con 9.203 ventas casi todo es significativo | [Hipótesis](#hipótesis-los-tests-formales) |
| Los micro-mercados se comparan con precios observados, no con la rentabilidad estimada | El numerador de la rentabilidad sale de un modelo que ya usa esos atributos | Notebook 05 |
| P1 contra el techo de la banda y con el escenario pesimista; P2 por dominancia de bandas; soporte del modelo | Una compra no se deshace barato, y la banda es la incertidumbre real de cada estimación | [Función de decisión](#función-de-decisión) |
| El informe lo escribe un script | Cada cifra narrada sale del dato y no se desincroniza | `src/reporte.py` |

---

## Limitaciones

- **Precios de publicación, no de cierre**, del lado de la venta y del alquiler.
- **Una sola inmobiliaria**: la cartera de RE/MAX publica alrededor de 8% más barato que
  el mercado y está sesgada en cobertura geográfica (`sesgo.py`). Las rentabilidades
  probablemente están del lado alto.
- **El alquiler es estimado**: cada rentabilidad es una banda, que contiene al 82% de los
  alquileres reales.
- **Casas y PH fuera de las recomendaciones**: hay muy pocos alquileres observados.
- **Sin apreciación, costos de salida ni riesgo legal**: la TIR supone reventa al mismo
  precio en dólares, y el riesgo legal no tiene una fuente que lo cuantifique.
- **Liquidez de toda la Ciudad**: el tiempo de publicación de IDECBA es por cantidad de
  ambientes, no por barrio ni por propiedad.
- **Accesibilidad en línea recta**: no ve barreras, frecuencias ni destinos, y no incluye
  el Premetro.
- **Un corte temporal único**: el relevamiento es de agosto de 2026.

---

## Reproducir

Python 3.13. Desde esta carpeta:

```bash
py -m pip install -r requirements.txt

py src/limpieza.py --tc 1500             # crudo -> dataset limpio + auditoría
py src/variables.py                      # RegEx sobre el texto -> dummies
py src/espacial.py                       # distancias a subte, tren, Metrobús y plazas
py src/kpis.py                           # modelo de alquiler -> KPIs, ABL, costos y TIR
py src/temporal.py                       # P3: tradicional contra temporal
py src/sesgo.py                          # la cartera contra IDECBA y el Censo
py src/accesibilidad.py                  # H2: precio del m2 y distancia a la red
py src/comparacion_modelos.py            # el modelo contra la referencia (el paso más lento)
py src/decision.py                       # P1 a P3 -> columnas de la decisión
py src/reporte.py                        # informe/INFORME_HALLAZGOS.md
py src/test_variables.py                 # motor RegEx, sin red
py src/test_supuestos.py                 # supuestos.py contra el pipeline
py src/test_fuentes.py                   # joins con fuentes externas, sin red
py src/test_eda.py                       # estadística de eda.py, sin datos
py src/test_espacial.py                  # fusión espacial, sin red
py src/test_costos.py                    # ABL, costos de entrada y TIR
py src/test_accesibilidad.py             # método de H2, sobre datos sintéticos
py src/test_modelo.py                    # banda cuantílica y metadata del modelo
py src/test_validacion.py                # piezas de los tests formales, sin datos
py src/test_sintesis.py                  # PCA, MCA y micro-mercados, sin datos
py src/test_decision.py                  # función de decisión
```

Los diez primeros scripts reconstruyen `data/processed/` y el informe a partir de
`data/raw/dataset_maestro.csv`, en ese orden: `temporal.py` usa el ABL que calcula
`kpis.py`, `comparacion_modelos.py` lee la banda del modelo que guarda `kpis.py`,
`decision.py` necesita la salida de `temporal.py`, y `reporte.py` lee todo lo anterior.
La corrida de los diez scripts tarda unos 3 minutos, y reproduce exactamente los valores versionados: en una corrida desde cero solo cambian las fechas de los reportes.

Después, los notebooks, que leen esas salidas:

```bash
cd notebooks
py -m nbconvert --to notebook --execute --inplace 01_accesibilidad.ipynb
py -m nbconvert --to notebook --execute --inplace 02_costos_del_propietario.ipynb
py -m nbconvert --to notebook --execute --inplace 03_modelo_alquiler.ipynb
py -m nbconvert --to notebook --execute --inplace 04_validacion.ipynb   # unos 2 minutos
py -m nbconvert --to notebook --execute --inplace 05_sintesis_atributos.ipynb   # 1 minuto
py -m nbconvert --to notebook --execute --inplace 06_decision.ipynb
```

Los notebooks necesitan `dataset_espacial.csv` (el 03 lee de ahí los alquileres para la
banda), que es intermedio y no se versiona: hay que correr antes el pipeline. Los intermedios (`dataset_limpio.csv`, `dataset_excluidos.csv`,
`dataset_variables.csv`, `dataset_espacial.csv`) no se versionan.

`espacial.py` usa las capas versionadas de `data/external/`, así que corre sin red. Con
`--descargar` vuelve a bajarlas de Buenos Aires Data a `data/external/raw/` (no
versionado; el archivo de espacios verdes pesa 15 MB) y rehace las capas con la fecha
del día.

**Cifras de referencia.** Una corrida correcta da exactamente estas cifras. Si alguna
cambia, cambió el pipeline o una dependencia:

| Cifra | Valor | Respecto de la 2da entrega |
|---|---|---|
| Dataset limpio | 12.097 filas | igual |
| Ventas con estimación confiable | 9.203 | igual |
| Rentabilidad bruta mediana | 7,01% | igual |
| Rentabilidad neta mediana | 5,65% | 5,67% con ABL plano |
| TIR a 5 años mediana | 4,27% | nueva |
| Repago mediano | 171 meses | igual |
| R² del modelo de alquiler (log, fuera de muestra) | 0,848 | igual |
| Error relativo mediano | 11,2% | igual |
| Cobertura de la banda del KPI 4, fuera de muestra | 81,6% | 50,1% con la banda anterior |
| Universo de la decisión | 4.484 propiedades | nueva |
| Pasan P1 (neta pesimista sobre el techo) | 18; 4 con costos de entrada | nueva |
| Frontera de P2 | 140 propiedades; 7,2% de pares distinguibles | nueva |
| `dataset_analitico.csv` | 12.097 × 128 | 98 columnas en la 2da |

---

## Estructura

```
Entrega 3/
├── data/
│   ├── raw/            dataset_maestro.csv, crudo sin modificar
│   ├── processed/      dataset_analitico.csv, reportes, DICCIONARIO_DATOS.md, GUIA_TABLERO.md
│   ├── external/       tablas fechadas de las fuentes externas y capas espaciales
│   └── reference/      ranking de barrios de la 1ra entrega, para comparar
├── informe/            INFORME_HALLAZGOS.md, FUENTES_EXTERNAS.md
├── notebooks/          01 accesibilidad, 02 costos, 03 modelo, 04 validación, 05 síntesis, 06 decisión (en orden de lectura)
├── graficos/           los 15 gráficos que guardan los notebooks
├── src/                pipeline, supuestos y tests
├── requirements.txt
└── README.md
```

La carpeta del tablero se agrega cuando se crea.
