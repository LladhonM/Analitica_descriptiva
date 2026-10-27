#!/usr/bin/env python
"""
supuestos.py — Todos los supuestos y umbrales del analisis, en un solo lugar.

POR QUE EXISTE
--------------
En la 1ra entrega la vacancia y los gastos eran dos numeros sueltos (8% y 12%)
sin fuente, y el presupuesto del inversor, los minimos de cobertura y los
cortes de los graficos estaban repartidos entre notebooks. Este modulo los
junta, y cada constante lleva al lado de donde sale y cuando se consulto.

Los valores que se DERIVAN (la vacancia, el total de gastos, la banda de
retorno) se calculan aca a partir de sus componentes, nunca se escriben a
mano: si alguien cambia un componente, el total lo sigue solo.

QUE NO ESTA ACA, A PROPOSITO
----------------------------
- LIMITES y PERCENTILES de limpieza.py: son reglas de limpieza, no supuestos
  del analisis. Moverlos obligaria a reejecutar el pipeline sin motivo.
- Los parametros del modelo (BINS_SUP, MIN_ALQ_BARRIO, las variables
  predictoras): viven en modelo_alquiler.py, junto al modelo que los usa.
  Los notebooks que necesiten BINS_SUP lo toman de ahi.

Uso:
    import supuestos as S
    S.VACANCIA_PCT, S.GASTOS_PCT, S.PRESUPUESTO_USD
    py src/supuestos.py          # imprime la tabla de supuestos con sus fuentes
"""

from __future__ import annotations

# Las fuentes web citadas abajo se consultaron el 28-09-2026, salvo que la
# linea indique otra fecha. Los mercados se mueven: esto fija a que momento
# corresponde cada numero.


# ==========================================================================
# 0. TIPO DE CAMBIO
# ==========================================================================
# Convierte a dolares los precios publicados en pesos (el 81,6% de los
# alquileres del dataset limpio; las ventas estan todas en USD). Es un SUPUESTO, no un dato del
# aviso: el portal no informa a que cambio convierte cada publicador.
#
# Fuente: BCRA, Tipo de Cambio de Referencia Com. "A" 3500 (mayorista),
# api.bcra.gob.ar/estadisticascambiarias, consultado el 06-10-2026.
#   - Promedio de agosto de 2026 (20 dias habiles): ARS 1.499,92
#   - 14-08-2026, ultimo dia habil antes del scraping (16-08): ARS 1.487,50
# Criterio: promedio del mes del scraping, redondeado. Un solo dia expone el
# resultado al ruido diario, y el promedio mensual es la misma variable que
# releva el REM del BCRA. El A 3500 es el oficial mayorista: el MEP y el
# minorista cotizan algo por encima, y el TC implicito en los avisos (ARS
# ~1.150, notebook 01 sec. 4.1) por debajo.
TC_ARS_USD = 1500                # BCRA A 3500, promedio ago-2026 (1.499,92)


# ==========================================================================
# 1. PRESUPUESTO DEL INVERSOR
# ==========================================================================

# Perfil definido en la 1ra entrega (Entrega 1/README.md, "El interlocutor"): una
# persona con ahorros en dolares, tipicamente entre USD 80.000 y 200.000.
# Es un parametro del problema, no un hallazgo: por eso no tiene fuente externa.
PRESUPUESTO_MIN_USD = 80_000     # Entrega 1/README.md (ago-2026)
PRESUPUESTO_MAX_USD = 200_000    # idem
PRESUPUESTO_USD = (PRESUPUESTO_MIN_USD, PRESUPUESTO_MAX_USD)


# ==========================================================================
# 2. VACANCIA
# ==========================================================================
# Definicion: fraccion del anio en que la unidad no genera alquiler porque esta
# entre un inquilino y el siguiente. No incluye morosidad (inquilino que ocupa
# y no paga), que es otro riesgo y no se modela.
#
# Se deriva de dos cosas medibles por separado: cuanto tarda en re-alquilarse
# y cada cuanto hay que re-alquilar. vacancia = meses_vacios / ciclo completo.

# Camara Inmobiliaria Argentina (N. Vieitez) y SD Propiedades en Ambito,
# 01-10-2025: "una propiedad se alquila entre 30 y 60 dias promedio";
# "historicamente se necesitaba un mes... hoy el promedio es de dos meses".
# Se toma el punto medio del rango.
MESES_VACIOS_POR_ROTACION = 1.5  # Ambito 01-10-2025, rango 1 a 2 meses

# CCyC art. 1198 segun DNU 70/2023: el plazo es libre, y si el contrato no lo
# fija, para vivienda permanente es de 2 anios. Se usa el plazo supletorio
# porque es el unico con respaldo legal; contratos de 1 anio duplican la
# cantidad de rotaciones y llevan la vacancia a ~11% (ver sensibilidad en kpis.py).
DURACION_CONTRATO_MESES = 24     # CCyC art. 1198, texto DNU 70/2023 (dic-2023)

VACANCIA_PCT = round(MESES_VACIOS_POR_ROTACION / (DURACION_CONTRATO_MESES + MESES_VACIOS_POR_ROTACION) * 100, 2)


# ==========================================================================
# 3. GASTOS DEL PROPIETARIO, DESAGREGADOS
# ==========================================================================
# Todos se expresan como % del alquiler efectivamente cobrado, porque asi los
# aplica el modelo: neta = bruta x (1 - vacancia) x (1 - gastos).
#
# Las expensas ORDINARIAS no estan: en CABA las paga el inquilino
# (CCyC art. 1209). Descontarlas seria cobrarle al propietario un gasto ajeno.

# --- 3a. Administracion -----------------------------------------------------
# Ley 5859 CABA: la comision de locacion en vivienda la paga solo el
# propietario, con tope de 4,15% del valor total del contrato (IVA incluido).
# Como se calcula sobre la suma de los alquileres del contrato, equivale a
# 4,15% de cada alquiler cobrado. Fuente: Garantear, 14-08-2026; Plato,
# 19-04-2026. NO incluye la administracion mensual delegada (cobro, rendicion),
# que las inmobiliarias cobran aparte entre 5% y 10%: se asume que el
# inversor cobra directo. Si delega, este componente sube a ~9-14%.
ADMINISTRACION_PCT = 4.15        # Ley 5859 CABA, tope legal

# --- 3b. ABL ----------------------------------------------------------------
# CCyC art. 1209: el inquilino no paga "las cargas que graven la cosa"; y ante
# AGIP el contribuyente es siempre el propietario (Roomix, 05-05-2026). Muchos
# contratos se lo trasladan al inquilino, pero no es la regla: se asume que lo
# paga el propietario, que es el caso conservador.
# Monto: Ley Tarifaria 6927 (2026), ejemplos de Roomix 05-05-2026 para
# valuaciones fiscales de ARS 15M y 25M, el rango de un 2 ambientes usado.
ABL_ARS_MES_MIN = 21_250         # VFH ARS 15M, coef. 0,75 (Roomix 05-05-2026)
ABL_ARS_MES_MAX = 43_994         # VFH ARS 25M, coef. 1,25 (idem)
ABL_ARS_MES = (ABL_ARS_MES_MIN + ABL_ARS_MES_MAX) / 2

# Alquiler de referencia para pasar el ABL a porcentaje: mediana de los
# alquileres de 2 ambientes y 40-60 m2 del propio dataset (scraping ago-2026),
# convertida al tipo de cambio de la seccion 0 (TC_ARS_USD).
# test_supuestos.py verifica que siga coincidiendo con el dataset.
ALQUILER_REF_USD_MES = 573       # dataset_analitico.csv, 2 amb 40-60 m2

ABL_PCT = round(ABL_ARS_MES / (ALQUILER_REF_USD_MES * TC_ARS_USD) * 100, 2)

# --- 3c. Expensas extraordinarias -------------------------------------------
# Las paga el propietario (CCyC art. 1209). Se estiman como la fraccion de las
# expensas totales que va a obras extraordinarias, por el peso de las expensas
# sobre el alquiler.
# ConsorcioAbierto (datos CABA) en Ambito, 14-07-2026: "obras extraordinarias
# ~9%" del total de expensas.
EXTRAORD_SOBRE_EXPENSAS = 0.09   # ConsorcioAbierto via Ambito 14-07-2026
# Mediana de expensas_sobre_alquiler en los alquileres del dataset. Coincide
# con el 22,9% que publica iProfesional (28-09-2026) para CABA.
EXPENSAS_SOBRE_ALQUILER = 0.213  # dataset_analitico.csv, alquileres

EXTRAORDINARIAS_PCT = round(EXTRAORD_SOBRE_EXPENSAS * EXPENSAS_SOBRE_ALQUILER * 100, 2)

# --- 3d. Mantenimiento ------------------------------------------------------
# CCyC art. 1201: el locador debe conservar la cosa apta para el uso, y las
# reparaciones por desgaste o antiguedad son suyas. Es el componente con menos
# respaldo: no hay una serie publicada para CABA. Se asume medio mes de
# alquiler por anio (pintura y arreglos al rotar inquilino, reposicion de
# artefactos). La regla internacional del 1% del valor del inmueble daria ~15%,
# pero incluye partes comunes que aca ya cubren las expensas.
# ESTIMACION PROPIA: es el primer candidato a revisar si hay mejor dato.
MANTENIMIENTO_MESES_POR_ANIO = 0.5  # estimacion propia, sin fuente publicada
MANTENIMIENTO_PCT = round(MANTENIMIENTO_MESES_POR_ANIO / 12 * 100, 2)

GASTOS_COMPONENTES = {
    "administracion": ADMINISTRACION_PCT,
    "abl": ABL_PCT,
    "extraordinarias": EXTRAORDINARIAS_PCT,
    "mantenimiento": MANTENIMIENTO_PCT,
}
# El modelo recibe un solo numero. test_supuestos.py verifica que sea la suma.
GASTOS_PCT = round(sum(GASTOS_COMPONENTES.values()), 2)

# Valores de la 1ra entrega, conservados para poder reproducir sus KPIs y
# reportar el antes y el despues.
VACANCIA_PCT_ENTREGA_1 = 8.0     # 1ra entrega, sin fuente
GASTOS_PCT_ENTREGA_1 = 12.0      # idem

# Grilla del analisis de sensibilidad de kpis.py.
SENSIBILIDAD_VACANCIA = [4.0, 6.0, 8.0, 10.0, 12.0]
SENSIBILIDAD_GASTOS = [8.0, 10.0, 12.0, 14.0, 16.0]


# ==========================================================================
# 4. RETORNO MINIMO: COSTO DE OPORTUNIDAD
# ==========================================================================
# RESTRICCION DEL ANALISIS, NO RECOMENDACION DE INVERSION.
# Es la vara contra la que se lee la rentabilidad neta: si el ladrillo rinde
# menos que un bono en dolares, el inversor esta pagando la iliquidez del
# inmueble en vez de cobrarla.
#
# La banda son las ON corporativas en USD de primera linea: es la alternativa
# de renta fija que un ahorrista puede comprar con el mismo capital, en
# dolares y con riesgo argentino, igual que el inmueble. Va como banda y no
# como numero porque el plazo cambia la tasa: 7,1% a 5 anios, 7,6% a 11.
TIR_ON_YPF_2031 = 7.1            # YMCXO, Ambito jul-2026
TIR_ON_PAMPA_2037 = 7.6          # MGCRO, Ambito jul-2026

RETORNO_MIN_PISO_PCT = min(TIR_ON_YPF_2031, TIR_ON_PAMPA_2037)
RETORNO_MIN_TECHO_PCT = max(TIR_ON_YPF_2031, TIR_ON_PAMPA_2037)
RETORNO_MINIMO_BANDA = (RETORNO_MIN_PISO_PCT, RETORNO_MIN_TECHO_PCT)

# Referencia, fuera de la banda: rendimiento soberano aproximado como
# Treasury + riesgo pais (EMBI, J.P. Morgan). No es la vara del inversor: es
# lo que cobra el riesgo pais puro, y sirve para leer cuanto de la banda es
# prima por riesgo argentino. El EMBI es spread sobre la curva de EE.UU., asi
# que sumarlo al 10 anios es una aproximacion, no la TIR de un bono puntual.
UST_10A_PCT = 5.24               # ABC Color / Bloomberg Linea, 28-09-2026
RIESGO_PAIS_PB = 641             # El Vocero / Indicadores AR, 28-09-2026
RETORNO_SOBERANO_REF_PCT = round(UST_10A_PCT + RIESGO_PAIS_PB / 100, 2)


# ==========================================================================
# 4b. HORIZONTE
# ==========================================================================
# El horizonte de tenencia se fija igual al plazo de la ON que define el piso
# de la banda (YMCXO vence en 2031): comparar un inmueble contra un bono solo
# tiene sentido a plazo equivalente. Cinco anios cubren ademas dos contratos
# completos de DURACION_CONTRATO_MESES con sus rotaciones.
# Es un parametro del problema, como el presupuesto: si el cliente declara
# otro horizonte, se cambia aca y la banda deberia elegir la ON de ese plazo.
HORIZONTE_ANIOS = 5              # vencimiento YMCXO (2031) desde 2026


# ==========================================================================
# 4c. ALQUILER TEMPORAL (la alternativa de explotacion)
# ==========================================================================
# Se compara neta contra neta con el tradicional. La asimetria que mas pesa:
# en el temporal las expensas y los servicios los paga el duenio; en el
# tradicional, en CABA, el inquilino. La vacancia no se descuenta aparte
# porque ya esta en la ocupacion.
#
# Todos los porcentajes van sobre el ingreso bruto por noches, salvo la
# gestion, que se cobra sobre lo que queda despues de la plataforma.

# Airbnb paso a la tarifa unica "host-only": la comision la paga entera el
# anfitrion. Migracion de todos los anfitriones fuera del EEE al 15-09-2026.
# Hostfully / Smoobu, 2026.
COMISION_PLATAFORMA_PCT = 15.5   # Airbnb host-only fee, 2026

# BeeMyHost (Buenos Aires), plan intermedio "Bee Full": 18% sobre el neto de
# comision de plataforma y limpieza. Planes de 9% (el duenio opera) a 28%.
# Se usa el intermedio porque el temporal exige check-ins, reposicion y
# atencion diaria: autogestionarlo es un trabajo, no un ahorro. temporal.py
# reporta tambien la variante autogestionada (0%).
GESTION_TEMPORAL_PCT = 18.0      # BeeMyHost, consultado 28-09-2026

# D. Bryn (Invertire) en La Nacion, 29-05-2025: mantenimiento "otro 10% a 15%"
# de los ingresos. Es mayor que en el tradicional por el desgaste de rotar
# huespedes cada pocos dias. Se toma el punto medio.
MANTENIMIENTO_TEMPORAL_PCT = 12.5  # La Nacion 29-05-2025, rango 10-15%

# Limpieza: no es costo neto. Se cobra al huesped como fee por reserva y cubre
# limpieza, lavanderia e insumos (BeeMyHost). Tampoco esta en el ingreso que
# informa Inside Airbnb, que es precio por noche.

# Servicios que paga el duenio: luz, gas y agua de un hogar del AMBA sin
# subsidio. IIEP UBA-CONICET via Infobae, 21-06-2026: ARS 282.758 de canasta
# menos 116.688 de transporte. Es junio, con gas de invierno: es un techo.
# Internet NO esta incluido: no se encontro un dato verificable y se deja
# como costo no cuantificado (sesga levemente a favor del temporal).
SERVICIOS_ARS_MES = 282_758 - 116_688  # IIEP UBA-CONICET, jun-2026

# Amoblamiento y equipamiento inicial, amortizado en el horizonte. ESTIMACION
# PROPIA: no se encontro una fuente publicada con montos para CABA. Es el
# segundo candidato a revisar, despues del mantenimiento del tradicional.
AMOBLAMIENTO_USD = {"0-1": 4_000, "2": 6_000, "3+": 8_000}  # estimacion propia

# Ocupacion de referencia externa, para contrastar la estimada por Inside
# Airbnb (que se infiere de resenias y sale mucho mas baja). La Nacion,
# 29-05-2025, informa 53% para CABA. No se usa como caso base: se usa para
# mostrar cuanto cambia la conclusion segun que ocupacion se crea.
OCUPACION_REF_PCT = 53.0         # La Nacion 29-05-2025

# Minimo de avisos por celda barrio x dormitorios, de cada lado (Airbnb
# activos y ventas de RE/MAX), para comparar.
MIN_CELDA_TEMPORAL = 20


# ==========================================================================
# 5. COBERTURA Y COMPLETITUD
# ==========================================================================
# Minimos de observaciones por debajo de los cuales un estadistico no se
# informa. La mediana de 5 avisos cambia de lugar con un aviso mas.

# Criterio de seleccion de predictoras del modelo (modelo_alquiler.py):
# disponibilidad de al menos 95% de completitud. Se aplico al elegirlas, no
# se verifica en cada corrida porque el dataset analitico ya trae las
# predictoras imputadas; por eso queda como criterio declarado y no como
# constante.

MIN_VENTAS_BARRIO = 30           # barrio entra al ranking y a los violines
MIN_AVISOS_TRAMO = 20            # tramo de superficie entra al boxplot
MIN_AVISOS_CELDA = 10            # celda barrio x tramo: estrato de comparacion
# Dentro de una celda del estrato, cada grupo que se compara (con y sin
# amenities, a reciclar o no) necesita al menos esta cantidad de avisos. Con
# menos, la mediana del grupo chico la mueve un solo aviso.
MIN_GRUPO_ESTRATO = 5
# Para correlaciones dentro de una celda: un Spearman sobre 10 puntos oscila
# demasiado. Se exige el mismo minimo que para entrar al ranking de barrios.
MIN_CELDA_CORRELACION = MIN_VENTAS_BARRIO


# ==========================================================================
# 6. CORTES GRAFICOS
# ==========================================================================
# Recortan la VISTA, nunca los datos: los estadisticos que acompanan cada
# grafico se calculan sobre la serie completa.

# Orden de las etiquetas de superficie_rango. Los cortes los define
# limpieza.py (0/35/55/80/120 m2); test_supuestos.py verifica que coincidan.
ORDEN_SUPERFICIE_RANGO = ["hasta 35", "36-55", "56-80", "81-120", "120+"]

N_BARRIOS_EXTREMOS = 6           # violines: 6 barrios de arriba y 6 de abajo

VIOLIN_TECHO_CUANTIL = 0.995     # eje y del violin
HIST_RANGO_CUANTILES = (0.01, 0.99)  # histograma de rentabilidad
HIST_N_BORDES = 56               # bordes de bins (55 barras)
ECDF_XMAX_CUANTIL = 0.985        # eje x de la ECDF del ticket


# ==========================================================================

def tabla() -> str:
    """Resumen legible de los supuestos derivados, para reportes y notebooks."""
    l = [
        f"Presupuesto del inversor : USD {PRESUPUESTO_MIN_USD:,} a {PRESUPUESTO_MAX_USD:,}",
        "",
        f"Vacancia                 : {VACANCIA_PCT:.2f}%  "
        f"({MESES_VACIOS_POR_ROTACION} meses vacios cada contrato de {DURACION_CONTRATO_MESES})",
        "",
        "Gastos del propietario (% del alquiler cobrado):",
        f"    administracion       : {ADMINISTRACION_PCT:>5.2f}%  comision de locacion, Ley 5859",
        f"    ABL                  : {ABL_PCT:>5.2f}%  ARS {ABL_ARS_MES:,.0f}/mes sobre "
        f"USD {ALQUILER_REF_USD_MES} x {TC_ARS_USD}",
        f"    extraordinarias      : {EXTRAORDINARIAS_PCT:>5.2f}%  "
        f"{EXTRAORD_SOBRE_EXPENSAS:.0%} de expensas que pesan {EXPENSAS_SOBRE_ALQUILER:.1%}",
        f"    mantenimiento        : {MANTENIMIENTO_PCT:>5.2f}%  "
        f"{MANTENIMIENTO_MESES_POR_ANIO} mes de alquiler por anio (estimacion propia)",
        f"    TOTAL                : {GASTOS_PCT:>5.2f}%",
        "",
        f"Retorno minimo (banda)   : {RETORNO_MIN_PISO_PCT:.2f}% a {RETORNO_MIN_TECHO_PCT:.2f}%  "
        f"(ON corporativas USD, 2031 a 2037)",
        "    restriccion del analisis, no recomendacion de inversion",
        f"    referencia soberana  : {RETORNO_SOBERANO_REF_PCT:.2f}%  "
        f"(Treasury 10 anios + {RIESGO_PAIS_PB} pb)",
        f"Horizonte                : {HORIZONTE_ANIOS} anios  (plazo de la ON del piso)",
    ]
    return "\n".join(l)


if __name__ == "__main__":
    print(tabla())
