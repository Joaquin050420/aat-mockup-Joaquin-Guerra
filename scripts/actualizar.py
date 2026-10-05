"""Calcula los pronósticos de Cuarta y Corta.

Uso:
    python3 scripts/actualizar.py

Lee:
    data/entrada.json     datos crudos de la semana (partidos, momios, lesiones, descanso)
    data/resultados.json  (opcional) marcadores finales de la semana anterior
Escribe:
    data/semana.json      lo que muestra la página
    data/historial.json   aciertos acumulados (se califica la semana anterior)

Modelo (transparente a propósito):
  1. Base = probabilidad del mercado: moneyline actual sin la comisión de la casa.
  2. Lesiones: cada titular con estatus Out / Doubtful / Questionable resta
     probabilidad a su equipo según posición y estatus. Se aplica a la mitad (x0.5)
     porque el mercado ya descuenta parte de las lesiones conocidas.
     Injured Reserve no ajusta: es una baja larga que la línea ya refleja.
  3. Descanso: +1 punto por cada día de ventaja de descanso arriba de 1, máximo 3.
  Ajuste total máximo: ±8 puntos. "Valor" cuando el modelo se separa ≥3 puntos del mercado.
"""
import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"

PESOS = {  # puntos de probabilidad por titular, antes del factor de mercado
    "QB": {"Out": 6.0, "Doubtful": 4.5, "Questionable": 1.5},
    "ALTO": {"Out": 1.2, "Doubtful": 0.9, "Questionable": 0.3},   # RB WR TE OL EDGE CB
    "MEDIO": {"Out": 0.8, "Doubtful": 0.6, "Questionable": 0.2},  # DL LB S
    "K": {"Out": 1.0, "Doubtful": 0.7, "Questionable": 0.2},
}
GRUPO = {"QB": "QB", "RB": "ALTO", "WR": "ALTO", "TE": "ALTO", "OL": "ALTO", "EDGE": "ALTO",
         "CB": "ALTO", "DL": "MEDIO", "LB": "MEDIO", "S": "MEDIO", "K": "K"}
FACTOR_MERCADO = 0.5
TOPE_AJUSTE = 8.0
UMBRAL_VALOR = 3.0

ESTATUS_ES = {"Out": "fuera", "Doubtful": "en duda seria", "Questionable": "en duda"}
POS_ES = {"QB": "QB", "RB": "corredor", "WR": "receptor", "TE": "ala cerrada", "OL": "linier ofensivo",
          "EDGE": "pass rusher", "CB": "esquinero", "DL": "linier defensivo", "LB": "apoyador",
          "S": "safety", "K": "pateador"}


def implicita(ml):
    ml = float(ml)
    return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)


def sin_comision(ml_local, ml_visit):
    a, b = implicita(ml_local), implicita(ml_visit)
    return a / (a + b) * 100


def fecha(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def calcular(entrada):
    partidos = []
    for p in entrada["partidos"]:
        loc, vis = p["local"], p["visitante"]
        mercado = sin_comision(p["ml_local"], p["ml_visitante"])
        apertura = (sin_comision(p["ml_local_apertura"], p["ml_visitante_apertura"])
                    if p.get("ml_local_apertura") is not None else mercado)
        factores, ajuste = [], 0.0

        for equipo, signo in ((loc, -1), (vis, +1)):  # baja del local resta al local
            for les in p.get("lesiones", {}).get(equipo, []):
                g = GRUPO.get(les["pos"])
                if not les.get("titular") or g is None or les["estatus"] not in PESOS[g]:
                    continue
                pts = PESOS[g][les["estatus"]] * FACTOR_MERCADO * signo
                ajuste += pts
                factores.append({
                    "texto": f'{les["jugador"]} ({POS_ES[les["pos"]]}, {equipo}) {ESTATUS_ES[les["estatus"]]}',
                    "puntos": round(pts, 1)})

        juego = fecha(p["fecha_utc"])
        ult = entrada.get("ultimo_partido", {})
        if loc in ult and vis in ult:
            d_loc = (juego - fecha(ult[loc])).total_seconds() / 86400
            d_vis = (juego - fecha(ult[vis])).total_seconds() / 86400
            dif = d_loc - d_vis
            if abs(dif) >= 1.5:
                pts = max(-3.0, min(3.0, (abs(dif) - 1))) * (1 if dif > 0 else -1)
                ajuste += pts
                quien = loc if dif > 0 else vis
                factores.append({"texto": f"{quien} llega con {round(abs(dif))} días más de descanso",
                                 "puntos": round(pts, 1)})

        ajuste = max(-TOPE_AJUSTE, min(TOPE_AJUSTE, ajuste))
        modelo = max(1.0, min(99.0, mercado + ajuste))
        movimiento = mercado - apertura
        if abs(movimiento) >= 2:
            hacia = loc if movimiento > 0 else vis
            factores.append({"texto": f"La línea se movió hacia {hacia} desde que abrió",
                             "puntos": 0, "informativo": True})

        favorito = loc if modelo >= 50 else vis
        valor = None
        if modelo - mercado >= UMBRAL_VALOR:
            valor = loc
        elif mercado - modelo >= UMBRAL_VALOR:
            valor = vis

        factores = [f for f in factores if f.get("informativo") or abs(f["puntos"]) >= 0.3]
        factores.sort(key=lambda f: -abs(f["puntos"]))
        partidos.append({
            "id": p["id"], "fecha_utc": p["fecha_utc"], "local": loc, "visitante": vis,
            "estadio": p.get("estadio"), "ciudad": p.get("ciudad"), "neutral": p.get("neutral", False),
            "record_local": entrada.get("records", {}).get(loc),
            "record_visitante": entrada.get("records", {}).get(vis),
            "spread_local": p.get("spread_local"), "spread_local_apertura": p.get("spread_local_apertura"),
            "over_under": p.get("over_under"),
            "prob_mercado_local": round(mercado, 1), "prob_apertura_local": round(apertura, 1),
            "prob_modelo_local": round(modelo, 1), "ajuste_local": round(ajuste, 1),
            "favorito": favorito, "valor": valor, "factores": factores[:5],
        })
    partidos.sort(key=lambda x: x["fecha_utc"])
    return {"temporada": entrada["temporada"], "semana": entrada["semana"],
            "actualizado": entrada["actualizado"], "descansan": entrada.get("descansan", []),
            "partidos": partidos, "fuentes": entrada.get("fuentes", [])}


def calificar(anterior, resultados, historial):
    """Compara el favorito del modelo de la semana anterior contra el ganador real."""
    if not anterior or not resultados or resultados.get("semana") != anterior.get("semana"):
        return historial
    if any(s["semana"] == anterior["semana"] and s["temporada"] == anterior["temporada"]
           for s in historial["semanas"]):
        return historial  # ya calificada
    marc = {r["id"]: r for r in resultados["resultados"]}
    aciertos = jugados = 0
    detalle = []
    for p in anterior["partidos"]:
        r = marc.get(p["id"])
        if not r or r["puntos_local"] == r["puntos_visitante"]:
            continue
        ganador = p["local"] if r["puntos_local"] > r["puntos_visitante"] else p["visitante"]
        ok = ganador == p["favorito"]
        jugados += 1
        aciertos += ok
        detalle.append({"partido": f'{p["visitante"]} @ {p["local"]}', "pronostico": p["favorito"],
                        "ganador": ganador, "acierto": ok})
    historial["semanas"].append({"temporada": anterior["temporada"], "semana": anterior["semana"],
                                 "aciertos": aciertos, "jugados": jugados, "detalle": detalle})
    historial["aciertos"] = sum(s["aciertos"] for s in historial["semanas"])
    historial["jugados"] = sum(s["jugados"] for s in historial["semanas"])
    return historial


def leer(nombre, defecto=None):
    f = DATA / nombre
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else defecto


def main():
    entrada = leer("entrada.json")
    anterior = leer("semana.json")
    historial = leer("historial.json", {"desde": "Semana 5, 2026", "aciertos": 0, "jugados": 0, "semanas": []})
    historial = calificar(anterior, leer("resultados.json"), historial)
    nueva = calcular(entrada)
    (DATA / "semana.json").write_text(json.dumps(nueva, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA / "historial.json").write_text(json.dumps(historial, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f'Semana {nueva["semana"]}: {len(nueva["partidos"])} partidos. '
          f'Historial: {historial["aciertos"]}/{historial["jugados"]}')


if __name__ == "__main__":
    main()
