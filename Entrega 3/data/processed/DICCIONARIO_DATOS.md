# Diccionario de datos — `dataset_analitico.csv`

Matriz final del pipeline: **12.097 filas × 98 columnas**, una fila por aviso
residencial de RE/MAX en CABA (10.749 en venta y 1.348 en alquiler), con las variables
curadas, las extraídas del texto y los cuatro KPIs materializados. Es la que construyó
la 2da pre-entrega, sin cambios: las columnas que agregue esta entrega se documentan acá
cuando entren al pipeline.

| Atributo | Valor |
|---|---|
| Grano | Un aviso publicado (`id_aviso` es clave única) |
| Fuente primaria | API JSON pública de RE/MAX Argentina (listado `findAll` y ficha `findBySlug`), scrapeada en la 1ra entrega |
| Fecha de captura | 16 de agosto de 2026, hora argentina (`fecha_scraping` está en UTC y cruza al 17) |
| Origen en disco | `data/raw/dataset_maestro.csv` (14.867 avisos × 55 columnas) |
| Generado por | `src/limpieza.py --tc 1500` → `src/variables.py` → `src/kpis.py` |
| Codificación | CSV UTF-8 con BOM (`utf-8-sig`), separador coma, decimal punto |
| Tipo de cambio | **ARS 1.500 por USD**, fijo para todo el dataset (el implícito en los alquileres publicados es 1.110) |

---

## Cómo leer este diccionario

- **Tipo**: tipo lógico de la variable. Los conteos que pasaron por imputación o
  redondeo (`ambientes`, `dormitorios`) y las binarias con nulos (`es_a_estrenar`) se
  guardan como decimal en el CSV, aunque su valor sea entero.
- **Fuente**: de dónde sale el dato.
  - *RE/MAX* es un campo de la API, con su nombre original entre comillas invertidas.
  - *Derivada* indica el script que la calcula.
- **Transformaciones**: todo lo que se le hizo al dato desde el crudo. Los pasos de
  limpieza se citan como `limpieza P1` a `limpieza P9`.
- **Tres clases de nulo**, según `auditoria_calidad.csv`:
  - *Estructural*: la celda no aplica a esa fila. Por ejemplo, `venta_usd` en un
    alquiler. **No se imputa nunca.**
  - *Informativo*: la ausencia es en sí misma un dato, y se convierte en una dummy.
  - *Faltante*: el dato existe pero el portal no lo publicó. Solo estos se imputan, y
    cada imputación queda marcada en una columna `<variable>_imputada`.

### Linaje

```
dataset_maestro.csv  (14.867 × 55)
  │ limpieza.py   P1 correcciones · P2 solo vivienda · P3 duplicados · P4 imposibles
  │               P5 monedas · P6 outliers · P7 derivadas · P8 columnas · P9 nulos
  │               → 2.770 filas excluidas, con motivo, en dataset_excluidos.csv
  │ variables.py  RegEx sobre título + descripción + detalles → 35 dummies + 5 de estructura
  │ kpis.py       modelo Ridge de alquiler → 4 KPIs
  ▼
dataset_analitico.csv  (12.097 × 98)
```

---

## 1. Identificación y tipología

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `id_aviso` | Identificador único del aviso | Texto (UUID) | — | RE/MAX `id` (o `internalId`) | Deduplicación por `id_aviso` y por `url` (P3); se conserva la captura más reciente |
| `url` | Enlace público al aviso | Texto | — | RE/MAX `slug` → `https://www.remax.com.ar/listings/{slug}` | Deduplicación (P3) |
| `fecha_scraping` | Momento de la captura | Fecha-hora ISO 8601, UTC | — | Scraper (reloj local al guardar) | Ordena la deduplicación |
| `operacion` | Tipo de operación publicada | Categórica: `venta`, `alquiler` | — | RE/MAX `operation.value` (`sale` / `rent`), filtrado del lado del cliente | 1 aviso corregido de venta a alquiler por título y monto (P1) |
| `tipo_propiedad` | Tipología detallada del inmueble | Categórica, 12 niveles | — | RE/MAX `type.value` | Solo se conservan departamentos, PH y casas (P2); cocheras, oficinas, locales, terrenos y demás se excluyen |
| `tipo_familia` | Tipología agrupada | Categórica: `departamento` (9.948), `ph` (1.452), `casa` (697) | — | Derivada, `limpieza P7` | Prefijo de `tipo_propiedad` |

## 2. Precio y expensas

Las columnas `venta_*` y `alquiler_*` tienen la unidad en el nombre y **solo se llenan
para su operación**: el nulo de la otra es estructural.

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `precio_valor` | Precio publicado, en la moneda original | Decimal | ARS o USD; total en venta, mensual en alquiler | RE/MAX `price` | Se excluyen nulos y valores ≤ 0 (P4). Sin conversión |
| `precio_moneda` | Moneda del precio publicado | Categórica: `USD` (10.997), `ARS` (1.100) | — | RE/MAX `currency.value` | 5 alquileres corregidos de USD a ARS: su monto solo es coherente en pesos (P1) |
| `precio_m2` | `precio_valor / sup_total_m2` | Decimal | **Mezcla ARS/m², USD/m² y USD/m²/mes** | Derivada, scraper | Recalculada en P5. ⚠ No agregar: usar `venta_m2_usd` o `alquiler_m2_usd_mes` |
| `precio_usd` | Precio unificado en dólares | Decimal | USD (venta) o USD/mes (alquiler) | Derivada, `limpieza P5` | ARS ÷ 1.500 |
| `venta_usd` | Precio de venta | Decimal | USD | Derivada, `limpieza P5` | `precio_usd` de las ventas. Nulo estructural en alquileres |
| `alquiler_usd_mes` | Alquiler mensual publicado | Decimal | USD/mes | Derivada, `limpieza P5` | `precio_usd` de los alquileres. Nulo estructural en ventas. Es la variable objetivo del modelo de alquiler |
| `venta_m2_usd` | Precio de venta por m² | Decimal | USD/m² | Derivada, `limpieza P5` | `venta_usd / sup_total_m2`. Recorte de percentiles 1 y 99 (P6): rango válido 546,51 a 4.583,63, con 220 filas excluidas |
| `alquiler_m2_usd_mes` | Alquiler mensual por m² | Decimal | USD/m²/mes | Derivada, `limpieza P5` | `alquiler_usd_mes / sup_total_m2`. Recorte de percentiles 1 y 99 (P6): rango válido 5,71 a 28,16, con 28 filas excluidas |
| `expensas_valor` | Expensas mensuales, en la moneda original | Decimal | ARS o USD por mes | RE/MAX `expensesPrice` | Anuladas si superan 15 USD/m²/mes, por error de carga (P5). **No se imputa**: 321 nulos (2,7%). El 0 es un valor real: casas y PH sin consorcio |
| `expensas_moneda` | Moneda de las expensas | Categórica: `ARS` (12.078), `USD` (18) | — | RE/MAX `expensesCurrency.value` | Si falta y hay monto, se asume ARS (scraper) |
| `expensas_usd` | Expensas mensuales en dólares | Decimal | USD/mes | Derivada, `limpieza P5` | ARS ÷ 1.500; mismo tope de 15 USD/m²/mes. Imputada en P9 con la mediana de barrio × `tipo_familia` × `superficie_rango`, o la global si el grupo está vacío. Ver `expensas_usd_imputada` |
| `expensas_sobre_alquiler` | Peso de las expensas sobre el alquiler | Decimal | Proporción (0 a 2) | Derivada, `limpieza P7` | `expensas_usd / alquiler_usd_mes`; valores mayores a 2 → nulo. Solo definida en alquileres. Su mediana (0,213) alimenta un supuesto de `supuestos.py` |

## 3. Ubicación

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `direccion` | Dirección publicada (calle y altura redondeada) | Texto | — | RE/MAX `displayAddress` | Limpieza de espacios. Integra la clave de duplicado del mismo inmueble (P3) |
| `calle` | Nombre de la calle, sin altura | Texto | — | Derivada, scraper (`parse_address`) | Se descartaron `altura` (redondeada a la cuadra) y `piso` (0,3% de completitud) en P8 |
| `barrio` | Barrio oficial de CABA, en minúsculas y sin tildes | Categórica, 48 niveles | — | Derivada, scraper (`normalizar_barrio`) | Mapea `barrio_raw` o la dirección a los 48 barrios oficiales mediante alias; si no resuelve, usa la ficha (`geo.citie`) |
| `barrio_raw` | Ubicación tal como la publica RE/MAX | Texto, 75 valores | — | RE/MAX `addressInfo` (primer segmento) | Ninguna; conserva sub-barrios comerciales |
| `comuna` | Comuna de CABA | Entero, 1 a 15 | — | Derivada, scraper (`comuna_de_barrio`) | Tabla fija barrio → comuna |
| `latitud` | Latitud del inmueble | Decimal | Grados, WGS84 | RE/MAX `location.coordinates` (GeoJSON `[lon, lat]`) | Anulada si cae fuera de −35,1 a −34,4 (scraper). **No se imputa** (7 nulos): una coordenada inventada cambia el barrio |
| `longitud` | Longitud del inmueble | Decimal | Grados, WGS84 | Ídem `latitud` | Ídem `latitud` |

## 4. Características físicas

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `sup_total_m2` | Superficie total | Decimal | m² | RE/MAX `dimensionTotalBuilt` (o `dimensionLand` si falta) | Excluidos nulos, < 10 m² y > 2.000 m² (P4); 1 superficie anulada por inconsistente (P1). Rango final: 13,4 a 1.100 |
| `sup_cubierta_m2` | Superficie cubierta | Decimal | m² | RE/MAX `dimensionCovered` | Ninguna, salvo la anulación de P1 |
| `ratio_cubierta` | Proporción cubierta de la superficie total | Decimal | Proporción (0 a 1) | Derivada, `limpieza P7` | `sup_cubierta_m2 / sup_total_m2`; nulo si es ≤ 0 o > 1,05 (7 nulos) |
| `superficie_rango` | Tramo de superficie total | Categórica ordinal: `hasta 35`, `36-55`, `56-80`, `81-120`, `120+` | m² | Derivada, `limpieza P7` | Cortes en 35, 55, 80 y 120. **No** son los tramos de `error_estimacion` |
| `log_sup` | Logaritmo natural de la superficie total | Decimal | ln(m²) | Derivada, `kpis.py` (`modelo_alquiler.preparar`) | `ln(sup_total_m2)`. Predictora del modelo de alquiler |
| `ambientes` | Cantidad de ambientes | Entero | Conteo | RE/MAX `totalRooms` | Valores > 15 → nulo (P4); 4 imputados con la mediana de `superficie_rango` y redondeados (P9) |
| `dormitorios` | Cantidad de dormitorios (0 = monoambiente) | Entero | Conteo | Ficha RE/MAX `bedrooms` | Valores > 12 → nulo (P4); 1 imputado con la mediana de `superficie_rango` y redondeado (P9) |
| `banos` | Cantidad de baños | Entero | Conteo | RE/MAX `bathrooms` | Ninguna |
| `cocheras` | Cantidad de cocheras | Entero | Conteo | Ficha RE/MAX `parkingSpaces` | Si faltaba y el texto mencionaba una cochera, el scraper de la 1ra entrega cargó 1 |
| `antiguedad_anios` | Antigüedad del edificio | Entero | Años | Ficha RE/MAX `yearBuilt` | Si viene como año: 2026 − año. Fuera de 0 a 150 → nulo (P4). 131 imputados con la mediana de barrio × `tipo_familia`, o la global (P9) |
| `antiguedad_rango` | Tramo de antigüedad | Categórica ordinal: `a estrenar`, `1-5`, `6-15`, `16-30`, `31-50`, `50+` | Años | Derivada, `limpieza P7` | Recalculada después de imputar (P9) |
| `es_a_estrenar` | El edificio es nuevo (antigüedad ≤ 0) | Binaria 0/1, con nulos | — | Derivada, scraper, de `yearBuilt` | Anulada junto con la antigüedad fuera de rango. **No se imputa** (131 nulos, las mismas filas con antigüedad imputada). Distinta de `estrenar`, que sale del texto |

## 5. Calidad y trazabilidad

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `antiguedad_anios_imputada` | 1 si `antiguedad_anios` fue imputada | Binaria 0/1 | — | Derivada, `limpieza P9` | 131 filas en 1 |
| `expensas_usd_imputada` | 1 si `expensas_usd` fue imputada | Binaria 0/1 | — | Derivada, `limpieza P9` | 321 filas en 1, casi todas casas, a las que el grupo les asigna 0 |
| `ambientes_imputada` | 1 si `ambientes` fue imputada | Binaria 0/1 | — | Derivada, `limpieza P9` | 4 filas en 1 |
| `dormitorios_imputada` | 1 si `dormitorios` fue imputada | Binaria 0/1 | — | Derivada, `limpieza P9` | 1 fila en 1 |
| `tiene_detalles` | 1 si el aviso tiene sección de características | Binaria 0/1 | — | Derivada, `limpieza P9` | Nulo informativo de `detalles` convertido en dummy: 2.173 avisos en 0 |
| `completitud_aviso` | Proporción de 11 variables clave informadas | Decimal | Proporción (0 a 1) | Derivada, `limpieza P9` | Promedio de no nulos en precio, superficies, ambientes, dormitorios, baños, antigüedad, `expensas_valor`, latitud, descripción y detalles. Se calcula **después de imputar**, así que en la práctica mide `detalles`, `expensas_valor` y `latitud`. Valores: 1 (9.657), 0,909 (2.379), 0,818 (61) |

## 6. Texto libre

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `titulo` | Título del aviso | Texto | — | RE/MAX `title` | Limpieza de espacios |
| `descripcion` | Descripción redactada por el agente | Texto | — | Ficha RE/MAX `description` | Limpieza de espacios. No se imputa: contaminaría el RegEx |
| `detalles` | Lista de características declaradas, concatenada | Texto | — | Ficha RE/MAX `features` | 2.173 nulos (18%), de naturaleza informativa: ver `tiene_detalles` |

## 7. Variables extraídas del texto (`variables.py`)

Todas salen del mismo texto: `titulo`, `descripcion` y `detalles` concatenados y
normalizados (minúsculas, sin tildes, signos reemplazados por espacio). Reemplazan las
dummies por subcadena de la 1ra entrega; la comparación está en `reporte_regex.txt`.

> **Un 0 significa "no se menciona", no "no tiene".** Un aviso que no nombra el
> ascensor puede tenerlo igual.

### 7.1 Estructura

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `piso_txt` | Piso de la unidad | Decimal | Número de piso (0 = PB) | Derivada, `variables.py` | Patrones "piso N", "N° piso", "3er piso"; válido entre 0 y 50; 0 si menciona planta baja. 60,8% nulos (no lo menciona). Reemplaza la columna `piso` del crudo, que tenía 0,3% de completitud |
| `es_planta_baja` | Menciona planta baja | Binaria 0/1 | — | Derivada, `variables.py` | "planta baja", "PB" |
| `es_ultimo_piso` | Menciona último piso | Binaria 0/1 | — | Derivada, `variables.py` | "último piso", "piso alto", "penthouse" |
| `disposicion` | Ubicación de la unidad respecto de la calle | Categórica: `frente` (2.951), `contrafrente` (3.550), `sin dato` (5.596) | — | Derivada, `variables.py` | Si el aviso menciona contrafrente, prevalece sobre "al frente". Reemplaza la dummy `frente`, que marcaba 1 en los contrafrentes |
| `sup_declarada_txt` | Primera superficie escrita en el texto | Decimal | m² | Derivada, `variables.py` | Número de 2 a 4 cifras seguido de "m2", "mts2" o "metros cuadrados". 49,8% nulos. Solo sirve como control cruzado de `sup_total_m2`: incluye valores implausibles (0 a 6.900) |

### 7.2 Índices

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `amenities` | Tiene al menos un amenity de edificio | Binaria 0/1 | — | Derivada, `variables.py` | 1 si alguna de `pileta`, `parrilla`, `gimnasio`, `sum`, `solarium`, `laundry`, `sauna` o `coworking` vale 1. Prevalencia 41,5% |
| `n_amenities` | Cantidad de atributos de confort mencionados | Entero, 0 a 15 | Conteo | Derivada, `variables.py` | Suma simple, sin ponderar, de los 8 amenities más `seguridad`, `ascensor`, `baulera`, `aire_acondicionado`, `losa_radiante`, `balcon` y `terraza`. Mediana 3 |

### 7.3 Dummies de atributos (35)

Todas son **binarias 0/1, sin nulos**, derivadas por `variables.py` con expresiones
regulares con límite de palabra (`\b`). Cuando la columna *Negación* dice "sí", un
negador ("sin", "no", "nunca", "carece de", "excepto", "salvo") en las 3 palabras previas
anula esa mención. Prevalencia calculada sobre las 12.097 filas.

| Variable | Grupo | Qué detecta (ejemplos del patrón) | Negación | Prevalencia |
|---|---|---|---|---|
| `pileta` | Amenity | pileta, piscina, natatorio | sí | 18,2% |
| `parrilla` | Amenity | parrilla, quincho, asador | sí | 28,9% |
| `gimnasio` | Amenity | gimnasio, gym | sí | 9,0% |
| `sum` | Amenity | SUM, salón de usos múltiples | sí | 17,4% |
| `solarium` | Amenity | solarium, terraza solarium | no | 14,3% |
| `laundry` | Amenity | laundry, lavadero común, sala de lavado | no | 11,9% |
| `sauna` | Amenity | sauna, spa, jacuzzi, hidromasaje | no | 5,6% |
| `coworking` | Amenity | coworking, sala de trabajo | no | 2,0% |
| `aire_acondicionado` | Confort | aire acondicionado, AA, split, frío/calor | sí | 41,4% |
| `losa_radiante` | Confort | losa o piso radiante, calefacción central, caldera individual | sí | 12,6% |
| `calefaccion` | Confort | calefacción, radiadores, tiro balanceado, calefactor | sí | 17,6% |
| `ascensor` | Confort | ascensor, elevador | sí | 43,3% |
| `baulera` | Confort | baulera | sí | 15,9% |
| `cochera_txt` | Confort | cochera, garage, estacionamiento, guardacoches | sí | 30,6% |
| `seguridad` | Confort | vigilancia, seguridad 24 h, encargado permanente, cámaras | no | 9,6% |
| `amoblado` | Confort | amoblado, amueblado, equipado con muebles | sí | 7,7% |
| `apto_mascotas` | Confort | apto o acepta mascotas, pet friendly | sí | 1,6% |
| `balcon` | Espacio | balcón, balconcito | sí | 63,6% |
| `terraza` | Espacio | terraza, azotea, aterrazado | sí | 37,6% |
| `patio_jardin` | Espacio | patio, jardín, fondo libre, parque propio | sí | 28,9% |
| `dependencia` | Espacio | dependencia, cuarto o habitación de servicio | no | 11,2% |
| `toilette` | Espacio | toilette, toilet, baño de servicio | no | 30,8% |
| `vestidor` | Espacio | vestidor, walk-in closet | no | 14,2% |
| `lavadero` | Espacio | lavadero | sí | 46,0% |
| `a_reciclar` | Estado | a reciclar, a refaccionar, a poner en valor, a demoler | no | 4,3% |
| `reciclado` | Estado | reciclado, refaccionado, remodelado, a nuevo | no | 13,2% |
| `estrenar` | Estado | a estrenar, obra nueva | no | 11,0% |
| `en_pozo` | Estado | en pozo, en construcción, en obra, preventa | no | 4,0% |
| `luminoso` | Estado | luminoso, vista abierta, vista panorámica | no | 50,5% |
| `apto_credito` | Comercialización | apto crédito, apto hipotecario | sí | 21,5% |
| `apto_profesional` | Comercialización | apto profesional, uso profesional, apto oficina | sí | 11,9% |
| `renta_actual` | Comercialización | alquilado, con inquilino, con renta, contrato vigente | no | 2,4% |
| `oportunidad` | Comercialización | oportunidad, excelente inversión, imperdible | no | 34,2% |
| `financiacion` | Comercialización | financiación, en cuotas, plan de pago | no | 8,4% |
| `dueno_directo` | Comercialización | dueño directo, sin comisión, trato directo | no | 0,0% |

`dueno_directo` vale 0 en todas las filas porque RE/MAX es una red de agentes y no
publica avisos de particulares. El patrón sí funciona: `variables.py` lo prueba contra un
texto sintético. No sirve como predictora.

## 8. Estimación del alquiler y KPIs (`kpis.py`)

Una propiedad en venta no tiene alquiler observado, así que se estima con un modelo.
Todas estas columnas **solo existen para las 10.749 ventas**; en los 1.348 alquileres el
nulo es estructural, porque sin precio de venta la rentabilidad no está definida.

**El modelo** es una regresión Ridge (`RidgeCV`) sobre `log(alquiler_usd_mes)`,
entrenada con los 1.348 alquileres. Usa estas predictoras:

- 5 numéricas, imputadas por mediana y estandarizadas: `log_sup`, `ambientes`, `banos`,
  `dormitorios`, `antiguedad_anios`.
- 2 categóricas en one-hot: `barrio` y `tipo_familia`.
- 14 dummies de texto.

En validación de 5 particiones, fuera de muestra, obtiene un R² de 0,848 en logaritmo
y un error relativo mediano de 11,2%.

**Los supuestos del KPI 2**, tomados de `supuestos.py`, son una vacancia de 5,88% y
gastos del propietario de 14,04%.

| Variable | Significado | Tipo | Unidad | Fuente | Transformaciones |
|---|---|---|---|---|---|
| `alquiler_est_usd_mes` | Alquiler mensual estimado para la propiedad en venta | Decimal | USD/mes | Derivada, `kpis.py` (`modelo_alquiler.imputar`) | `exp(predicción) × 1,0193`. El factor es el smearing de Duan, calculado con residuos fuera de muestra, y corrige el sesgo de volver del logaritmo |
| `alquiler_est_m2` | Alquiler estimado por m² | Decimal | USD/m²/mes | Derivada, `kpis.py` | `alquiler_est_usd_mes / sup_total_m2` |
| `n_alq_barrio` | Alquileres de entrenamiento en el barrio de la propiedad | Entero | Conteo | Derivada, `kpis.py` | 0 si el barrio no tiene alquileres |
| `estimacion_confiable` | 1 si el barrio tiene al menos 10 alquileres | Binaria 0/1 | — | Derivada, `kpis.py` | `n_alq_barrio ≥ 10` (`MIN_ALQ_BARRIO`). 9.203 de 10.749 ventas en 1. Por debajo, el modelo extrapola desde otros barrios. **Los resúmenes de KPIs filtran por esta columna** |
| `rent_bruta_pct` | **KPI 1**: rentabilidad bruta anual | Decimal | % anual | Derivada, `kpis.py` | `alquiler_est_usd_mes × 12 / venta_usd × 100`, a 2 decimales |
| `rent_neta_pct` | **KPI 2**: rentabilidad neta anual | Decimal | % anual | Derivada, `kpis.py` | `rent_bruta_pct × (1 − 0,0588) × (1 − 0,1404)`, a 2 decimales. Las expensas ordinarias no se descuentan: las paga el inquilino |
| `meses_repago` | **KPI 3**: meses de alquiler para recuperar el precio | Entero | Meses | Derivada, `kpis.py` | `venta_usd / alquiler_est_usd_mes`, redondeado. Recupero simple: sin descuento, sin valor residual, sin inflación |
| `error_estimacion` | Error relativo mediano del modelo en el tramo de superficie de la propiedad | Decimal, 5 valores | Proporción | Derivada, `kpis.py` | Error fuera de muestra por tramo: < 35 m² → 0,104; 35-50 → 0,097; 50-70 → 0,123; 70-100 → 0,154; 100+ → 0,174 |
| `rent_bruta_min` | **KPI 4**: extremo inferior de la banda de incertidumbre | Decimal | % anual | Derivada, `kpis.py` | `rent_bruta_pct × (1 − error_estimacion)` |
| `rent_bruta_max` | **KPI 4**: extremo superior de la banda | Decimal | % anual | Derivada, `kpis.py` | `rent_bruta_pct × (1 + error_estimacion)` |

---

## Advertencias de uso

1. **`precio_m2` mezcla unidades.** Su mediana es 1.991 en ventas (USD/m²), 18.322 en
   alquileres en pesos (ARS/m²/mes) y 16 en alquileres en dólares (USD/m²/mes). Para
   cualquier agregación hay que usar `venta_m2_usd` o `alquiler_m2_usd_mes`.
2. **Todos los precios son de publicación, no de cierre.** Tanto `venta_usd` como
   `alquiler_usd_mes` son precios pedidos.
3. **El tipo de cambio es una foto.** Toda columna en USD que viene de pesos depende del
   ARS 1.500 de `limpieza.py`. Con otro `--tc` cambian `alquiler_usd_mes`, el modelo y
   los cuatro KPIs.
4. **Hay pares de variables parecidas que miden cosas distintas.**
   - `es_a_estrenar` sale del año de construcción; `estrenar`, del texto.
   - `cocheras` es la cantidad estructurada; `cochera_txt`, la mención en el texto.
   - `superficie_rango` agrupa para el EDA; los tramos de `error_estimacion` son los
     del modelo.
5. **Hay que separar lo observado de lo imputado.** Para estadísticas de antigüedad,
   expensas, ambientes o dormitorios, conviene excluir o marcar las filas con
   `<variable>_imputada == 1`.
6. **La cartera de RE/MAX no es el mercado.** Está sesgada en precio y en cobertura
   geográfica; el detalle está en `informe/FUENTES_EXTERNAS.md` y en `sesgo_*.csv`.
