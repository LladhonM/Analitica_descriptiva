#!/usr/bin/env python
"""
test_variables.py — Tests del motor de extraccion por RegEx. No toca la red.

Cada patron nuevo que se agregue a `variables.PATRONES` deberia entrar aca con
al menos dos casos: uno que tiene que dar 1 y uno que tiene que dar 0. Los
casos negativos son los que valen: son los que evitan volver a los errores que
este modulo vino a corregir.

Uso:
    py src/test_variables.py
"""

import sys

import numpy as np

from variables import (extraer_dummies, extraer_estructura, normalizar,
                       dummies_viejas, PATRONES)


fallos = []
corridos = 0


def check(descripcion: str, obtenido, esperado) -> None:
    global corridos
    corridos += 1
    ok = (obtenido == esperado) or (
        isinstance(esperado, float) and isinstance(obtenido, float)
        and np.isnan(esperado) and np.isnan(obtenido))
    if not ok:
        fallos.append(f"{descripcion}\n      esperado {esperado!r}, obtenido {obtenido!r}")


def dummy(texto: str, campo: str):
    return extraer_dummies(normalizar(texto))[campo]


def estructura(texto: str, campo: str):
    return extraer_estructura(normalizar(texto))[campo]


# ==========================================================================
# 1. NORMALIZACION
# ==========================================================================

check("normaliza tildes", normalizar("Balcón Aterrazado"), "balcon aterrazado")
check("colapsa espacios", normalizar("piso   3   \n  frente"), "piso 3 frente")
check("los signos se vuelven espacio, no se borran",
      normalizar("cochera/baulera"), "cochera baulera")
check("acepta no-string sin romper", normalizar(None), "")
check("acepta NaN sin romper", normalizar(float("nan")), "")


# ==========================================================================
# 2. EL ERROR DE FRAGMENTO: subcadena dentro de otra palabra
# ==========================================================================

# Este es el caso que motivo todo el modulo: "sum" dentro de "consumo".
check("'consumo' NO es un SUM", dummy("bajo consumo de gas", "sum"), 0)
check("'resumen' NO es un SUM", dummy("resumen de la propiedad", "sum"), 0)
check("'asumir' NO es un SUM", dummy("puede asumir el contrato", "sum"), 0)
check("SUM como sigla si cuenta", dummy("edificio con SUM y parrilla", "sum"), 1)
check("salon de usos multiples cuenta",
      dummy("cuenta con salon de usos multiples", "sum"), 1)

check("el metodo viejo SI se equivocaba con consumo",
      dummies_viejas(normalizar("bajo consumo de gas"))["amenities"], 1)
check("el metodo nuevo no",
      dummy("bajo consumo de gas", "sum"), 0)

check("'sumamente' no dispara amenities",
      extraer_dummies(normalizar("departamento sumamente luminoso"))["sum"], 0)


# ==========================================================================
# 3. EL ERROR DE ANTONIMO: contrafrente contiene frente
# ==========================================================================

check("contrafrente no es frente",
      estructura("departamento al contrafrente muy silencioso", "disposicion"),
      "contrafrente")
check("al frente es frente",
      estructura("living al frente con vista", "disposicion"), "frente")
check("si menciona los dos, gana contrafrente porque es lo que se declara",
      estructura("living al frente y dormitorio al contrafrente", "disposicion"),
      "contrafrente")
check("sin mencion queda sin dato",
      estructura("departamento de dos ambientes", "disposicion"), "sin dato")
check("el metodo viejo colapsaba ambos en la misma dummy",
      dummies_viejas(normalizar("unidad al contrafrente"))["frente"], 1)


# ==========================================================================
# 4. NEGACION
# ==========================================================================

check("sin balcon", dummy("departamento sin balcon", "balcon"), 0)
check("no posee balcon", dummy("la unidad no posee balcon", "balcon"), 0)
check("no cuenta con cochera", dummy("no cuenta con cochera", "cochera_txt"), 0)
check("con balcon", dummy("amplio balcon con vista", "balcon"), 1)

# El veto es por ocurrencia: si el aviso niega en un lado y afirma en otro,
# la afirmacion vale. Es deliberado, no un bug.
check("niega en una frase y afirma en otra -> gana la afirmacion",
      dummy("el edificio no posee cochera propia pero se alquila una cochera "
            "en el subsuelo", "cochera_txt"), 1)

# La ventana es corta a proposito: una negacion lejana no debe vetar.
check("negacion lejana no veta",
      dummy("sin expensas extraordinarias durante el primer anio, ademas "
            "cuenta con balcon", "balcon"), 1)

check("'sin estrenar' no se lee como negacion de estrenar",
      dummy("departamento sin estrenar", "estrenar"), 1)


# ==========================================================================
# 5. MORFOLOGIA: plurales, femeninos y variantes de escritura
# ==========================================================================

check("plural", dummy("dos bauleras incluidas", "baulera"), 1)
check("femenino", dummy("totalmente reciclada", "reciclado"), 1)
check("masculino", dummy("totalmente reciclado", "reciclado"), 1)
check("garage con e", dummy("garage cubierto", "cochera_txt"), 1)
check("garaje con j", dummy("garaje cubierto", "cochera_txt"), 1)
# Este test encontro un bug real: el patron era `garage?s?`, que hace opcional
# la 'e' y matchea el fragmento "garag" suelto. Queda como regresion.
check("fragmento 'garag' no alcanza", dummy("garag cubierto", "cochera_txt"), 0)
check("gym", dummy("gym en planta baja", "gimnasio"), 1)
check("aire acondicionado escrito split", dummy("dos split frio calor", "aire_acondicionado"), 1)
check("frio-calor con guion", dummy("equipo frio-calor", "aire_acondicionado"), 1)


# ==========================================================================
# 6. ESTADO: a reciclar contra reciclado
# ==========================================================================

check("a reciclar", dummy("propiedad a reciclar", "a_reciclar"), 1)
check("a reciclar no marca reciclado", dummy("propiedad a reciclar", "reciclado"), 0)
check("reciclado no marca a_reciclar", dummy("bano reciclado a nuevo", "a_reciclar"), 0)
check("a demoler cuenta como a reciclar", dummy("lote a demoler", "a_reciclar"), 1)


# ==========================================================================
# 7. EXTRACCION DE PISO
# ==========================================================================

check("piso N", estructura("ubicado en piso 7 contrafrente", "piso_txt"), 7.0)
check("Nmo piso", estructura("3er piso por escalera", "piso_txt"), 3.0)
check("planta baja da piso 0", estructura("departamento en planta baja", "piso_txt"), 0.0)
check("planta baja marca la dummy", estructura("departamento en planta baja", "es_planta_baja"), 1)
check("PB abreviada", estructura("unidad en pb con patio", "es_planta_baja"), 1)
check("ultimo piso", estructura("ultimo piso con terraza propia", "es_ultimo_piso"), 1)
check("penthouse es ultimo piso", estructura("exclusivo penthouse", "es_ultimo_piso"), 1)
check("sin piso queda NaN", estructura("dos ambientes al frente", "piso_txt"), float("nan"))
check("piso absurdo se descarta (no hay 80 pisos en CABA)",
      estructura("piso 80 del edificio", "piso_txt"), float("nan"))


# ==========================================================================
# 8. SUPERFICIE DECLARADA EN EL TEXTO
# ==========================================================================

check("m2 pegado", estructura("son 65m2 totales", "sup_declarada_txt"), 65.0)
check("m2 separado", estructura("superficie de 120 m2", "sup_declarada_txt"), 120.0)
check("metros cuadrados en palabras",
      estructura("tiene 48 metros cuadrados", "sup_declarada_txt"), 48.0)
check("sin superficie queda NaN",
      estructura("luminoso y comodo", "sup_declarada_txt"), float("nan"))


# ==========================================================================
# 9. VARIABLES NUEVAS QUE NO EXISTIAN EN LA 1RA ENTREGA
# ==========================================================================

check("apto mascotas", dummy("apto mascotas pequenas", "apto_mascotas"), 1)
check("dueno directo", dummy("vende dueno directo sin comision", "dueno_directo"), 1)
check("en pozo", dummy("unidad en pozo con entrega 2027", "en_pozo"), 1)
check("renta actual", dummy("actualmente alquilado con contrato vigente", "renta_actual"), 1)
check("oportunidad", dummy("unica oportunidad de inversion", "oportunidad"), 1)
check("dependencia de servicio", dummy("con dependencia de servicio", "dependencia"), 1)
check("vestidor", dummy("suite con vestidor", "vestidor"), 1)
check("toilette", dummy("bano completo y toilette", "toilette"), 1)


# ==========================================================================
# 10. INVARIANTES DEL MOTOR
# ==========================================================================

vacio = extraer_dummies("")
check("texto vacio deja todas las dummies en 0", sum(vacio.values()), 0)
check("texto vacio devuelve todas las claves", len(vacio), len(PATRONES))
check("todo valor es 0 o 1", set(vacio.values()) <= {0, 1}, True)

completo = extraer_dummies(normalizar(
    "Piso 4 al frente. Balcon aterrazado, cochera y baulera. Edificio con "
    "pileta, parrilla, SUM, gimnasio y seguridad 24 hs. Apto credito."))
for campo in ["balcon", "cochera_txt", "baulera", "pileta", "parrilla",
              "sum", "gimnasio", "seguridad", "apto_credito"]:
    check(f"aviso completo detecta {campo}", completo[campo], 1)
check("aviso completo NO inventa pozo", completo["en_pozo"], 0)
check("aviso completo NO inventa a_reciclar", completo["a_reciclar"], 0)


# ==========================================================================
# RESULTADO
# ==========================================================================

print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
