#!/usr/bin/env python
"""
test_sintesis.py — Tests de sintesis.py (PCA, MCA y micro-mercados), sin datos.

Oraculos independientes:
  - el MCA de dos variables, contra el chi-cuadrado de scipy: sus autovalores
    no triviales cumplen (2*lambda - 1)^2 = autovalores del analisis de
    correspondencias simple, que suman chi2 / n
  - la inercia total del MCA, contra la identidad K/Q - 1
  - las coordenadas de los avisos, contra la formula de transicion (cada aviso
    es el promedio de sus categorias, dividido por la raiz del autovalor)
  - los micro-mercados, contra grupos plantados
  - la prima en la celda, contra una prima plantada
con NEGATIVOS donde el metodo ingenuo se equivoca y el correcto no.

Uso:
    py src/test_sintesis.py
"""

import sys

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import adjusted_rand_score

import sintesis as SI


fallos = []
corridos = 0


def check(descripcion: str, condicion: bool, detalle: str = "") -> None:
    global corridos
    corridos += 1
    if not condicion:
        fallos.append(descripcion + (f"\n      {detalle}" if detalle else ""))


rng = np.random.default_rng(5)

# --- MCA de dos variables contra scipy -------------------------------------------
n = 2_000
a = rng.choice(["x", "y", "z"], n)
b = np.where(rng.random(n) < 0.6, np.where(a == "x", "p", np.where(a == "y", "q", "r")), rng.choice(["p", "q", "r", "s"], n))
dos = pd.DataFrame({"a": a, "b": b})
m = SI.mca(dos, n_ejes=2)
lam = m["autovalores"]
chi2 = stats.chi2_contingency(pd.crosstab(dos["a"], dos["b"]), correction=False)[0]
mu = (2 * lam[lam > 0.5 + 1e-12] - 1) ** 2
check("MCA de dos variables: sus autovalores reproducen el chi-cuadrado de scipy",
      abs(mu.sum() - chi2 / n) < 1e-8, f"{mu.sum():.6f} contra {chi2 / n:.6f}")
K = dos["a"].nunique() + dos["b"].nunique()
check("MCA: la inercia total es K/Q - 1", abs(lam.sum() - (K / 2 - 1)) < 1e-8, f"{lam.sum()} contra {K / 2 - 1}")

# --- Formula de transicion ---------------------------------------------------------
Z = pd.get_dummies(dos, prefix_sep="=", dtype=float)
prom = Z.values @ m["categorias"].values / 2
check("MCA: cada aviso es el promedio de sus categorias / raiz del autovalor",
      np.allclose(m["filas"], prom / np.sqrt(lam[:2])), "formula de transicion")

# --- Benzecri --------------------------------------------------------------------
bz = SI.benzecri(np.array([0.30, 0.20, 0.10, 0.05]), q=10)
check("Benzecri: suma 1", abs(bz.sum() - 1) < 1e-12)
check("Benzecri: un autovalor <= 1/Q no aporta", bz[2] == 0 and bz[3] == 0, f"{bz}")

# --- Grupos plantados --------------------------------------------------------------
# Tres tipos de propiedad latentes; cada uno tiene probabilidades distintas en
# ocho atributos si/no y en una categorica de tamanio.
tipos = rng.integers(0, 3, 3_000)
prob = np.array([[0.9, 0.9, 0.8, 0.1, 0.1, 0.1, 0.5, 0.5],
                 [0.1, 0.1, 0.1, 0.9, 0.9, 0.8, 0.5, 0.5],
                 [0.1, 0.2, 0.1, 0.1, 0.2, 0.1, 0.9, 0.9]])
plant = pd.DataFrame({f"v{j}": np.where(rng.random(3_000) < prob[tipos, j], "si", "no") for j in range(8)})
plant["tam"] = np.where(rng.random(3_000) < 0.8, np.array(["chico", "medio", "grande"])[tipos],
                        rng.choice(["chico", "medio", "grande"], 3_000))
mp = SI.mca(plant, n_ejes=3)
lab = SI.micromercados(mp["filas"], k=3)
ari = adjusted_rand_score(tipos, lab)
check("micro-mercados: recuperan los tipos plantados", ari > 0.9, f"ARI {ari:.3f}")
check("micro-mercados: etiquetas ordenadas por tamanio",
      list(pd.Series(lab).value_counts().index) == sorted(set(lab)))
est = SI.estabilidad(mp["filas"], lab, k=3, n=5)
check("estabilidad: con grupos reales, las submuestras dan los mismos grupos", est.min() > 0.9, f"{est}")
inercia_cruda = mp["autovalores"][:2].sum() / mp["autovalores"].sum()
check("Benzecri: con la correccion, los dos ejes resumen casi todo", mp["benzecri"][:2].sum() > 0.85,
      f"{mp['benzecri'][:2].sum():.3f}")
check("NEG: la inercia cruda subestima lo que resumen los dos ejes",
      inercia_cruda < mp["benzecri"][:2].sum() - 0.25, f"cruda {inercia_cruda:.3f}")

# Sin estructura, la silueta cae: el clustering no fabrica grupos donde no hay.
ruido = pd.DataFrame({f"v{j}": rng.choice(["si", "no"], 3_000) for j in range(8)})
sil_ruido = SI.silueta_por_k(SI.mca(ruido)["filas"], [3]).iloc[0]
sil_plant = SI.silueta_por_k(mp["filas"], [3]).iloc[0]
check("NEG: sin estructura plantada la silueta es mucho menor", sil_plant > sil_ruido + 0.2,
      f"plantada {sil_plant:.3f}, ruido {sil_ruido:.3f}")

# --- PCA --------------------------------------------------------------------------
base = pd.DataFrame({c: (rng.random(1_000) < 0.3).astype(int) for c in SI.ATRIBUTOS})
edif = rng.random(1_000) < 0.4
for c in SI.EDIFICIO[:6]:
    base[c] = (edif & (rng.random(1_000) < 0.85)).astype(int)
pc = SI.pca_atributos(base)
check("PCA: la varianza explicada suma 1", abs(pc["varianza"].sum() - 1) < 1e-10)
top = pc["cargas"]["CP1"].abs().sort_values(ascending=False).index[:6]
check("PCA: el primer componente junta los amenities correlacionados", set(top) == set(SI.EDIFICIO[:6]), f"{list(top)}")
# Tolerancia 1e-3: StandardScaler divide por n y PCA por n - 1, y eso mueve
# la carga en la cuarta decimal. Las cargas se leen con dos.
check("PCA: las cargas son correlaciones con el puntaje",
      abs(abs(pc["cargas"].loc["pileta", "CP1"])
          - abs(np.corrcoef(base["pileta"], pc["puntajes"][:, 0])[0, 1])) < 1e-3)

# --- Nombres -----------------------------------------------------------------------
toy = pd.DataFrame({"grupo": [0, 0, 1, 1, 2, 2, 3, 3],
                    "tipo_familia": ["departamento"] * 4 + ["ph", "casa"] + ["departamento"] * 2,
                    "amenities": [0, 0, 1, 1, 0, 1, 0, 0],
                    "sup_total_m2": [45, 50, 55, 60, 150, 200, 95, 100]})
nom = SI.nombrar(toy)
check("nombrar: reglas fijas", nom == {2: "PH y casas", 1: "torre con amenities",
                                       3: "departamento clasico grande", 0: "departamento estandar"}, f"{nom}")

# --- Prima en la celda ---------------------------------------------------------------
# El grupo 1 esta concentrado en el barrio caro y vale 20% mas que el 0 dentro
# de cada celda. Comparado sin celda, la prima se infla con la del barrio.
filas = []
for barrio, nivel, share in [("caro", 3000, 0.7), ("barato", 1500, 0.1)]:
    for sup in ["36-55", "56-80"]:
        for _ in range(300):
            g = int(rng.random() < share)
            filas.append({"barrio": barrio, "superficie_rango": sup, "tipo_familia": "departamento", "grupo": g,
                          "m2": nivel * (1.2 if g else 1.0) * np.exp(rng.normal(0, 0.1))})
for i in range(6):  # barrios extra, para que el error agrupado tenga grupos
    for _ in range(100):
        g = int(rng.random() < 0.4)
        filas.append({"barrio": f"b{i}", "superficie_rango": "36-55", "tipo_familia": "departamento", "grupo": g,
                      "m2": 2000 * (1.2 if g else 1.0) * np.exp(rng.normal(0, 0.1))})
p = pd.DataFrame(filas)
pr = SI.prima_en_celda(p, "m2", "grupo", referencia=0)
check("prima en la celda: recupera la prima plantada de 20%", abs(pr.loc[1, "prima_pct"] - 20) < 2,
      f"{pr.loc[1, 'prima_pct']:.2f}")
check("prima en la celda: el intervalo la contiene", pr.loc[1, "ic_inf"] < 20 < pr.loc[1, "ic_sup"])
ingenua = (p[p.grupo == 1]["m2"].median() / p[p.grupo == 0]["m2"].median() - 1) * 100
check("NEG: sin la celda, la prima se infla con el barrio", ingenua > 35, f"{ingenua:.1f}%")


print(f"Tests corridos : {corridos}")
print(f"Fallos         : {len(fallos)}")
if fallos:
    print()
    for f in fallos:
        print(f"  FALLO: {f}")
    sys.exit(1)
print("OK")
sys.exit(0)
