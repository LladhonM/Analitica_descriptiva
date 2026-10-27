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
Sobre esa base ya están hechas:

- la **fusión espacial** y la medida de accesibilidad (ver
  [Accesibilidad al transporte](#accesibilidad-al-transporte));
- la **magnitud y forma de H2** (ver [H2](#h2-precio-del-m²-y-distancia-a-la-red));
- el **ABL segmentado** y los **costos de entrada y refacción**, que cambian el KPI 2 y
  suman la TIR a 5 años (ver [Costos del propietario](#costos-del-propietario-antes-y-después)).

El dataset con estas columnas es la base del tablero. Lo único pendiente que puede
volver a mover sus números es la revisión del modelo de alquiler (fila 7). El resto se
registra en la tabla [Qué se construye en esta entrega](#qué-se-construye-en-esta-entrega).

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
| `src/kpis.py` | Lee `dataset_espacial.csv` (salida de `espacial.py`) en lugar de `dataset_variables.csv`. **El KPI 2 usa el ABL de cada propiedad** (`costos.py`) en lugar de un porcentaje plano; `--gastos` vuelve al plano. Suma costos de entrada, refacción y TIR a 5 años, el antes y el después, y una segunda grilla de sensibilidad (ABL × costos de entrada × vacancia). El modelo de alquiler no cambia. En el docstring, el apartado sobre las dummies de RegEx se atribuye a la 2da entrega |
| `src/modelo_alquiler.py` | Se quitó el `main()`, un punto de entrada heredado de la 1ra entrega que no usaba nadie: aplicaba vacancia 8% y gastos 12% (no los de `supuestos.py`), escribía archivos que el pipeline no usa y pisaba `ranking_barrios.csv`. El docstring deja de citar un error de ~11,5%, que no es el vigente (11,2%). `calcular_rentabilidad` acepta gastos por propiedad. **El ranking de barrios se ordena por neta y no por bruta**, con desempate por nombre: con el ABL segmentado ya no es lo mismo, y el orden ya no cambia entre corridas |
| `src/supuestos.py` | Se quitaron constantes que ningún script ni notebook leía (`TOP_BARRIOS_HEATMAP` y tres `SCATTER_*`); la fecha de consulta y el umbral de completitud pasan a comentario. Nuevas secciones: radio de caminata y tramos de H2 (4b2), ABL segmentado (3b2), costos de entrada (3e), refacción (3f) y riesgo legal como limitación (3g). **Se corrigieron dos errores heredados del ABL**: el ejemplo de ARS 43.994 es con coeficiente geográfico 1,75 y no 1,25, y la fuente no dice que una VFH de 15 a 25 millones sea "el rango de un 2 ambientes usado" |
| `src/eda.py` | Se quitaron un import sin uso (`matplotlib.pyplot`) y un color que no se usaba (`BUENO`) |
| `src/temporal.py` | Se quitó un import sin uso (`numpy`). `lado_remax()` acepta la ruta del dataset como parámetro. La neta tradicional y los fijos del temporal usan el ABL mediano de cada celda en lugar del plano, para que P3 use los mismos gastos que el KPI 2 |
| `src/reporte.py` | Se quitó un import sin uso. **Su texto es el informe de la 2da entrega**: se reescribe con los hallazgos de esta, y hasta entonces no forma parte del pipeline |
| `src/sesgo.py` | Sin cambios |
| `src/fuentes_externas.py` | Sin cambios |
| `src/test_fuentes.py` | Resuelve las rutas desde la ubicación del archivo: antes solo corría desde la raíz de la entrega |
| `src/test_supuestos.py` | Verifica el contrato nuevo del KPI 2 (gastos de cada propiedad = 10,24% + su ABL), la tabla de coeficientes geográficos (48 barrios, entre 0 y 2), la escala del Impuesto Inmobiliario y los rangos de los costos de entrada. Incluye un negativo: con el gasto plano, la neta del dataset no coincide |
| `src/test_variables.py` | Sin cambios |
| `src/test_eda.py` | Sin cambios |

**Datos (`data/`)**

| Archivo | Estado |
|---|---|
| `data/raw/dataset_maestro.csv` | Sin cambios. Es el crudo del scraping de la 1ra entrega (14.867 avisos, 16-08-2026) |
| `data/external/` (7 tablas y `reporte_fuentes.txt`) | Sin cambios. Tablas agregadas y fechadas de IDECBA, Colegio de Escribanos, Inside Airbnb y Censo 2022 |
| `data/reference/` (`ranking_barrios_entrega1.csv`, `LEEME.md`) | Sin cambios |
| `data/processed/` — `auditoria_calidad.csv`, `reporte_limpieza.txt`, `reporte_regex.txt` | **Regenerados en esta carpeta** por `limpieza.py` y `variables.py`. Contenido idéntico al de la 2da entrega; los reportes cambian la fecha de corrida |
| `data/processed/` — `dataset_analitico.csv`, `ranking_barrios.csv`, `modelo_alquiler.joblib`, `sensibilidad_supuestos.csv`, `reporte_kpis.txt` | **Regenerados con contenido nuevo** por `espacial.py` y `kpis.py`. `dataset_analitico.csv` suma 15 columnas (accesibilidad y costos) y su `rent_neta_pct` usa el ABL segmentado; el resto de las columnas heredadas no cambia. El ranking se ordena por neta. La sensibilidad suma la grilla B |
| `data/processed/` — `temporal_vs_tradicional.csv`, `reporte_temporal.txt` | **Regenerados** por `temporal.py`, con el ABL segmentado |
| `data/processed/` — `sesgo_precio_barrio.csv`, `sesgo_representacion_comuna.csv`, `reporte_sesgo.txt` | Sin cambios: copiados, no regenerados. `sesgo.py` no usa la neta |
| `data/processed/DICCIONARIO_DATOS.md` | El encabezado deja de presentar la matriz como "de la 2da pre-entrega". Se agregaron la sección 8.1 (ABL, costos y TIR), la 9 (accesibilidad), los pasos nuevos del linaje, la fórmula nueva de `rent_neta_pct` y tres advertencias de uso |

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
| `src/accesibilidad.py` | H2: pendiente con y sin barrio fijo, perfil por tramos de distancia, radio de influencia y réplica del antecedente del repositorio de trabajo |
| `src/test_accesibilidad.py` | 8 tests de H2, sobre datos sintéticos con la respuesta conocida: el barrio fijo elimina la centralidad pura y el perfil recupera una penalidad plantada |
| `src/costos.py` | Fórmulas del ABL segmentado (Ley 6927), costos de entrada, refacción y TIR a 5 años. Los números están en `supuestos.py` |
| `src/test_costos.py` | 38 tests. El ABL se valida contra un oráculo externo: los siete ejemplos que calcula Roomix con la Ley 6927 |
| `data/processed/h2_perfil_distancia.csv`, `reporte_h2.txt` | Salida de `accesibilidad.py` |
| `data/processed/antes_despues_kpis.csv` | Neta mediana, barrios sobre el piso y top 5, antes y después del ajuste |
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
| 2 | Tests formales de H1 a H4, con p-valor, tamaño del efecto, intervalo y lectura de si cambian la decisión | Devolución, prioridad 2 | Pendiente |
| 3 | Función de decisión prescriptiva para P1 (comprar o no), P2 (qué propiedad) y P3 (tradicional o temporal), **implementada y evaluada** | Devolución, prioridad 3; consigna de la 3ra entrega | Pendiente |
| 4 | ABL segmentado por barrio, superficie y tipo de propiedad, y su efecto sobre la rentabilidad neta | Devolución, prioridad 4 | Hecho (ver [Costos del propietario](#costos-del-propietario-antes-y-después)) |
| 5 | Costos de entrada, refacción, liquidez y riesgo legal, con fuente y fecha en `supuestos.py` | Devolución, prioridad 5 | Hecho: entrada y refacción con fuente; riesgo legal como limitación declarada. La liquidez sigue siendo la del tiempo de publicación de IDECBA (ficha 5 del catálogo) |
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

## H2: precio del m² y distancia a la red

> **H2.** El precio del m² decrece con la distancia al transporte, y existe un radio de
> influencia a partir del cual el beneficio se diluye.

`py src/accesibilidad.py` estima la **magnitud y la forma** de la relación con el método
declarado desde la 1ra entrega: regresión de log(USD/m²) sobre la distancia, **con efectos
fijos de barrio**. Base: 10.743 avisos de venta. El contraste con p-valor va con los
tests formales (fila 2 de la tabla de arriba).

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

| ABL como % del alquiler, por quintil de rentabilidad bruta | Q1 (rinde menos) | Q2 | Q3 | Q4 | Q5 (rinde más) |
|---|---|---|---|---|---|
| Plano (2da entrega) | 3,80% | 3,80% | 3,80% | 3,80% | 3,80% |
| Segmentado | 4,58% | 4,18% | 3,84% | 3,46% | 2,90% |

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

## Reproducir

Python 3.13. Desde esta carpeta:

```bash
py -m pip install -r requirements.txt

py src/limpieza.py --tc 1500             # crudo -> dataset limpio + auditoría
py src/variables.py                      # RegEx sobre el texto -> dummies
py src/espacial.py                       # distancias a subte, tren, Metrobús y plazas
py src/kpis.py                           # modelo de alquiler -> KPIs, ABL, costos y TIR
py src/temporal.py                       # P3: tradicional contra temporal
py src/accesibilidad.py                  # H2: precio del m2 y distancia a la red
py src/test_variables.py                 # motor RegEx, sin red
py src/test_supuestos.py                 # supuestos.py contra el pipeline
py src/test_fuentes.py                   # joins con fuentes externas, sin red
py src/test_eda.py                       # estadística de eda.py, sin datos
py src/test_espacial.py                  # fusión espacial, sin red
py src/test_costos.py                    # ABL, costos de entrada y TIR
py src/test_accesibilidad.py             # método de H2, sobre datos sintéticos
```

Los seis primeros scripts reconstruyen `data/processed/` a partir de
`data/raw/dataset_maestro.csv`, en ese orden: `temporal.py` usa el ABL que calcula
`kpis.py`. Los intermedios (`dataset_limpio.csv`, `dataset_excluidos.csv`,
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
| `dataset_analitico.csv` | 12.097 × 113 | 98 columnas en la 2da |

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
