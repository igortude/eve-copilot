# -*- coding: utf-8 -*-
"""
Training System (manual, seções 17, 18 e 19): exercícios, perguntas conceituais (Training Mode),
After Action Review, histórico do piloto e detecção de padrões.

O AAR NUNCA afirma causas sem evidência: só aponta o que os dados informados sustentam e usa
linguagem de possibilidade ("possível consequência").
"""
import time

from . import load_json, save_json, UNKNOWN
from .engine import thresholds, SHORT_RANGE_FAMILIES
from .enemies import lookup

HISTORY_FILE = "pilot_history.json"

# --------------------------------------------------------------------------- #
# Exercícios (seção 17)
# --------------------------------------------------------------------------- #
EXERCISES = [
    {"id": "range_control", "title": "Range Control", "level": "Iniciante", "tag": "perdeu_range",
     "objective": "Manter um alvo entre 4 e 6 km por 2 minutos.",
     "steps": ["Escolha um alvo NPC fraco.", "Ative propulsão e use Keep at Range em 5 km.",
               "Observe a distância no Overview e corrija o rumo manualmente quando passar de 6 km ou cair abaixo de 4 km."],
     "success": "Distância dentro da faixa pelo menos 80% do tempo.", "why": "Controle de distância define quem aplica dano."},
    {"id": "orbit", "title": "Orbit", "level": "Iniciante", "tag": "tracking",
     "objective": "Entender o efeito do Orbit na velocidade angular e no seu tracking.",
     "steps": ["Orbite um alvo a 2 km e observe acertos/erros.", "Repita a 5 km e compare.",
               "Anote em qual distância seus lasers erram menos."],
     "success": "Você explica por que a mudança de raio alterou os acertos.", "why": "Orbit ajuda a defender, mas pode piorar o seu tracking."},
    {"id": "keep_at_range", "title": "Keep at Range", "level": "Iniciante", "tag": "perdeu_range",
     "objective": "Perceber que KAR não garante manter a distância.",
     "steps": ["Use KAR em 4 km contra um alvo que se move.", "Anote quando o alvo conseguiu ficar mais perto/longe.",
               "Troque para pilotagem manual e compare."],
     "success": "Identifica ao menos 2 situações em que KAR falhou.", "why": "KAR tenta, não garante."},
    {"id": "manual_piloting", "title": "Pilotagem manual", "level": "Intermediário", "tag": "perdeu_range",
     "objective": "Controlar ângulo e distância sem comandos automáticos.",
     "steps": ["Pratique movimento lateral e aproximação em ângulo.", "Corrija a trajetória quando o alvo mudar de direção.",
               "Aumente/reduza velocidade angular de propósito e veja o efeito nos acertos."],
     "success": "Mantém a distância-alvo sem usar Orbit/KAR por 1 minuto.", "why": "Base para vencer kiters e controlar range."},
    {"id": "tracking", "title": "Tracking", "level": "Intermediário", "tag": "tracking",
     "objective": "Relacionar velocidade angular, tracking e erros dos lasers.",
     "steps": ["Observe seu combat log (aba Combat Log) por erros.", "Reduza a velocidade angular e compare a taxa de acertos.",
               "Registre a distância em que os erros aumentam."],
     "success": "Taxa de acerto sobe ao ajustar a trajetória.", "why": "DPS nominal ≠ dano aplicado."},
    {"id": "overheating", "title": "Overheating", "level": "Intermediário", "tag": "cap",
     "objective": "Usar overheat só quando necessário e entender o desgaste.",
     "steps": ["Ative overheat em um módulo relevante durante uma luta curta.", "Desative antes do módulo queimar.",
               "Anote o ganho e o risco."],
     "success": "Overheat usado em momento decisivo sem queimar módulos.", "why": "Ganho temporário com custo de módulo."},
    {"id": "capacitor", "title": "Gerenciamento de capacitor", "level": "Iniciante", "tag": "cap",
     "objective": "Terminar uma luta sem zerar o capacitor.",
     "steps": ["Observe o capacitor durante uma luta.", "Desligue módulos não essenciais quando baixar.",
               "Evite ciclos desnecessários do reparador."],
     "success": "Capacitor não zera durante a luta.", "why": "Sem capacitor, nenhum módulo ativo funciona."},
    {"id": "tackle", "title": "Tackle", "level": "Iniciante", "tag": "tackle_escape",
     "objective": "Aplicar scrambler e webifier no momento certo e dentro do alcance.",
     "steps": ["Aproxime-se até o alcance do tackle.", "Ative scrambler primeiro, depois webifier.",
               "Confirme os ícones de efeito no alvo."],
     "success": "Alvo preso antes de ele sair da distância.", "why": "Tackle é o que impede o alvo de escapar."},
    {"id": "dscan", "title": "D-Scan", "level": "Iniciante", "tag": "numeros",
     "objective": "Ler o D-Scan antes de entrar num complexo.",
     "steps": ["Faça scan 360° em alcance amplo.", "Conte naves de combate por classe.", "Decida entrar ou sair e registre o motivo."],
     "success": "Decisão tomada com base na contagem de naves.", "why": "Evita emboscadas."},
    {"id": "ship_recognition", "title": "Reconhecimento de naves", "level": "Iniciante", "tag": "sem_dados",
     "objective": "Identificar a classe e armas prováveis de 10 naves no Overview.",
     "steps": ["Abra o Enemy Analyzer (aba Tactics).", "Compare a hipótese com o dano que você realmente recebe.",
               "Anote quando a hipótese estava errada."],
     "success": "Acerta a classe de 9 em 10 e entende que fittings variam.", "why": "Modelo da nave ≠ fitting."},
]
EXERCISE_BY_TAG = {}
for _e in EXERCISES:
    EXERCISE_BY_TAG.setdefault(_e["tag"], _e)

# --------------------------------------------------------------------------- #
# Training Mode — base conceitual offline (seção 17 e 23)
# --------------------------------------------------------------------------- #
CONCEPTS = [
    {"keys": ["orbit", "orbitar", "cruiser"],
     "title": "Por que orbitar uma cruiser?",
     "answer": ("Orbit pode aumentar sua velocidade angular em relação à cruiser. Se ela utilizar torretas médias com tracking "
                "insuficiente, isso poderá reduzir o dano recebido. Entretanto, drones, webifiers, neutralizadores e mísseis "
                "podem continuar sendo perigosos.")},
    {"keys": ["keep at range", "kar", "manter distância", "4 km"],
     "title": "Por que manter 4 km?",
     "answer": ("4 km é uma referência inicial para a Tormentor: longe o bastante para reduzir o dano de armas de curto alcance "
                "e perto o bastante para aplicar dano com lasers e prender com scrambler. A distância exata depende do alcance "
                "efetivo dos seus cristais — confirme o Optimal Range real.")},
    {"keys": ["orbitar a 2", "2 km", "orbit 2"],
     "title": "Por que orbitar a 2 km?",
     "answer": ("Órbitas curtas elevam a velocidade angular, o que atrapalha torretas com tracking fraco — mas também reduz a "
                "aplicação das suas próprias armas e não ajuda contra mísseis/drones. Só faz sentido se você ainda aplicar dano.")},
    {"keys": ["lateral", "movimento lateral"],
     "title": "Quando o movimento lateral ajuda?",
     "answer": ("Quando você precisa criar velocidade transversal (para reduzir o dano de torretas) ou ajustar o ângulo de aproximação. "
                "Não ajuda tanto contra mísseis/foguetes, cuja aplicação depende de velocidade e assinatura.")},
    {"keys": ["errando", "erram", "lasers", "tracking"],
     "title": "Por que meus lasers estão errando?",
     "answer": ("Provavelmente a velocidade angular está alta demais para o tracking, ou você está fora do optimal/falloff. "
                "Reduza a velocidade angular (aponte mais direto), ajuste a distância ou troque os cristais.")},
    {"keys": ["acerta", "rápido", "mesmo eu"],
     "title": "Por que meu inimigo consegue me acertar mesmo eu estando rápido?",
     "answer": ("Velocidade da nave não é velocidade angular: se você se move em linha reta em direção/afastando-se do alvo, a angular é baixa. "
                "Além disso, mísseis e drones ignoram tracking, e webifiers reduzem sua velocidade.")},
    {"keys": ["dps", "nominal", "destruindo"],
     "title": "Por que meu DPS nominal não está destruindo o alvo?",
     "answer": ("DPS nominal é teórico. O dano aplicado depende de distância (optimal/falloff), tracking, assinatura do alvo e resistências. "
                "Use a aba Tactics → Weapon Application para comparar.")},
    {"keys": ["cristal", "trocar", "multifrequency", "standard", "radio"],
     "title": "Quando devo trocar os cristais?",
     "answer": ("Quando a distância de combate mudar de faixa: Multifrequency (mais dano, menos alcance) para curta, Standard para média, "
                "Radio (mais alcance, menos dano) para longa. Confirme os alcances reais com suas habilidades.")},
    {"keys": ["fugir", "retirada", "retirar"],
     "title": "Quando devo fugir?",
     "answer": ("Quando perder o controle da distância sem recuperar, com capacitor crítico, com superioridade numérica, ou quando seu dano "
                "aplicado não reduzir o tank dele. Retirar também é decisão tática.")},
    {"keys": ["kar", "orbit", "diferença", "versus", "vs"],
     "title": "KAR vs Orbit",
     "answer": ("KAR tenta manter a distância escolhida e gera trajetórias mais retas (bom para tracking próprio). Orbit mantém trajetória circular "
                "e eleva a velocidade angular (defesa contra torretas), mas atrapalha seu tracking. Nenhum é automático/ideal.")},
]


def answer_concept(question: str) -> dict | None:
    q = (question or "").lower()
    best, best_score = None, 0
    for c in CONCEPTS:
        score = sum(1 for k in c["keys"] if k in q)
        if score > best_score:
            best, best_score = c, score
    return best


# --------------------------------------------------------------------------- #
# Histórico e evolução (seção 19)
# --------------------------------------------------------------------------- #
PROBLEM_LABELS = {
    "perdeu_range": "Perda de controle de distância",
    "tracking": "Tracking ineficiente",
    "cap": "Gestão de capacitor",
    "tackle_escape": "Alvo escapou / tackle ineficaz",
    "numeros": "Superioridade numérica / falta de D-Scan",
    "municao": "Munição inadequada à distância",
    "tank_tardio": "Reparador ativado tarde",
    "sem_dados": "Dados insuficientes para concluir",
}


class PilotHistory:
    def __init__(self):
        self.records: list = load_json(HISTORY_FILE, [])

    def add(self, record: dict) -> dict:
        record = dict(record)
        record.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S"))
        record.setdefault("problems", [])
        record.setdefault("skills", [])
        self.records.append(record)
        save_json(HISTORY_FILE, self.records)
        return record

    def clear(self):
        self.records = []
        save_json(HISTORY_FILE, self.records)

    def stats(self) -> dict:
        wins = sum(1 for r in self.records if r.get("result") == "VITÓRIA")
        losses = sum(1 for r in self.records if r.get("result") == "DERROTA")
        problems, skills = {}, set()
        for r in self.records:
            for p in r.get("problems", []):
                problems[p] = problems.get(p, 0) + 1
            skills.update(r.get("skills", []))
        return {
            "combats": len(self.records), "wins": wins, "losses": losses,
            "ships_lost": sum(1 for r in self.records if r.get("ship_lost")),
            "ships_destroyed": sum(1 for r in self.records if r.get("enemy_destroyed")),
            "isk_lost": sum(float(r.get("isk_lost") or 0) for r in self.records),
            "isk_destroyed": sum(float(r.get("isk_destroyed") or 0) for r in self.records),
            "recurring_problems": dict(sorted(problems.items(), key=lambda x: -x[1])),
            "skills_learned": sorted(skills),
        }

    def patterns(self) -> list:
        """Padrões: problema recorrente em ≥2 derrotas e ≥50% das derrotas."""
        losses = [r for r in self.records if r.get("result") == "DERROTA"]
        if len(losses) < 2:
            return []
        counts = {}
        for r in losses:
            for p in set(r.get("problems", [])):
                counts[p] = counts.get(p, 0) + 1
        out = []
        for tag, n in sorted(counts.items(), key=lambda x: -x[1]):
            share = n / len(losses)
            if n >= 2 and share >= 0.5:
                ex = EXERCISE_BY_TAG.get(tag)
                priority = "ALTA" if (n >= 3 or share >= 0.6) else "MÉDIA"
                out.append({"tag": tag, "label": PROBLEM_LABELS.get(tag, tag), "occurrences": n,
                            "of_losses": len(losses), "priority": priority,
                            "training": ex["title"] if ex else "Revisão geral",
                            "text": (f"PADRÃO IDENTIFICADO:\n\n{PROBLEM_LABELS.get(tag, tag)} em {n} de {len(losses)} derrotas.\n\n"
                                     f"TREINAMENTO RECOMENDADO:\n\n{ex['title'] if ex else 'Revisão geral'}\n\nPrioridade: {priority}")})
        return out


# --------------------------------------------------------------------------- #
# After Action Review (seção 18)
# --------------------------------------------------------------------------- #
def after_action_review(data: dict, profile: dict | None = None) -> dict:
    """
    data: ship, enemy, result, initial_distance_m, min_distance_m, planned_range_m, ammo, modules,
          problems_text, cap_zero(bool), repair_late(bool), enemy_weapon, killmail(dict|None)
    Só afirma o que os dados sustentam.
    """
    p = profile or {}
    t = thresholds(p)
    result = (data.get("result") or UNKNOWN).upper()
    ship, enemy = data.get("ship") or UNKNOWN, data.get("enemy") or UNKNOWN
    info = lookup(enemy)
    modules = (data.get("modules") or "").lower()
    ammo = (data.get("ammo") or "").lower()
    ptxt = (data.get("problems_text") or "").lower()
    evidence, tags, consequences, improvements = [], [], [], []

    planned = data.get("planned_range_m")
    mn = data.get("min_distance_m")
    weapon = data.get("enemy_weapon") or (info["weapons"][0] if info and len(info["weapons"]) == 1 else None)
    short_enemy = bool(weapon in SHORT_RANGE_FAMILIES) if weapon else False

    if mn is not None and planned and mn < planned * t["range_lost_ratio"] and result in ("DERROTA", "FUGA"):
        evidence.append(f"O adversário reduziu a distância para {int(mn)} m (planejado: {int(planned)} m).")
        tags.append("perdeu_range")
        if short_enemy:
            consequences.append("Armas de curto alcance adversárias podem ter aplicado dano elevado a essa distância.")
        else:
            consequences.append("Perder o controle da distância pode ter favorecido a aplicação de dano do adversário (arma não confirmada).")
        improvements.append("Treinar controle de distância com AB + Webifier.")
    if "radio" in ammo and mn is not None and mn < (p.get("ammo_bands_m") or {}).get("multifrequency_max", 4000):
        evidence.append("Cristal de longo alcance (Radio) usado a distância curta registrada.")
        tags.append("municao")
        consequences.append("Dano aplicado menor que o possível com cristal de curto alcance.")
        improvements.append("Revisar a escolha de cristal por faixa de distância (Ammo Advisor).")
    if data.get("cap_zero"):
        evidence.append("Você informou que o capacitor zerou.")
        tags.append("cap")
        consequences.append("Sem capacitor, módulos ativos (tackle, reparador, lasers) param.")
        improvements.append("Treinar gerenciamento de capacitor e ciclos do reparador.")
    if data.get("repair_late"):
        evidence.append("Você informou que o reparador foi ativado tarde.")
        tags.append("tank_tardio")
        improvements.append("Ativar o reparador no limite configurado, não em armadura crítica.")
    if result in ("DERROTA", "FUGA") and modules and not any(k in modules for k in ("scrambler", "disruptor")):
        evidence.append("Nenhum scrambler/disruptor consta nos módulos usados informados.")
        tags.append("tackle_escape")
        consequences.append("Possível dificuldade em prender o alvo ou impedir escapes.")
    km = data.get("killmail")
    if km:
        att = km.get("attackers_count")
        if att and att >= 2:
            evidence.append(f"O killmail mostra {att} atacantes.")
            tags.append("numeros")
            consequences.append("Superioridade numérica pode ter sido decisiva.")
            improvements.append("Treinar uso de D-Scan antes de entrar em complexos.")
    keyword_tags = {"perdi range": "perdeu_range", "range": "perdeu_range", "tracking": "tracking", "errando": "tracking",
                    "capacitor": "cap", "cap ": "cap", "neut": "cap", "escapou": "tackle_escape", "fugiu": "tackle_escape",
                    "muitos": "numeros", "gang": "numeros", "munição": "municao", "cristal": "municao"}
    for kw, tag in keyword_tags.items():
        if kw in ptxt and tag not in tags:
            tags.append(tag)
            evidence.append(f"Você relatou: \"{kw.strip()}\".")

    tags = list(dict.fromkeys(tags))
    if not evidence:
        tags = ["sem_dados"] if result in ("DERROTA", "FUGA") else tags
        evidence = ["Evidência insuficiente para afirmar causas."]
        improvements.append("Registre distância inicial/mínima, munição, módulos e killmail para uma análise melhor.")

    first_tag = next((t for t in tags if t in EXERCISE_BY_TAG), None)
    ex = EXERCISE_BY_TAG.get(first_tag) if first_tag else None
    next_ex = ex["objective"] if ex else "Repetir o combate registrando mais dados."

    lines = [
        f"RESULTADO: {result}", "", f"NAVE: {ship}", f"INIMIGO: {enemy}", "",
        "PROBLEMA IDENTIFICADO:", *[f"- {e}" for e in evidence], "",
        "POSSÍVEL CONSEQUÊNCIA:", *([f"- {c}" for c in consequences] or ["- Não afirmável com os dados atuais."]), "",
        "MELHORIA:", *([f"- {i}" for i in improvements] or ["- —"]), "",
        "PRÓXIMO EXERCÍCIO:", next_ex,
    ]
    return {"text": "\n".join(lines), "tags": tags, "exercise": ex, "evidence": evidence}
