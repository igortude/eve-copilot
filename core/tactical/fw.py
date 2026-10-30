# -*- coding: utf-8 -*-
"""
Faction Warfare Assistant (manual, seção 13) + D-Scan Advisor + Capture Advisor.

As regras de FW mudam ao longo do tempo. As restrições abaixo são TENDÊNCIAS gerais e sempre
vêm com o aviso "verifique a mensagem de entrada do complexo no jogo". O sistema não presume que um
complexo é exclusivo para fragatas só por aparecer na zona de guerra.
"""
import re

from .enemies import lookup, CLASS_RANK

ACTIVITY_KINDS = {
    "Complexos de captura (plexes)": ("Complexos em sistemas contestados. Ocupar com naves da sua milícia altera a contestação do sistema. "
                                       "Têm restrição de tamanho de nave na entrada."),
    "Missões de agentes FW": ("Missões de agentes da sua milícia. Fonte de Loyalty Points (LP) e reputação. "
                              "Não é o mesmo que capturar complexo."),
    "Pirate Insurgencies": ("Atividade de insurgência pirata em sistemas de fronteira, separada dos complexos de captura. "
                            "Mecânicas e recompensas próprias."),
    "Outras atividades PvE": ("Anomalias, missões e sinais comuns — não fazem parte da captura de FW, ainda que ocorram na zona de guerra."),
}

COMPLEX_TYPES = {
    "Novice": {"tendencia": "Naves menores (fragatas; verifique destroyers).", "max_rank": 1},
    "Small": {"tendencia": "Fragatas e destroyers (verifique cruisers).", "max_rank": 2},
    "Medium": {"tendencia": "Até cruisers (verifique battlecruisers).", "max_rank": 3},
    "Large": {"tendencia": "Naves maiores (verifique limite exato).", "max_rank": 4},
}

VERIFY = ("VERIFIQUE: leia o texto de restrição exibido no acceleration gate do complexo. "
          "Regras da CCP podem ter mudado.")


def explain_complex(kind: str) -> str:
    c = COMPLEX_TYPES.get(kind)
    if not c:
        return "Tipo de complexo desconhecido."
    return f"{kind}: {c['tendencia']} {VERIFY}"


def check_entry(complex_kind: str, ship_class: str) -> dict:
    """Probabilidade de entrada permitida — sempre como TENDÊNCIA com aviso de verificação."""
    c = COMPLEX_TYPES.get(complex_kind)
    rank = CLASS_RANK.get(ship_class)
    if not c or not rank:
        return {"verdict": "DESCONHECIDO", "message": "Informe tipo de complexo e classe da nave. " + VERIFY}
    if rank <= c["max_rank"]:
        verdict = "PROVAVELMENTE PERMITIDO"
    else:
        verdict = "PROVAVELMENTE RESTRITO"
    return {"verdict": verdict, "message": f"{explain_complex(complex_kind)}"}


def recommend_complexes(ship_class: str, enemy_presence: str = "desconhecida") -> list:
    """Recomenda tipos de complexo adequados à nave atual (sem exclusividade presumida)."""
    rank = CLASS_RANK.get(ship_class, 1)
    out = []
    for kind, c in COMPLEX_TYPES.items():
        fit = rank <= c["max_rank"]
        if kind == "Novice" and rank == 1:
            reason = "Complexo menor combina com fragata e tende a atrair menos naves grandes."
        elif fit:
            reason = "Sua nave provavelmente entra, mas complexos maiores podem atrair naves maiores/mais pilotos."
        else:
            reason = "Sua nave provavelmente excede a restrição deste tipo."
        out.append({"type": kind, "fit": fit, "reason": reason, "verify": VERIFY})
    if enemy_presence in ("alta", "múltiplos"):
        out.append({"type": "AVISO", "fit": None,
                    "reason": "Há risco de múltiplos inimigos: avalie desistir da captura em vez de insistir.", "verify": ""})
    return out


LP_EXPLANATION = (
    "Loyalty Points (LP): pontos ganhos pela sua milícia ao participar de FW (ex.: concluir/capturar complexos, missões "
    "de agente, abates de inimigos da milícia adversária). São gastos na Loja de LP da sua milícia. "
    "Valores e fontes mudam — consulte o jogo/loja para números atuais."
)

CAPTURE_DEFENSE = [
    "Capturar (offense): ocupar complexos em sistemas contestados com naves da sua milícia empurra a contestação do sistema a seu favor.",
    "Defender: ocupar complexos no seu sistema contra o avanço inimigo ajuda a manter/retomar a contestação.",
    "Não presuma segurança: quem ocupa o complexo fica visível/previsível e atrai combate.",
    "Se aparecerem múltiplos inimigos, decida entre manter a captura ou sair — o complexo não vale a nave.",
]

NPC_GUIDANCE = [
    "Aliados e hostis: confie nos ícones de standing do Overview (azul/neutro/vermelho), não no nome da nave.",
    "Não presuma que NPCs com nome da sua milícia são todos aliados em todos os complexos — verifique o standing de cada um.",
    "Configure filtros de Overview separando jogadores, NPCs hostis e aliados antes de entrar.",
]

DSCAN_ROUTINE = [
    "1. Faça um scan 360° em alcance amplo ao chegar no sistema/complexo.",
    "2. Conte naves de combate por classe; ignore estruturas e itens.",
    "3. Procure sondas de combate/scanner (Combat Scanner Probe) — indicam caçadores.",
    "4. Repita o scan a cada ciclo de captura (as coisas mudam rápido).",
    "5. Se o número de naves de combate hostis superar o que você pode lidar solo, saia antes de entrar no complexo.",
]


def parse_dscan(text: str) -> dict:
    """
    Interpreta o texto copiado da janela D-Scan (colunas separadas por TAB: id, nome, tipo, distância).
    Retorna contagem por tipo e por classe conhecida (a partir da base interna) + alertas.
    """
    counts, by_class, unknown = {}, {}, {}
    probes = 0
    for raw in (text or "").splitlines():
        parts = [p.strip() for p in raw.split("\t")]
        if len(parts) >= 3:
            ship_type = parts[2]
        elif parts and parts[0]:
            ship_type = parts[0]
        else:
            continue
        counts[ship_type] = counts.get(ship_type, 0) + 1
        if "probe" in ship_type.lower():
            probes += 1
            continue
        info = lookup(ship_type)
        if info:
            by_class[info["class"]] = by_class.get(info["class"], 0) + 1
        else:
            unknown[ship_type] = unknown.get(ship_type, 0) + 1
    combat = sum(by_class.values())
    alerts = []
    if probes:
        alerts.append(f"{probes} sonda(s) de scanner detectada(s): possível caçador/scan em andamento.")
    if combat >= 3:
        alerts.append(f"{combat} naves de combate conhecidas no D-Scan: risco de múltiplos inimigos.")
    elif combat == 2:
        alerts.append("2 naves de combate conhecidas: possível superioridade numérica.")
    return {"counts": counts, "by_class": by_class, "unknown": unknown, "probes": probes,
            "alerts": alerts,
            "note": "O D-Scan mostra o que está no alcance, não quem é hostil nem a distância exata."}
