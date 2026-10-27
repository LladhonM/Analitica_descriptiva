# Catálogo de fuentes externas

**TP Integrador · 82.04 Analítica Descriptiva (ITBA) · Grupo 2 · 3ra pre-entrega**

El análisis de las entregas anteriores dependía de una sola fuente: la cartera de avisos de
RE/MAX. Este catálogo documenta las fuentes que se sumaron para leerla contra el mercado
y las que quedan planificadas. Cada una se describe con los mismos campos: qué variable
aporta, cobertura geográfica, período, granularidad, cómo se une con RE/MAX, qué pregunta,
KPI o hipótesis ayuda a analizar, y sus limitaciones.

Las fichas 1 a 5 vienen de la 2da entrega. Esta entrega agrega las capas espaciales
(fichas 6 a 9), que en la 2da figuraban como planificadas.

Las fuentes 1 a 5 se leen con `py src/fuentes_externas.py`, y las capas espaciales, con
`py src/espacial.py`. Los dos scripts dejan tablas fechadas en `data/external/`. Los
archivos crudos no se versionan (`data/external/raw/` está en `.gitignore`): se vuelven a
bajar con el script. El agregado versionado congela la evidencia, porque algunas fuentes
reemplazan sus archivos (Inside Airbnb, cada trimestre). Las fuentes 1 a 5 se unen por
nombre de barrio, por comuna o a nivel ciudad; las 6 a 9, por coordenadas.

| # | Fuente | Estado | Se une por | Responde a |
|---|---|---|---|---|
| 1 | Estadística Ciudad: precio publicado del m² | Integrada | barrio × ambientes × estado | Sesgo de precio de RE/MAX |
| 2 | Colegio de Escribanos: escrituras | Integrada | nivel ciudad, por mes | Precio de cierre, liquidez, crédito |
| 3 | Inside Airbnb | Integrada | barrio × dormitorios | P3: tradicional o temporal |
| 4 | Censo 2022: departamentos por comuna | Integrada | comuna | Sesgo de representación |
| 5 | Estadística Ciudad: tiempo medio de publicación | Integrada | ambientes, nivel ciudad | Liquidez (P1, P2) |
| 6 | BA Data: bocas de subte | Integrada | coordenadas (más cercana) | H2, accesibilidad |
| 7 | BA Data: estaciones de ferrocarril | Integrada | coordenadas (más cercana) | H2, accesibilidad |
| 8 | BA Data: estaciones de Metrobús | Integrada | coordenadas (más cercana) | H2, accesibilidad |
| 9 | BA Data: espacios verdes públicos | Integrada | coordenadas (borde más cercano) | Revisión del modelo de alquiler |
| 10 | IPC del INDEC | Planificada | nivel país, por mes | Lectura en términos reales |

---

## Fuentes integradas

### 1. Estadística Ciudad (IDECBA): precio promedio de publicación del m²

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Precio promedio de publicación del m², en dólares, de departamentos en venta (`usd_m2`) |
| **Cobertura geográfica** | Los 48 barrios de CABA, más el total de la Ciudad |
| **Período** | Serie trimestral desde el 4to trimestre de 2006 (1 ambiente, desde 2017) hasta el 2do trimestre de 2026. Se conservan los últimos 8 trimestres, del 3ro de 2024 al 2do de 2026 |
| **Granularidad** | Barrio × ambientes (1, 2, 3) × estado (usado, a estrenar) × trimestre. Seis cuadros, uno por combinación de ambientes y estado |
| **Cómo se une con RE/MAX** | Por `barrio`, `ambientes` y estado (`es_a_estrenar`), fijando un trimestre. Promedio contra promedio, porque IDECBA publica promedios |
| **Qué ayuda a analizar** | El **sesgo de precio de la cartera de RE/MAX**: si publica más caro o más barato que el mercado en la misma celda. Afecta directamente al KPI 1, que tiene el precio en el denominador |
| **Limitaciones** | Son precios **de publicación**, no de cierre, igual que los de RE/MAX: la comparación es publicado contra publicado. La base es Argenprop desde julio de 2015, así que es otro portal, no el mercado entero. IDECBA suprime las celdas con pocos avisos: en el último trimestre hay dato para entre 18 y 45 barrios según la combinación. Hay un trimestre de desfase con el scraping (agosto de 2026) |
| **Archivo** | `data/external/estadistica_ciudad_m2_barrio.csv` |
| **Fuente** | [IDECBA, banco de datos, mercado inmobiliario](https://www.estadisticaciudad.gob.ar/eyc/categoria-banco-datos/mercado-inmobiliario/), cuadros `MI_DVP_AX01` a `AX04`, `AX09` y `AX10` |

### 2. Colegio de Escribanos de la Ciudad de Buenos Aires: escrituras

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Cantidad de escrituras de compraventa, cantidad con hipoteca, porcentaje con hipoteca y, para 2026, monto promedio en dólares |
| **Cobertura geográfica** | Toda la Ciudad, sin apertura por barrio |
| **Período** | Mensual, de enero de 2002 a diciembre de 2025 (cuadro de IDECBA) más julio y agosto de 2026 (informes mensuales del Colegio) |
| **Granularidad** | Ciudad × mes |
| **Cómo se une con RE/MAX** | No se une fila a fila. Es un **ancla agregada**: el monto promedio escriturado se compara con el precio promedio de la cartera, y el volumen mensual describe la liquidez del mercado en el que se va a revender |
| **Qué ayuda a analizar** | La diferencia entre **precio publicado y precio de cierre** (contexto argentino, punto 4 del README de la 2da entrega), el **predominio del contado** (en 2025, 19,1% de las compraventas tuvo hipoteca) y la **liquidez** del mercado de salida (restricción de P1) |
| **Limitaciones** | Incluye todas las compraventas de la Ciudad (cualquier tipo de inmueble), no solo departamentos residenciales, así que el monto promedio no es comparable uno a uno con la cartera. Sin apertura por barrio. **El cuadro de IDECBA trae 2026 con valores inconsistentes**: julio de 2026 figura con 1.159 compraventas y el Colegio informa 6.051 (acumulado enero-julio: 6.771 contra 35.528). Hasta 2025 coinciden (agosto de 2025: 6.372 contra 6.370). Por eso se usa el cuadro solo hasta 2025, y 2026 sale de los informes del Colegio, cargados con su URL. Solo hay monto en dólares para los meses de 2026 |
| **Archivo** | `data/external/colegio_escribanos_mensual.csv` |
| **Fuente** | [IDECBA, actos notariales de compraventa e hipotecas](https://www.estadisticaciudad.gob.ar/eyc/banco-datos/actos-notariales-de-compraventa-de-inmuebles-e-hipotecas-anotados-en-el-colegio-de-escribanos-ciudad-de-buenos-aires-enero-de-2002-junio-de-2025/); Colegio de Escribanos, informes de [julio](https://www.colegio-escribanos.org.ar/2026/08/24/cantidad-de-escrituras-de-compraventa-realizadas-en-julio-2026/) y [agosto de 2026](https://www.colegio-escribanos.org.ar/2026/09/22/cantidad-de-escrituras-de-compraventa-realizadas-en-agosto-2026/) |

### 3. Inside Airbnb: Buenos Aires

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Tarifa por noche (ADR), ocupación estimada, ingreso anual estimado y cantidad de avisos activos, por barrio y por dormitorios |
| **Cobertura geográfica** | CABA. 46 de los 48 barrios tienen avisos activos; Versalles no tiene ninguno |
| **Período** | Snapshot del 29-06-2026. Ocupación e ingreso de los últimos 12 meses |
| **Granularidad** | En origen, un aviso por fila (29.685). Agregado a barrio y a barrio × dormitorios (0-1, 2, 3+), solo unidades enteras con al menos una reseña en los últimos 12 meses (20.895) |
| **Cómo se une con RE/MAX** | Por `barrio` y grupo de dormitorios, contra los departamentos en venta de la cartera. Los barrios de Airbnb (`neighbourhood_cleansed`) usan los nombres oficiales y se normalizan sin pérdidas |
| **Qué ayuda a analizar** | **P3**: la alternativa de explotar la unidad por noche en vez de con contrato. Se compara neta contra neta en `temporal.py`, con los costos del temporal declarados en `supuestos.py` |
| **Limitaciones** | **La ocupación es una estimación, no un dato observado**: Inside Airbnb la infiere de las reseñas. Su mediana (21,4% en la Ciudad) queda muy por debajo del 53% que informa la prensa (La Nación, 29-05-2025). Por eso la comparación informa la **ocupación de equilibrio** y no una rentabilidad puntual. Los precios están en pesos y se convierten con el mismo tipo de cambio del pipeline (ARS 1.500). Inside Airbnb reemplaza sus archivos cada trimestre, y el snapshot usado puede dejar de estar disponible |
| **Archivos** | `data/external/airbnb_barrio.csv`, `data/external/airbnb_barrio_dormitorios.csv` |
| **Fuente** | [Inside Airbnb, get the data](https://insideairbnb.com/get-the-data/) |

### 4. Censo 2022: viviendas particulares habitadas por tipo, según comuna

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Cantidad de departamentos habitados por comuna (1.025.296 en la Ciudad) y su peso sobre el total |
| **Cobertura geográfica** | Las 15 comunas de CABA |
| **Período** | Censo Nacional de Población, Hogares y Viviendas 2022 |
| **Granularidad** | Comuna. Es el nivel más fino con un universo completo publicado: IDECBA no publica oferta ni stock actual por barrio |
| **Cómo se une con RE/MAX** | Por `comuna`, contra la distribución de los departamentos de la cartera |
| **Qué ayuda a analizar** | El **sesgo de representación**: qué zonas pesan en la cartera más o menos de lo que pesan en la Ciudad |
| **Limitaciones** | Es stock censado, no oferta: una comuna puede tener mucho stock y poca rotación. El índice mide composición, no error. Es de 2022 |
| **Archivo** | `data/external/censo_departamentos_comuna.csv` |
| **Fuente** | [IDECBA, viviendas particulares habitadas por tipo de vivienda según comuna](https://www.estadisticaciudad.gob.ar/eyc/banco-datos/viviendas-particulares-habitadas-hogares-y-poblacion-censada-por-tipo-de-vivienda-segun-comuna-ciudad-de-buenos-aires-ano-2010/), sobre datos del INDEC |

### 5. Estadística Ciudad: tiempo medio de publicación de departamentos en venta

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Días promedio que un departamento en venta permanece publicado |
| **Cobertura geográfica** | Toda la Ciudad |
| **Período** | Trimestral, del 4to trimestre de 2013 al 2do trimestre de 2026 |
| **Granularidad** | Ambientes × trimestre, sin apertura por barrio |
| **Cómo se une con RE/MAX** | Por `ambientes`, a nivel ciudad |
| **Qué ayuda a analizar** | La **liquidez**, que es una restricción de P1 y P2: cuánto tardaría el inversor en vender su unidad. En el 2do trimestre de 2026, el promedio fue de 298 días publicado |
| **Limitaciones** | El tiempo publicado no es tiempo de venta: un aviso puede bajarse sin venderse. Sin barrio, y sin forma de medirlo por propiedad con un scraping de un solo día |
| **Archivo** | `data/external/estadistica_ciudad_tiempo_publicacion.csv` |
| **Fuente** | [IDECBA, cuadro `MI_DVT`](https://www.estadisticaciudad.gob.ar/eyc/banco-datos/tiempo-medio-de-publicacion-dias-de-departamentos-en-venta-por-cantidad-de-ambientes-ciudad-de-buenos-aires-4to-trimestre-de-2013-2do-trimestre-de-2024/) |

### 6. Buenos Aires Data: bocas de subte

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Distancia del aviso a la boca de subte más cercana (`dist_subte_m`) |
| **Cobertura geográfica** | CABA: 379 bocas de las líneas A, B, C, D, E y H. **No incluye el Premetro** |
| **Período** | Capa vigente, actualizada en el portal el 13-09-2019 y descargada el 27-10-2026. Se controla contra la capa de estaciones de subte (actualizada el 30-12-2024): las 90 estaciones vigentes tienen una boca a 91 m o menos, así que la capa de 2019 cubre la red actual |
| **Granularidad** | Punto: una boca de acceso. Se mide contra la boca y no contra el centro de la estación, porque es por donde se entra |
| **Cómo se une con RE/MAX** | Por coordenadas (`latitud`, `longitud`): para cada aviso, la boca más cercana, con BallTree y métrica haversine. No hay join por clave, así que no puede multiplicar filas |
| **Qué ayuda a analizar** | **H2** (el precio del m² decrece con la distancia al transporte) y la accesibilidad como atributo de cada propiedad en **P2** |
| **Limitaciones** | Sin el Premetro (línea P, en Villa Soldati y Villa Lugano), la distancia al subte queda sobrestimada justo en el sur, donde la red es más escasa. No informa frecuencia. Las de la sección [Accesibilidad](#accesibilidad-qué-mide-la-distancia-y-qué-no) valen para las fichas 6 a 9 |
| **Archivo** | `data/external/transporte_estaciones.csv` (`capa` = `subte_bocas`; las estaciones de control, `subte_estaciones`) |
| **Fuente** | Buenos Aires Data (GCBA), [bocas de subte](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/sbase/bocas-de-subte/bocas-de-subte.csv) y [estaciones de subte](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/sbase/subte-estaciones/estaciones-de-subte.csv) |

### 7. Buenos Aires Data: estaciones de ferrocarril

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Distancia del aviso a la estación de tren más cercana (`dist_tren_m`) |
| **Cobertura geográfica** | CABA y conurbano: 301 estaciones de 8 líneas (Roca, Mitre, Sarmiento, Urquiza, Belgrano Sur, Belgrano Norte, San Martín y Tren de la Costa), 234 de ellas fuera de la Ciudad. Las del conurbano se conservan a propósito: un aviso junto a la General Paz puede tener su estación más cercana del otro lado |
| **Período** | Capa vigente, actualizada en el portal el 01-10-2026 y descargada el 27-10-2026 |
| **Granularidad** | Punto: una estación |
| **Cómo se une con RE/MAX** | Igual que la ficha 6 |
| **Qué ayuda a analizar** | H2 y accesibilidad. Cubre el oeste, donde el subte casi no llega: en las comunas 9, 10 y 11, a lo sumo el 6,5% de los avisos tiene subte a menos de 800 m, y entre el 18,2% y el 47,5% tiene tren |
| **Limitaciones** | Es la capa con más diferencia de frecuencia entre líneas, y no la informa: una estación con un tren por hora vale en la medida lo mismo que una con un tren cada diez minutos. Tampoco informa si la estación tiene servicio regular |
| **Archivo** | `data/external/transporte_estaciones.csv` (`capa` = `tren`) |
| **Fuente** | Buenos Aires Data (GCBA), [estaciones de ferrocarril](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/transporte-y-obras-publicas/estaciones-ferrocarril/estaciones_ferroviarias.csv) |

### 8. Buenos Aires Data: estaciones de Metrobús

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Distancia del aviso a la parada de Metrobús más cercana (`dist_metrobus_m`) |
| **Cobertura geográfica** | CABA: 390 paradas (una por sentido) con 139 nombres de estación, sobre 20 avenidas |
| **Período** | Capa actualizada en el portal el 08-08-2024 y descargada el 27-10-2026. El portal conserva versiones anteriores del mismo archivo en otras rutas (2019 y 2020, con 231 paradas); se usa la vigente |
| **Granularidad** | Punto: una parada en un sentido. La capa no trae el nombre del corredor: lo identifica la avenida |
| **Cómo se une con RE/MAX** | Igual que la ficha 6 |
| **Qué ayuda a analizar** | H2 y accesibilidad. Es la red más extendida en el sur: en la comuna 8 ningún aviso tiene subte a menos de 800 m, y el 55,8% tiene Metrobús |
| **Limitaciones** | Es colectivo con carril exclusivo, no transporte guiado: más lento que el subte y con frecuencia que depende de cada línea. Cada parada sirve a líneas con destinos distintos, y la medida no mira hacia dónde van. Los colectivos comunes quedan fuera por diseño: la medida es de redes con vía o carril propio |
| **Licencia** | CC-BY-2.5-AR |
| **Archivo** | `data/external/transporte_estaciones.csv` (`capa` = `metrobus`) |
| **Fuente** | Buenos Aires Data (GCBA), [Metrobús](https://data.buenosaires.gob.ar/dataset/metrobus); archivo [estaciones-de-metrobus.csv](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/transporte-y-obras-publicas/metrobus/estaciones-de-metrobus.csv) |

### 9. Buenos Aires Data: espacios verdes públicos

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Distancia al borde de la plaza o parque más cercano (`dist_plaza_m`) y del parque de 1 hectárea o más más cercano (`dist_parque_m`) |
| **Cobertura geográfica** | CABA. De los 2.176 polígonos de la capa se conservan 608: se excluyen los canteros centrales (con ellos casi todo aviso queda cerca de un "espacio verde" y la variable no discrimina) y los espacios de menos de 1.000 m². 136 son parques de 1 hectárea o más |
| **Período** | Capa actualizada en el portal el 06-07-2026 y descargada el 27-10-2026 |
| **Granularidad** | Polígono. La distancia se mide contra sus vértices, que aproximan el borde: medir contra el centroide dejaría a cientos de metros un inmueble pegado a un parque grande. Los vértices se versionan en una grilla de 4 decimales (unos 11 × 9 m), con un error menor a 7 m sobre la distancia |
| **Cómo se une con RE/MAX** | Por coordenadas: para cada aviso, el vértice más cercano de la capa filtrada |
| **Qué ayuda a analizar** | No forma parte de H2. Es una predictora candidata para la revisión del modelo de alquiler |
| **Limitaciones** | Mide cercanía, no calidad ni seguridad del espacio. Un parque con rejas se entra por sus puertas, no por cualquier punto del borde. El umbral de 1.000 m² es una decisión de este trabajo, no una categoría oficial |
| **Archivos** | `data/external/espacios_verdes.csv` (un polígono por fila, con nombre, clasificación y área) y `data/external/espacios_verdes_vertices.csv` |
| **Fuente** | Buenos Aires Data (GCBA), [espacios verdes públicos](https://cdn.buenosaires.gob.ar/datosabiertos/datasets/secretaria-de-desarrollo-urbano/espacios-verdes/espacio_verde_publico.csv) |

---

## Accesibilidad: qué mide la distancia y qué no

**La medida.** `dist_transporte_m` es la distancia, en metros, a la estación más cercana
de cualquiera de las tres redes masivas de la Ciudad: subte, tren o Metrobús. Es el
mínimo de las tres, sin pesos. El subte solo no describe la accesibilidad de CABA: en
las comunas 8 y 11 ningún aviso de la cartera tiene una boca de subte a menos de 800 m,
y con las tres redes, el 72,1% y el 75,3% tiene una estación a esa distancia.

**Por qué el mínimo y no un índice.** Lo que un inquilino paga todos los días es la
caminata hasta la red, y una vez adentro cualquiera de las tres lo conecta con el resto
de la Ciudad. Un índice ponderado exigiría pesar cada modo por su frecuencia, y no hay
un dato de frecuencia por estación que se pueda unir: los pesos serían inventados.
Contar cuántos modos hay cerca tampoco sirve: un conteo no es una tasa, y tener tres
redes a 300 m no da el triple de acceso que tener una.

**El límite, declarado.** Es una distancia en línea recta, no accesibilidad real:

- **No ve barreras.** Un aviso a 400 m de una estación en línea recta puede estar a
  1.500 m caminando si en el medio hay vías, una autopista o el Riachuelo.
- **No ve la frecuencia.** Una estación de tren con un tren por hora no equivale a un
  subte cada cuatro minutos, y en la medida valen lo mismo.
- **No ve el destino.** Estar cerca de una estación no dice adónde se llega desde ella
  ni en cuánto tiempo.
- **Le falta el Premetro**, que sirve a Villa Soldati y Villa Lugano: en el sur, la
  medida exagera la distancia a la red.

Por eso la medida es una **cota inferior del esfuerzo de llegar a la red**, no una medida
de qué tan bien conectado está un inmueble. Una medida de tiempo de viaje requeriría
la red de calles y los horarios de cada servicio, que este trabajo no integra.

**Nivel territorial.** La medida es por aviso, no por barrio. En 20 de los 44 barrios
con al menos 30 avisos conviven avisos a menos y a más de 800 m de la red: un promedio
barrial les asignaría a todos el mismo acceso. En Mataderos, por ejemplo, el 10% más
cercano está a 461 m y el 10% más lejano, a 2.358 m.

**Cobertura del dato.** 7 de los 12.097 avisos (0,06%) no tienen coordenadas y quedan sin
distancia. No se concentran en el sur: hay 1 en Villa Lugano (comuna 8), 2 en la
comuna 10 (Floresta y Villa Real) y 4 en Palermo. Como tasa, el máximo es 0,51% en la
comuna 8, que equivale a un aviso de 198. No sesgan la medida.

---

## El sesgo de usar una sola fuente, cuantificado

`py src/sesgo.py` mide las dos dimensiones que se pueden contrastar con fuentes oficiales.
Resultados completos en `data/processed/reporte_sesgo.txt`.

**Precio.** La cartera de RE/MAX publica **más barato** que el promedio de Argenprop en
127 de las 135 celdas de barrio × ambientes × estado con datos suficientes. En el total de
la Ciudad, el desvío es de −5,2% a −8,5% en usados y de −13,5% a −16,3% a estrenar. El
desfase de un trimestre entre las fuentes no lo explica: IDECBA varió como máximo 0,8%
entre el 1er y el 2do trimestre de 2026.

*Consecuencia para los KPIs.* El precio está en el denominador de la rentabilidad, así
que la de la cartera sale **más alta** que la que daría el precio publicado promedio del
mercado. El alquiler estimado también sale de avisos de RE/MAX, y no hay fuente oficial
para medir si su cartera de alquileres tiene el mismo sesgo. Por lo tanto, el efecto neto
sobre el KPI no se puede firmar.

**Representación.** Respecto del stock de departamentos del Censo 2022, la cartera de
ventas sobrerrepresenta la comuna 1 (índice 1,28) y subrepresenta las comunas 4, 8 y 9
(índices de 0,47 a 0,68), que están en el sur y el oeste. Para replicar la composición del
censo habría que reasignar el 7,2% de las ventas a otras comunas. En alquileres el sesgo
es mayor: la comuna 14 (Palermo) tiene un índice de 1,68 y la 8, de 0,11.

*Consecuencia para generalizar.* Los promedios de ciudad del trabajo pesan de más a las
comunas sobrerrepresentadas. Por eso los KPIs se leen por barrio y no como un número del
mercado de CABA.

---

## Fuentes planificadas

### 10. IPC del INDEC

| Campo | Detalle |
|---|---|
| **Variable que aporta** | Variación mensual e interanual de precios al consumidor, incluido el componente de alquiler de la vivienda |
| **Cobertura geográfica** | Nacional y por región (GBA) |
| **Período** | Mensual |
| **Granularidad** | Región × mes × división |
| **Cómo se une con RE/MAX** | Por mes, a nivel agregado |
| **Qué ayuda a analizar** | La lectura en términos reales de un alquiler en pesos contra un precio en dólares (contexto argentino, punto 1 del README de la 2da entrega) |
| **Limitaciones** | Mide precios al consumidor, no el precio de los inmuebles. No tiene apertura por barrio |
| **Fuente** | INDEC, informe técnico del IPC ([agosto de 2026](https://www.indec.gob.ar/uploads/informesdeprensa/ipc_09_26A1BE2DC4CD.pdf)) |
