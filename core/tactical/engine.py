# -*- coding: utf-8 -*-
"""
Tactical Engine (manual, seções 6–12 e 15):
  Engagement Risk Analyzer, Range Control Advisor, Combat Decision Engine,
  Weapon Application Analyzer, Ammo Advisor, Capacitor Advisor, Armor Repair Advisor, alertas táticos.

Regras de honestidade:
  * Entradas ausentes => saída PENDENTE/DESCONHECIDO (nunca valores inventados).
  * Nenhum percentual de vitória é produzido.
  * O módulo RECOMENDA — não executa nada no cliente do jogo.
"""
import math

from . import UNKNOWN, PENDING, fmt_m
from .enemies import lookup, WEAPON_FAMILIES, CLASS_RANK
from .ships import recommended_range_m

SHORT_RANGE_FAMILIES = {"blaster", "autocannon", "pulse_laser", "rocket"}
MISSILE_FAMILIES = {"rocket", "light_missile"}
TURRET_FAMILIES = {"blaster", "railgun", "autocannon", "artillery", "pulse_laser", "beam_laser"}

DEFAULT_THRESHOLDS = {
    "cap_low_pct": 35, "cap_critical_pct": 15, "armor_repair_start_pct": 70,
    "paste_low_count": 20, "range_lost_ratio": 0.75, "miss_ratio_alert": 0.6, "miss_min_shots": 8,
}


def thresholds(profile: dict | None) -> dict:
    t = dict(DEFAULT_THRESHOLDS)
    t.update(((profile or {}).get("thresholds")) or {})
    return t


# --------------------------------------------------------------------------- #
# Física básica / aplicação de armas (seção 9)
# --------------------------------------------------------------------------- #
def angular_velocity(transversal_ms: float, distance_m: float) -> float | None:
    """Velocidade angular (rad/s) = transversal / distância."""
    if not distance_m or distance_m <= 0:
        return None
    return transversal_ms / distance_m


def orbit_angular_velocity(speed_ms: float, radius_m: float) -> float | None:
    """Órbita circular na velocidade máxima: ω = v / r (aproximação do melhor caso)."""
    return angular_velocity(speed_ms, radius_m)


def weapon_application(optimal_m=None, falloff_m=None, tracking_rad_s=None, sig_res_m=None,
                       target_sig_m=None, distance_m=None, transversal_ms=None, angular_rad_s=None,
                       nominal_dps=None) -> dict:
    """
    DPS teórico vs. dano efetivamente aplicado (torretas).
    chance = 0.5 ^ ( (ω·sigRes / (tracking·sigAlvo))² + (max(0, d − optimal)/falloff)² )
    dano médio por tiro ≈ (chance² + chance + 0.0498) / 2  (modelo padrão da comunidade).
    Se faltar qualquer dado necessário -> PENDENTE, listando o que falta.
    """
    missing = []
    for label, val in (("Optimal Range", optimal_m), ("Falloff", falloff_m), ("Tracking", tracking_rad_s),
                       ("Signature Resolution da arma", sig_res_m), ("Assinatura do alvo", target_sig_m),
                       ("Distância", distance_m)):
        if val in (None, ""):
            missing.append(label)
    omega = angular_rad_s
    if omega is None and transversal_ms is not None and distance_m:
        omega = transversal_ms / distance_m
    if omega is None:
        missing.append("Velocidade angular (ou transversal)")
    if missing:
        return {"status": PENDING, "missing": missing,
                "message": "Dados insuficientes: " + ", ".join(missing) + ". Nenhum valor foi estimado."}

    d = float(distance_m)
    range_term = 0.0
    if d > optimal_m:
        if not falloff_m or falloff_m <= 0:
            range_term = float("inf")
        else:
            range_term = (d - optimal_m) / falloff_m
    track_term = (omega * sig_res_m / (tracking_rad_s * target_sig_m)) ** 2
    exponent = track_term + (range_term ** 2 if range_term != float("inf") else float("inf"))
    chance = 0.0 if exponent == float("inf") else 0.5 ** exponent
    avg_mult = (chance ** 2 + chance + 0.0498) / 2.0 if chance > 0 else 0.0

    reasons = []
    if range_term and range_term > 0.5:
        reasons.append(f"Fora do optimal ({fmt_m(d)} vs {fmt_m(optimal_m)}): penalidade de falloff.")
    if track_term > 0.5:
        reasons.append("Velocidade angular alta em relação ao tracking: lasers/torretas tendem a errar.")
    if not reasons:
        reasons.append("Aplicação próxima do ideal nesta distância e velocidade angular.")

    result = {
        "status": "OK", "chance_to_hit": chance, "avg_damage_multiplier": avg_mult,
        "angular_rad_s": omega, "tracking_term": track_term, "range_term": range_term,
        "reasons": reasons,
        "message": (f"Chance de acerto ≈ {chance*100:.0f}% · multiplicador médio de dano ≈ {avg_mult*100:.0f}% do nominal."),
    }
    if nominal_dps:
        result["effective_dps"] = float(nominal_dps) * avg_mult
        result["message"] += (f" DPS nominal {nominal_dps:.0f} → efetivo ≈ {result['effective_dps']:.0f} "
                              "(DPS teórico ≠ dano aplicado).")
    return result


# --------------------------------------------------------------------------- #
# Janela de distância (seção 8, cenário A)
# --------------------------------------------------------------------------- #
def distance_window(profile: dict) -> dict:
    rec = recommended_range_m(profile)
    ws = (profile or {}).get("weapon_stats") or {}
    opt, fall, scram = ws.get("optimal_m"), ws.get("falloff_m"), ws.get("scram_range_m")
    ref = (profile or {}).get("reference_range_window_m")
    lo = rec["value"]
    hi, notes, source = None, [], rec["source"]

    if opt and fall:
        hi = float(opt) + 0.5 * float(fall)
        if scram and any(("scrambler" in t.lower() or "disruptor" in t.lower()) for t in profile.get("tackle", [])):
            hi = min(hi, float(scram) * 0.9)
        notes.append("Limite superior calculado pelo optimal+½ falloff da arma (e alcance do tackle).")
    elif ref and len(ref) == 2:
        hi = float(ref[1])
        lo = lo if lo else float(ref[0])
        source = "manual"
        notes.append("Janela de referência do manual — confirme o Optimal Range real com as habilidades atuais.")
    if lo and hi and hi < lo:
        hi = lo
    if lo is None:
        notes.append("Alcance PENDENTE: informe optimal/falloff/alcance do scrambler no Ship Manager.")
    if opt and ref and len(ref) == 2 and float(ref[1]) > float(opt) + 0.5 * float(fall or 0):
        notes.append(f"Não recomendar {fmt_m(ref[1])}: o alcance efetivo informado não sustenta aplicação de dano nessa distância.")
    return {"lo": lo, "hi": hi, "source": source, "notes": notes}


def _fmt_window(w: dict) -> str:
    if w["lo"] and w["hi"] and w["hi"] != w["lo"]:
        return f"{fmt_m(w['lo'])} – {fmt_m(w['hi'])}"
    if w["lo"]:
        return f"≥ {fmt_m(w['lo'])} (limite superior PENDENTE)"
    return PENDING


# --------------------------------------------------------------------------- #
# Famílias de armas do inimigo (fato confirmado x hipótese)
# --------------------------------------------------------------------------- #
def enemy_weapon_set(ctx: dict):
    """Retorna (set de famílias, confirmado?)."""
    w = ctx.get("enemy_weapon")
    if w and w in WEAPON_FAMILIES:
        return {w}, True
    info = ctx.get("enemy_info") or lookup(ctx.get("enemy") or "")
    if info:
        return set(info["weapons"]), False
    return set(), False


def _fam_match(fams: set, confirmed: bool, target: set) -> bool:
    """Confirmado: basta interseção. Hipótese: só dispara se TODAS as hipóteses caírem no alvo."""
    if not fams:
        return False
    return bool(fams & target) if confirmed else fams <= target


def _player_caps(profile: dict) -> dict:
    tackle = " ".join(profile.get("tackle", [])).lower()
    prop = (profile.get("propulsion") or "").lower()
    return {
        "has_scram": "scrambler" in tackle or "disruptor" in tackle,
        "has_web": "web" in tackle,
        "has_prop": bool(prop),
        "has_drones": bool(profile.get("drones")),
        "weak_cap": any("capacitor" in w.lower() for w in profile.get("weaknesses", [])),
        "rank": CLASS_RANK.get(profile.get("class_hint", "Frigate"), 1),
    }


# --------------------------------------------------------------------------- #
# Engagement Risk Analyzer (seção 6)
# --------------------------------------------------------------------------- #
def classify_engagement(ctx: dict) -> dict:
    """
    FAVORÁVEL | EQUILIBRADO | DESFAVORÁVEL | DESCONHECIDO.
    Considera: naves, distância, velocidade relativa, armas, alcance, resistências, capacitor,
    tackle, número de adversários e experiência (somente se confiável). Sem percentuais.
    """
    p = ctx.get("player") or {}
    info = ctx.get("enemy_info") or lookup(ctx.get("enemy") or "")
    count = int(ctx.get("enemy_count") or 1)
    caps = _player_caps(p)
    factors, missing, score = [], [], 0

    if not info:
        missing.append("Nave adversária reconhecida")
    fams, confirmed = enemy_weapon_set(ctx)
    if not fams:
        missing.append("Tipo de armas do adversário")
    elif not confirmed:
        missing.append("Armas do adversário confirmadas (hoje só hipótese)")
    if ctx.get("enemy_faster") is None:
        missing.append("Velocidade relativa (adversário mais rápido?)")
    if ctx.get("distance_m") is None:
        missing.append("Distância inicial")
    if ctx.get("enemy_tackle") is None:
        missing.append("Presença de tackle inimigo")
    if ctx.get("resistances_known") is not True:
        missing.append("Resistências (não informadas)")
    if ctx.get("own_cap_pct") is None:
        missing.append("Capacitor atual")

    # Superioridade numérica é informação suficiente por si só
    if count >= 3:
        factors.append(("-", f"{count} adversários: superioridade numérica esmagadora para combate solo."))
        return _risk_result("DESFAVORÁVEL", factors, missing, ctx)
    if count == 2:
        score -= 2
        factors.append(("-", "2 adversários: superioridade numérica."))

    if not info:
        return _risk_result(UNKNOWN, factors or [("?", "Nave adversária não identificada.")], missing, ctx)

    # tamanho
    prank = CLASS_RANK.get(ctx.get("player_class") or p.get("class_hint") or "Frigate", 1)
    erank = CLASS_RANK.get(info["class"], 1)
    if erank > prank:
        score -= 2
        factors.append(("-", f"Adversário de classe maior ({info['class']})."))
    elif erank < prank:
        score += 1
        factors.append(("+", f"Adversário de classe menor ({info['class']})."))

    # armas confirmadas e alcance
    if fams and confirmed:
        if fams & SHORT_RANGE_FAMILIES and not (fams - SHORT_RANGE_FAMILIES) and caps["has_scram"] and caps["has_prop"]:
            score += 1
            factors.append(("+", "Armas de curto alcance confirmadas e você tem propulsão + scrambler para gerir distância."))
        if fams & {"railgun", "artillery", "beam_laser"} and not (fams - {"railgun", "artillery", "beam_laser"}):
            if caps["has_scram"] and caps["has_prop"]:
                factors.append(("?", "Armas de longo alcance confirmadas: você precisará fechar distância."))
            else:
                score -= 1
                factors.append(("-", "Armas de longo alcance e você sem tackle/propulsão claros para fechar."))
    if ctx.get("enemy_faster") is True:
        score -= 1
        factors.append(("-", "Adversário mais rápido: ele tende a controlar a distância."))
    elif ctx.get("enemy_faster") is False:
        score += 1
        factors.append(("+", "Você é mais rápido: maior chance de controlar a distância."))
    if ctx.get("enemy_tackle") is True:
        score -= 1
        factors.append(("-", "Adversário com tackle: dificulta retirada."))
    if ctx.get("enemy_neut") is True and caps["weak_cap"]:
        score -= 1
        factors.append(("-", "Neutralizador inimigo e sua nave sofre com capacitor."))
    cap = ctx.get("own_cap_pct")
    if cap is not None and cap < thresholds(p)["cap_low_pct"]:
        score -= 1
        factors.append(("-", f"Capacitor baixo ({cap:.0f}%)."))
    exp = ctx.get("enemy_experience")  # 'maior' | 'menor' somente se fonte confiável
    if exp == "maior":
        score -= 1
        factors.append(("-", "Adversário mais experiente (fonte confiável informada)."))
    elif exp == "menor":
        score += 1
        factors.append(("+", "Adversário menos experiente (fonte confiável informada)."))

    # decisão: exige informação mínima
    # Informação essencial: armas CONFIRMADAS e relação de velocidade. Sem isso => DESCONHECIDO,
    # exceto quando já há evidência negativa decisiva (ex.: classe maior / superioridade numérica).
    essential_missing = [m for m in missing if m.startswith(("Armas", "Tipo de armas", "Velocidade"))]
    if score <= -2:
        label = "DESFAVORÁVEL"
    elif essential_missing:
        return _risk_result(UNKNOWN, factors, missing, ctx)
    elif score >= 2:
        label = "FAVORÁVEL"
    else:
        label = "EQUILIBRADO"
    return _risk_result(label, factors, missing, ctx)


def _risk_result(label, factors, missing, ctx):
    return {
        "classification": label,
        "factors": factors,
        "missing": missing,
        "disclaimer": "Classificação qualitativa; não há probabilidade de vitória. Revalide a cada mudança no combate.",
    }


# --------------------------------------------------------------------------- #
# Range Control Advisor (seção 7) + Combat Decision Engine (seção 8)
# --------------------------------------------------------------------------- #
MOVEMENT_EXPLANATIONS = {
    "KEEP AT RANGE": ("Keep at Range tenta manter a distância selecionada. NÃO garante que você conseguirá mantê-la. "
                      "Pode produzir trajetórias relativamente diretas, o que facilita a aplicação de dano por algumas torretas."),
    "ORBIT": ("Orbit tenta manter trajetória circular ao redor do alvo. Pode aumentar a velocidade angular e reduzir a "
              "aplicação de algumas torretas inimigas, mas também pode prejudicar o tracking das SUAS armas. "
              "Não deve ser recomendado automaticamente."),
    "APPROACH": "Approach fecha a distância em linha reta; útil para forçar brawl ou contra alvos que mantêm range.",
    "PILOTAGEM MANUAL": ("Pilotagem manual dá controle fino de ângulo e distância: movimento lateral, aproximação em ângulo, "
                         "correção de trajetória, aumento/redução de velocidade angular."),
    "RETIRADA": "Retirada: quando o confronto é desfavorável ou você perdeu o controle do combate.",
}


def decide(ctx: dict) -> dict:
    """Combat Decision Engine — cenários A–E. Retorna decisão estruturada e justificada."""
    p = ctx.get("player") or {}
    info = ctx.get("enemy_info") or lookup(ctx.get("enemy") or "")
    fams, confirmed = enemy_weapon_set(ctx)
    count = int(ctx.get("enemy_count") or 1)
    caps = _player_caps(p)
    win = distance_window(p)
    scenarios, why, cautions, missing = [], [], [], []
    movement, alts = None, []
    priority, danger = None, None
    cristal = None

    if not info and not fams:
        missing.append("Nave/armas adversárias")
        return {
            "scenarios": [], "movement": None, "alternatives": [], "distance": PENDING, "propulsion": None,
            "tackle": None, "ammo": None, "priority": None, "danger": None, "retreat": None,
            "why": ["Sem dados suficientes: nenhuma decisão foi inventada."], "cautions": [],
            "missing": missing, "window": win, "complete": False,
        }

    hyp_tag = "" if confirmed else " (hipótese)"
    erank = CLASS_RANK.get(info["class"], 1) if info else 1
    prank = CLASS_RANK.get(ctx.get("player_class") or p.get("class_hint") or "Frigate", 1)

    # Cenário E — vários inimigos
    if count >= 2:
        scenarios.append("E")
        why.append(f"{count} adversários: superioridade numérica. Evite combate prolongado sem justificativa; priorize sobrevivência.")
        cautions.append("Avalie retirada imediata se a situação estiver desfavorável.")
        movement = "RETIRADA" if count >= 3 else "PILOTAGEM MANUAL"
        alts = ["PILOTAGEM MANUAL"] if movement == "RETIRADA" else ["RETIRADA"]
        priority = "SOBREVIVER"
        danger = "SUPERIORIDADE NUMÉRICA"

    # Cenário D — inimigo mais rápido
    if ctx.get("enemy_faster") is True:
        scenarios.append("D")
        why.append("O adversário tende a controlar a distância: avalie webifier, possibilidade de escapar e pilotagem manual.")
        cautions.append("NÃO trate Keep at Range como solução garantida: você pode ser mantido fora do seu alcance.")
        if caps["has_web"]:
            why.append("Você tem webifier: aplicá-lo reduz a vantagem de velocidade dele.")
        if movement is None:
            movement = "PILOTAGEM MANUAL"
            alts = ["APPROACH", "RETIRADA"]
            priority = "REDUZIR A VELOCIDADE DELE (WEB) E FECHAR/ESCAPAR"
            danger = "SER MANTIDO FORA DO ALCANCE"

    # Cenário C — foguetes/mísseis
    if _fam_match(fams, confirmed, MISSILE_FAMILIES):
        scenarios.append("C")
        why.append(f"Foguetes/mísseis{hyp_tag}: a aplicação depende de velocidade, assinatura e alcance — NÃO de tracking.")
        cautions.append("Não use Orbit apenas para aumentar velocidade angular contra mísseis/foguetes.")
        if movement is None:
            movement = "KEEP AT RANGE" if caps["has_prop"] else "PILOTAGEM MANUAL"
            alts = ["PILOTAGEM MANUAL"]
            priority = "CONTROLE DE DISTÂNCIA, VELOCIDADE E ASSINATURA"
            danger = "DANO DE MÍSSEIS INDEPENDE DE TRACKING"

    # Cenário B — torretas maiores
    if info and erank > prank and (fams & TURRET_FAMILIES):
        scenarios.append("B")
        why.append("Torretas maiores: Orbit próximo pode prejudicar o tracking inimigo — avalie antes de recomendar.")
        for item in ("tamanho das armas", "velocidade angular", "alcance", "webifier inimigo", "drones", "neutralizadores",
                     "capacidade das SUAS armas aplicarem dano em órbita"):
            why.append(f"  · verificar: {item}")
        cautions.append("Orbit pode piorar o tracking das suas armas e não anula drones/webs/neuts/mísseis.")
        if movement is None:
            movement = "ORBIT"
            alts = ["PILOTAGEM MANUAL", "KEEP AT RANGE"]
            priority = "REDUZIR APLICAÇÃO INIMIGA SEM PERDER A SUA"
            danger = "DRONES / WEB / NEUT / MÍSSEIS CONTINUAM PERIGOSOS"

    # Cenário A — blasters de curto alcance
    if _fam_match(fams, confirmed, {"blaster"}):
        scenarios.append("A")
        why.append(f"Blasters/armas de curto alcance{hyp_tag}: manter distância suficiente reduz o dano recebido, "
                   "desde que SUAS armas continuem aplicando dano.")
        if caps["has_prop"] and caps["has_scram"]:
            why.append("Propulsão + scrambler permitem manter o alvo preso na janela de distância.")
        if movement is None:
            movement = "KEEP AT RANGE" if caps["has_prop"] else "PILOTAGEM MANUAL"
            alts = ["PILOTAGEM MANUAL", "ORBIT" if erank > prank else "APPROACH"]
            priority = "MANTER A DISTÂNCIA"
            danger = "CONTROLE DE RANGE"

    if movement is None:
        scenarios.append("—")
        if caps["has_prop"] and caps["has_scram"] and win["lo"]:
            movement = "KEEP AT RANGE"
            alts = ["PILOTAGEM MANUAL", "ORBIT"]
            priority = "MANTER A DISTÂNCIA"
            danger = "CONTROLE DE RANGE"
            why.append("Fitting inimigo DESCONHECIDO: orientação padrão do seu estilo (scram kiting) enquanto você confirma "
                       "as armas dele pelo dano recebido. Não é uma conclusão sobre o inimigo.")
        else:
            movement = "PILOTAGEM MANUAL"
            alts = ["KEEP AT RANGE"]
            priority = "OBSERVAR E CONFIRMAR O FITTING INIMIGO"
            danger = "FITTING INIMIGO DESCONHECIDO"
            why.append("Sem propulsão/scrambler/alcance definidos no seu perfil: observe dano recebido e distância.")

    if not confirmed:
        cautions.append("Armas do adversário são HIPÓTESE (modelo da nave) — confirme pelo dano/Overview.")
    if win["notes"]:
        cautions.extend(win["notes"])

    # Munição (usa janela de distância)
    ammo = recommend_ammo(ctx.get("distance_m") or win["lo"], profile=p, enemy_info=info)
    cristal = ammo.get("recommended") if ammo.get("status") == "OK" else None

    retreat = "SE PERDER O CONTROLE DA DISTÂNCIA, CAPACITOR CRÍTICO OU NOVOS INIMIGOS"
    if "E" in scenarios and count >= 3:
        retreat = "AGORA — SUPERIORIDADE NUMÉRICA"
    if info and not confirmed and "E" not in scenarios and ctx.get("enemy_faster") is None:
        missing.append("Velocidade relativa")
    complete = bool(fams) and info is not None

    return {
        "scenarios": scenarios, "movement": movement, "alternatives": alts,
        "distance": _fmt_window(win), "propulsion": p.get("propulsion") or PENDING,
        "tackle": " + ".join(p.get("tackle", [])) or PENDING,
        "ammo": cristal, "priority": priority, "danger": danger, "retreat": retreat,
        "why": why, "cautions": cautions, "missing": missing, "window": win, "complete": complete,
        "movement_explanation": MOVEMENT_EXPLANATIONS.get(movement, ""),
    }


def advise_movement(ctx: dict) -> dict:
    """Range Control Advisor: recomendação principal + alternativas + explicações (modo treino)."""
    d = decide(ctx)
    return {
        "recommendation": d["movement"], "alternatives": d["alternatives"],
        "explanations": {m: MOVEMENT_EXPLANATIONS[m] for m in ([d["movement"]] + d["alternatives"]) if m in MOVEMENT_EXPLANATIONS},
        "why": d["why"], "cautions": d["cautions"], "distance": d["distance"], "missing": d["missing"],
        "manual_piloting_progression": MANUAL_PILOTING_PROGRESSION,
    }


MANUAL_PILOTING_PROGRESSION = [
    ("Iniciante", ["Movimento lateral: clique no espaço perpendicular ao alvo para criar velocidade transversal.",
                   "Controle de distância: alterne Approach/Keep at Range curtos e observe a distância no Overview."]),
    ("Intermediário", ["Aproximação em ângulo: feche distância sem apontar direto para o alvo (menos tempo em linha de tiro).",
                       "Correção de trajetória: ajuste o vetor quando o alvo mudar de direção.",
                       "Reduzir velocidade angular: aponte mais diretamente quando SEUS lasers estiverem errando."]),
    ("Avançado", ["Aumentar velocidade angular de forma pontual contra torretas com tracking fraco.",
                  "Técnicas contra kiting: aproximação em ângulo + webifier + quebra de linha de fuga."]),
]


# --------------------------------------------------------------------------- #
# Ammo Advisor (seção 10)
# --------------------------------------------------------------------------- #
CRYSTALS = {
    "Multifrequency": {"band": "curto", "note": "maior dano, menor alcance efetivo"},
    "Standard": {"band": "médio", "note": "alcance intermediário"},
    "Radio": {"band": "longo", "note": "maior alcance, menor dano"},
}


def recommend_ammo(distance_m, profile: dict | None = None, enemy_info: dict | None = None,
                   crystal_ranges: dict | None = None) -> dict:
    """
    Recomenda cristais Amarr. Se `crystal_ranges` ({cristal: optimal_m}) vier do piloto, usa-o;
    senão usa faixas de referência EDITÁVEIS (profile['ammo_bands_m']) — confirmar Optimal Range real.
    """
    if distance_m in (None, 0):
        return {"status": PENDING, "message": "Informe a distância para recomendar munição."}
    p = profile or {}
    bands = {"multifrequency_max": 4000, "standard_max": 8000}
    bands.update(p.get("ammo_bands_m") or {})
    d = float(distance_m)
    motive = []
    if crystal_ranges:
        usable = [(c, r) for c, r in crystal_ranges.items() if r and r >= d]
        if usable:
            # menor optimal que ainda cobre a distância => maior dano
            c, r = sorted(usable, key=lambda x: x[1])[0]
            rec = c
            motive.append(f"{c} cobre {fmt_m(d)} (optimal informado {fmt_m(r)}) com o maior dano entre os que alcançam.")
        else:
            c, r = sorted(crystal_ranges.items(), key=lambda x: -(x[1] or 0))[0]
            rec = c
            motive.append(f"Nenhum cristal informado cobre {fmt_m(d)}; {c} tem o maior alcance informado ({fmt_m(r)}).")
    else:
        if d <= bands["multifrequency_max"]:
            rec = "Multifrequency"
        elif d <= bands["standard_max"]:
            rec = "Standard"
        else:
            rec = "Radio"
        motive.append(f"{CRYSTALS[rec]['note'].capitalize()} — compatível com {fmt_m(d)} segundo as faixas de referência editáveis.")
        if rec != "Multifrequency":
            motive.append("Maior alcance efetivo que Multifrequency.")
    resist_note = None
    if enemy_info:
        tanks = " ".join(enemy_info.get("tanks", [])).lower()
        if "escudo" in tanks:
            resist_note = "Hipótese: escudos tendem a ter menor resistência base a EM (lasers causam EM/Térmico). Confirme resistências reais."
        elif "armadura" in tanks:
            resist_note = "Hipótese: armaduras tendem a resistir mais a EM/Térmico que a Cinético/Explosivo. Confirme resistências reais."
    full = None
    for a in (p.get("ammo") or []):
        if rec.lower() in a.lower():
            full = a  # nome exato do cristal que o piloto já carrega (ex.: Imperial Navy Standard S)
            break
    return {
        "status": "OK", "recommended": full or rec,
        "crystal": rec, "distance_m": d, "motive": motive, "resistance_note": resist_note,
        "observation": "Confirmar Optimal Range real com as habilidades atuais. Se tiver armas T2, considere também munições T2 compatíveis.",
    }


# --------------------------------------------------------------------------- #
# Capacitor Management Advisor (seção 11) e Armor Repair Advisor (seção 12)
# --------------------------------------------------------------------------- #
def capacitor_advice(cap_pct, profile=None, enemy_neut=False, scram_on=True, enemy_dangerous=None) -> dict:
    t = thresholds(profile)
    if cap_pct is None:
        return {"level": PENDING, "alerts": [], "lines": ["Informe o capacitor atual."]}
    lines, level = [], "OK"
    if cap_pct <= t["cap_critical_pct"]:
        level = "CRÍTICO"
        lines += ["CAPACITOR CRÍTICO", "Energia insuficiente para combate prolongado.",
                  "Priorize sobrevivência e módulos essenciais."]
    elif cap_pct <= t["cap_low_pct"]:
        level = "BAIXO"
        lines += ["CAPACITOR BAIXO", "Priorize módulos essenciais.",
                  "Evite ciclos desnecessários do reparador.",
                  "Considere retirada se não conseguir manter o combate."]
    else:
        lines.append(f"Capacitor em {cap_pct:.0f}% — dentro do limite configurado.")
    if enemy_neut:
        lines.append("Neutralizador inimigo ativo: espere queda mais rápida do capacitor.")
    if scram_on and level in ("BAIXO", "CRÍTICO"):
        lines.append("Não desligue o scrambler automaticamente: se o alvo for perigoso, soltá-lo pode piorar a situação. "
                     "A decisão depende do seu objetivo.")
    return {"level": level, "alerts": [l for l in lines[:1] if level in ("BAIXO", "CRÍTICO")], "lines": lines}


def armor_advice(armor_pct, paste_count=None, profile=None, ancillary=True, cycle_s=None, reps_unloaded=False) -> dict:
    t = thresholds(profile)
    lines, level = [], "OK"
    if armor_pct is None:
        return {"level": PENDING, "lines": ["Informe a armadura atual (%)."]}
    if armor_pct <= 30:
        level = "CRÍTICO"
        lines.append(f"Armadura em {armor_pct:.0f}%: não espere níveis ainda mais baixos — ative o reparador AGORA ou reavalie retirada.")
    elif armor_pct <= t["armor_repair_start_pct"]:
        level = "ATIVAR"
        lines.append(f"Armadura em {armor_pct:.0f}% (limite configurado {t['armor_repair_start_pct']}%): momento adequado para ativar o reparador.")
    else:
        lines.append(f"Armadura em {armor_pct:.0f}%: ainda acima do limite de ativação configurado.")
    lines.append("Evite desperdício: não ative com a armadura quase cheia; o ciclo repara em blocos.")
    if cycle_s:
        lines.append(f"Considere o tempo de ciclo ({cycle_s:.1f}s): a reparação chega só no fim do ciclo.")
    if ancillary:
        if paste_count is not None and paste_count <= t["paste_low_count"]:
            lines.append(f"⚠ Nanite Repair Paste baixa ({paste_count}): reabasteça/planeje retirada.")
        elif paste_count is None:
            lines.append("Informe a quantidade de Nanite Repair Paste para monitorar o consumo.")
        if reps_unloaded:
            lines.append("Módulo descarregado consome capacitor adicional: considere recarregar a pasta.")
    return {"level": level, "lines": lines}


# --------------------------------------------------------------------------- #
# Alertas táticos (seção 15) — curtos e objetivos
# --------------------------------------------------------------------------- #
def generate_alerts(state: dict) -> list:
    """
    state: {profile, enemy, enemy_info, prev_distance_m, distance_m, planned_range_m,
            miss_ratio, shots, cap_pct}
    Retorna lista de {key, title, lines, speak}.
    """
    alerts = []
    p = state.get("profile") or {}
    t = thresholds(p)
    d, prev = state.get("distance_m"), state.get("prev_distance_m")
    planned = state.get("planned_range_m")
    info = state.get("enemy_info") or lookup(state.get("enemy") or "")
    fams = set(info["weapons"]) if info else set()

    if d is not None and prev is not None and d < prev and info and fams & SHORT_RANGE_FAMILIES and d > (planned or 0):
        lines = [f"{info['name']} a {d/1000:.1f} km.".replace(".", ",", 1)]
        if "blaster" in fams:
            lines.append("Possível ameaça de blasters.")
        lines += ["Prepare Webifier.", "Tente manter distância."]
        alerts.append({"key": "approach", "title": "⚠️ INIMIGO APROXIMANDO", "lines": lines,
                       "speak": "Atenção: inimigo aproximando."})
    if d is not None and planned and d < planned * t["range_lost_ratio"]:
        alerts.append({"key": "range", "title": "⚠️ RANGE PERDIDO",
                       "lines": [f"Inimigo a {fmt_m(d)}.", f"Seu alcance planejado era {fmt_m(planned)}.",
                                 "Tente recuperar distância se sua velocidade permitir."],
                       "speak": "Range perdido."})
    shots, miss = state.get("shots"), state.get("miss_ratio")
    if shots is not None and miss is not None and shots >= t["miss_min_shots"] and miss >= t["miss_ratio_alert"]:
        alerts.append({"key": "tracking", "title": "⚠️ TRACKING INEFICIENTE",
                       "lines": ["Seus lasers estão errando.", "Verifique velocidade angular.",
                                 "Considere reduzir Orbit ou ajustar trajetória."],
                       "speak": "Tracking ineficiente."})
    cap = state.get("cap_pct")
    if cap is not None and cap <= t["cap_critical_pct"]:
        alerts.append({"key": "cap", "title": "⚠️ CAPACITOR CRÍTICO",
                       "lines": ["Energia insuficiente para combate prolongado.",
                                 "Priorize sobrevivência e módulos essenciais."],
                       "speak": "Capacitor crítico."})
    return alerts


# --------------------------------------------------------------------------- #
# Combat Mode (seção 16) — cartão curto
# --------------------------------------------------------------------------- #
def combat_card(ctx: dict) -> dict:
    """Cartão mínimo. Se não houver dados suficientes, NÃO inventa decisão."""
    d = decide(ctx)
    risk = classify_engagement(ctx)
    if not d["complete"]:
        return {"ok": False, "text": "DADOS INSUFICIENTES\n\nInforme a nave adversária para receber orientação.",
                "decision": d, "risk": risk}
    enemy = (ctx.get("enemy_info") or lookup(ctx.get("enemy") or "") or {}).get("name") or ctx.get("enemy")
    dist = ctx.get("distance_m")
    dist_txt = f"{dist/1000:.0f} KM".replace(".", ",") if dist is not None else "—"
    text = (
        f"INIMIGO: {enemy}\n\n"
        f"RISCO: {risk['classification']}\n\n"
        f"DISTÂNCIA: {dist_txt}\n\n"
        f"MOVIMENTO: {d['movement']}\n\n"
        f"CRISTAL: {(d['ammo'] or '—').upper()}\n\n"
        f"TACKLE: {d['tackle'].upper()}\n\n"
        f"PRIORIDADE: {d['priority']}\n\n"
        f"PERIGO: {d['danger']}\n\n"
        f"RETIRADA: {d['retreat']}"
    )
    return {"ok": True, "text": text, "decision": d, "risk": risk}
