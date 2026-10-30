# -*- coding: utf-8 -*-
"""
Enemy Ship Analyzer (manual, seção 5).

IMPORTANTE: o sistema NUNCA assume o fitting inimigo só pelo modelo da nave.
  * FATOS  -> classe e raça da nave (conhecimento estável do jogo).
  * HIPÓTESES -> armamentos, tanques e estilos "comuns" (podem variar muito de um piloto para outro).
Valores de alcance são faixas QUALITATIVAS típicas; confirme sempre com o jogo.
"""
from . import UNKNOWN

# Faixas qualitativas típicas por família de arma (rótulos, não números do jogo)
WEAPON_FAMILIES = {
    "blaster": {"label": "Blasters (híbrido)", "band": "curto", "profile": "alto dano a curta distância; precisa fechar o alcance",
                "prefers": "brawl", "short_range": True},
    "railgun": {"label": "Railguns (híbrido)", "band": "longo", "profile": "alcance longo, tracking baixo; sofre contra alta velocidade angular",
                "prefers": "snipe", "short_range": False},
    "autocannon": {"label": "Autocannons (projétil)", "band": "curto-médio", "profile": "dano flexível com falloff generoso",
                   "prefers": "brawl/kite", "short_range": True},
    "artillery": {"label": "Artillery (projétil)", "band": "longo", "profile": "alcance longo e alpha alto; tracking fraco",
                  "prefers": "snipe", "short_range": False},
    "pulse_laser": {"label": "Pulse Lasers (energia)", "band": "curto-médio", "profile": "bom tracking, dano EM/Térmico; consome capacitor",
                    "prefers": "brawl", "short_range": True},
    "beam_laser": {"label": "Beam Lasers (energia)", "band": "médio-longo", "profile": "alcance maior e tracking menor que pulse",
                   "prefers": "kite", "short_range": False},
    "rocket": {"label": "Foguetes", "band": "curto", "profile": "dano aplicado depende de velocidade e assinatura, não de tracking",
               "prefers": "brawl", "short_range": True},
    "light_missile": {"label": "Mísseis leves", "band": "médio", "profile": "aplicação depende de velocidade/assinatura; sem tracking",
                      "prefers": "kite", "short_range": False},
    "drones": {"label": "Drones", "band": "variável", "profile": "dano independe de tracking da nave; controlado por distância/ordens",
               "prefers": "variável", "short_range": None},
}

# classe -> rank de tamanho (para comparar escalas)
CLASS_RANK = {
    "Frigate": 1, "Interceptor": 1, "Assault Frigate": 1, "Electronic Attack Frigate": 1,
    "Logistics Frigate": 1, "Covert Ops": 1, "Destroyer": 2, "Cruiser": 3,
    "Heavy Assault Cruiser": 3, "Battlecruiser": 4, "Battleship": 5,
}

# nome -> dados. 'fatos' = (classe, raça). Todo o resto é hipótese comum.
ENEMY_DB = {
    # --- Minmatar ---
    "rifter": {"class": "Frigate", "race": "Minmatar",
               "weapons": ["autocannon", "artillery", "rocket"], "styles": ["brawl", "kite curto"],
               "tanks": ["escudo ativo", "armadura", "buffer"], "ewar": ["tackle (scrambler/web)"],
               "speed": "rápida", "threats": ["Dano flexível a curta/média distância", "Tackle rápido"]},
    "slasher": {"class": "Frigate", "race": "Minmatar", "weapons": ["autocannon", "artillery"],
                "styles": ["kite", "tackle rápido"], "tanks": ["buffer fraco"], "ewar": ["tackle"],
                "speed": "muito rápida", "threats": ["Velocidade e tackle", "Dificulta manter range"]},
    "breacher": {"class": "Frigate", "race": "Minmatar", "weapons": ["light_missile", "rocket"],
                 "styles": ["kite"], "tanks": ["escudo"], "ewar": [], "speed": "média",
                 "threats": ["Mísseis ignoram tracking — aplicação via velocidade/assinatura"]},
    "wolf": {"class": "Assault Frigate", "race": "Minmatar", "weapons": ["autocannon", "artillery"],
             "styles": ["brawl", "kite"], "tanks": ["escudo", "armadura"], "ewar": ["tackle"],
             "speed": "rápida", "threats": ["Maior dano e resistência que fragata T1"]},
    "jaguar": {"class": "Assault Frigate", "race": "Minmatar", "weapons": ["autocannon", "artillery"],
               "styles": ["brawl", "kite"], "tanks": ["escudo", "armadura"], "ewar": ["tackle"],
               "speed": "rápida", "threats": ["Tank e dano acima de fragatas T1"]},
    "stiletto": {"class": "Interceptor", "race": "Minmatar", "weapons": ["autocannon", "rocket"],
                 "styles": ["tackle rápido"], "tanks": ["fraco"], "ewar": ["tackle (scram/disruptor)"],
                 "speed": "extrema", "threats": ["Velocidade extrema; difícil de rastrear"]},
    "vigil": {"class": "Frigate", "race": "Minmatar", "weapons": ["autocannon", "rocket"],
              "styles": ["suporte EWAR"], "tanks": ["fraco"],
              "ewar": ["possível EWAR/web (confirmar)"], "speed": "rápida",
              "threats": ["Possível EWAR; confirmar módulos em jogo"]},
    # --- Gallente ---
    "incursus": {"class": "Frigate", "race": "Gallente", "weapons": ["blaster", "railgun"],
                 "styles": ["brawl"], "tanks": ["armadura"], "ewar": ["web / scrambler"],
                 "speed": "média-rápida", "threats": ["Dano alto de blasters se chegar perto", "Webifier"]},
    "tristan": {"class": "Frigate", "race": "Gallente", "weapons": ["blaster", "railgun", "drones"],
                "styles": ["brawl", "drones"], "tanks": ["armadura"], "ewar": ["web / scrambler"],
                "speed": "média", "threats": ["Drones + armas; vários fits possíveis"]},
    "atron": {"class": "Frigate", "race": "Gallente", "weapons": ["blaster"],
              "styles": ["brawl rápido"], "tanks": ["fraco"], "ewar": ["web / scrambler"],
              "speed": "rápida", "threats": ["Fecha distância rápido", "Blasters de curto alcance"]},
    "maulus": {"class": "Frigate", "race": "Gallente", "weapons": ["blaster", "railgun"],
               "styles": ["suporte EWAR"], "tanks": ["fraco"], "ewar": ["sensor dampeners (provável)"],
               "speed": "média", "threats": ["Pode reduzir seu alcance de lock"]},
    "enyo": {"class": "Assault Frigate", "race": "Gallente", "weapons": ["blaster", "railgun"],
             "styles": ["brawl"], "tanks": ["armadura"], "ewar": ["web / scrambler"],
             "speed": "média-rápida", "threats": ["Alto dano de curta distância", "Tank superior ao T1"]},
    "ishkur": {"class": "Assault Frigate", "race": "Gallente", "weapons": ["blaster", "drones"],
               "styles": ["brawl", "drones"], "tanks": ["armadura"], "ewar": ["web / scrambler"],
               "speed": "média", "threats": ["Drones e blasters simultâneos"]},
    "taranis": {"class": "Interceptor", "race": "Gallente", "weapons": ["blaster", "railgun"],
                "styles": ["tackle rápido"], "tanks": ["fraco"], "ewar": ["tackle"],
                "speed": "extrema", "threats": ["Tackle com dano relevante"]},
    # --- Caldari ---
    "merlin": {"class": "Frigate", "race": "Caldari", "weapons": ["blaster", "railgun"],
               "styles": ["brawl", "kite"], "tanks": ["escudo"], "ewar": ["tackle"],
               "speed": "média", "threats": ["Pode usar blasters OU railguns — não presumir"]},
    "kestrel": {"class": "Frigate", "race": "Caldari", "weapons": ["light_missile", "rocket"],
                "styles": ["kite"], "tanks": ["escudo"], "ewar": [], "speed": "média",
                "threats": ["Mísseis: dano aplicado independe do seu tracking"]},
    "condor": {"class": "Frigate", "race": "Caldari", "weapons": ["blaster", "railgun"],
               "styles": ["kite", "tackle rápido"], "tanks": ["escudo fraco"], "ewar": ["tackle"],
               "speed": "rápida", "threats": ["Velocidade e tackle"]},
    "griffin": {"class": "Frigate", "race": "Caldari", "weapons": ["light_missile"],
                "styles": ["suporte EWAR"], "tanks": ["fraco"], "ewar": ["ECM"], "speed": "média",
                "threats": ["ECM pode quebrar seu lock"]},
    "hawk": {"class": "Assault Frigate", "race": "Caldari", "weapons": ["light_missile", "rocket"],
             "styles": ["kite", "brawl"], "tanks": ["escudo"], "ewar": [], "speed": "média",
             "threats": ["Mísseis com bom dano; tank de escudo"]},
    "harpy": {"class": "Assault Frigate", "race": "Caldari", "weapons": ["railgun", "blaster"],
              "styles": ["kite"], "tanks": ["escudo"], "ewar": [], "speed": "média",
              "threats": ["Railguns de longo alcance — controle de range pesa a favor dele"]},
    # --- Amarr ---
    "punisher": {"class": "Frigate", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser"],
                 "styles": ["brawl", "kite curto"], "tanks": ["armadura"], "ewar": ["tackle"],
                 "speed": "lenta-média", "threats": ["Tank de armadura resistente", "Consumo de capacitor"]},
    "executioner": {"class": "Frigate", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser"],
                    "styles": ["kite", "tackle rápido"], "tanks": ["fraco"], "ewar": ["tackle"],
                    "speed": "rápida", "threats": ["Velocidade para controlar distância"]},
    "tormentor": {"class": "Frigate", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser", "drones"],
                  "styles": ["scram kite", "brawl"], "tanks": ["armadura"], "ewar": ["scrambler / web"],
                  "speed": "média", "threats": ["Controle de range com drones"]},
    "slicer": {"class": "Frigate", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser"],
               "styles": ["kite", "brawl"], "tanks": ["armadura"], "ewar": ["tackle"],
               "speed": "rápida", "threats": ["Dano consistente e mobilidade"]},
    "crucifier": {"class": "Frigate", "race": "Amarr", "weapons": ["pulse_laser"],
                  "styles": ["suporte EWAR"], "tanks": ["fraco"], "ewar": ["tracking disruptors (provável)"],
                  "speed": "média", "threats": ["Pode degradar seu tracking/alcance"]},
    "retribution": {"class": "Assault Frigate", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser"],
                    "styles": ["brawl", "kite"], "tanks": ["armadura"], "ewar": ["tackle"],
                    "speed": "média", "threats": ["Tank e dano acima do T1"]},
    "crusader": {"class": "Interceptor", "race": "Amarr", "weapons": ["pulse_laser"],
                 "styles": ["tackle rápido"], "tanks": ["fraco"], "ewar": ["tackle"],
                 "speed": "extrema", "threats": ["Tackle rápido"]},
    # --- Destroyers ---
    "thrasher": {"class": "Destroyer", "race": "Minmatar", "weapons": ["autocannon", "artillery"],
                 "styles": ["brawl", "kite"], "tanks": ["escudo"], "ewar": [], "speed": "rápida",
                 "threats": ["Muitas torretas; alto DPS potencial vs fragatas"]},
    "catalyst": {"class": "Destroyer", "race": "Gallente", "weapons": ["blaster", "railgun"],
                 "styles": ["brawl"], "tanks": ["armadura"], "ewar": [], "speed": "média",
                 "threats": ["Alto DPS de curta distância vs fragatas"]},
    "cormorant": {"class": "Destroyer", "race": "Caldari", "weapons": ["railgun", "blaster"],
                  "styles": ["kite", "snipe"], "tanks": ["escudo"], "ewar": [], "speed": "média",
                  "threats": ["Alcance longo; fraco em curta distância"]},
    "coercer": {"class": "Destroyer", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser"],
                "styles": ["kite", "brawl"], "tanks": ["armadura"], "ewar": [], "speed": "média",
                "threats": ["Muitas torretas de energia; consome capacitor"]},
    # --- Cruisers ---
    "rupture": {"class": "Cruiser", "race": "Minmatar", "weapons": ["autocannon", "artillery"],
                "styles": ["brawl", "kite"], "tanks": ["escudo", "armadura"], "ewar": ["web possível"],
                "speed": "média", "threats": ["Torretas médias: sofre contra alta velocidade angular", "Drones possíveis"]},
    "stabber": {"class": "Cruiser", "race": "Minmatar", "weapons": ["autocannon", "artillery"],
                "styles": ["kite"], "tanks": ["escudo"], "ewar": ["web possível"], "speed": "rápida",
                "threats": ["Mobilidade; difícil de pegar"]},
    "thorax": {"class": "Cruiser", "race": "Gallente", "weapons": ["blaster", "railgun", "drones"],
               "styles": ["brawl", "drones"], "tanks": ["armadura"], "ewar": ["web possível"],
               "speed": "média", "threats": ["Drones + blasters; perigoso de perto"]},
    "vexor": {"class": "Cruiser", "race": "Gallente", "weapons": ["drones", "blaster"],
              "styles": ["drones"], "tanks": ["armadura"], "ewar": [], "speed": "média",
              "threats": ["Dano de drones independe do seu tracking — controlar drones/distância"]},
    "caracal": {"class": "Cruiser", "race": "Caldari", "weapons": ["light_missile"],
                "styles": ["kite"], "tanks": ["escudo"], "ewar": [], "speed": "média",
                "threats": ["Mísseis: aplicação depende de velocidade/assinatura"]},
    "moa": {"class": "Cruiser", "race": "Caldari", "weapons": ["railgun", "blaster"],
            "styles": ["kite", "snipe"], "tanks": ["escudo"], "ewar": [], "speed": "média",
            "threats": ["Alcance longo"]},
    "omen": {"class": "Cruiser", "race": "Amarr", "weapons": ["pulse_laser", "beam_laser"],
             "styles": ["brawl", "kite"], "tanks": ["armadura"], "ewar": [], "speed": "média",
             "threats": ["Lasers médios; consome capacitor"]},
    "maller": {"class": "Cruiser", "race": "Amarr", "weapons": ["pulse_laser"],
               "styles": ["brawl", "tank"], "tanks": ["armadura resistente"], "ewar": [],
               "speed": "lenta", "threats": ["Tank muito resistente — luta longa"]},
    "arbitrator": {"class": "Cruiser", "race": "Amarr", "weapons": ["drones"], "styles": ["EWAR / drones"],
                   "tanks": ["armadura"], "ewar": ["neutralizador / web / painter (possíveis)"],
                   "speed": "média", "threats": ["Neutralizadores de capacitor possíveis; drones"]},
}

ALIASES = {"imperial navy slicer": "slicer", "navy slicer": "slicer"}


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def lookup(name: str):
    key = ALIASES.get(_norm(name), _norm(name))
    data = ENEMY_DB.get(key)
    if data:
        out = dict(data)
        out["name"] = key.title() if key != "slicer" else "Imperial Navy Slicer"
        return out
    return None


def known_ships():
    return sorted(k.title() for k in ENEMY_DB)


def analyze_enemy(enemy_name: str, player_profile: dict | None = None) -> dict:
    """
    Devolve análise separando FATOS de HIPÓTESES, mais ameaças, vantagens, estratégia e retirada.
    """
    info = lookup(enemy_name)
    if not info:
        return {
            "known": False, "name": enemy_name, "risk_hint": UNKNOWN,
            "message": ("Nave fora da base interna. Informe a classe manualmente ou consulte dados públicos. "
                        "Nenhuma hipótese será inventada."),
            "facts": {}, "hypotheses": {}, "threats": [], "advantages": [], "strategy": [], "retreat": [],
        }

    weapons = [WEAPON_FAMILIES[w] for w in info["weapons"] if w in WEAPON_FAMILIES]
    short_range = [w for w in weapons if w["short_range"]]
    long_range = [w for w in weapons if w["short_range"] is False]

    facts = {"Classe": info["class"], "Raça/Facção da nave": info["race"]}
    hypotheses = {
        "Possíveis armamentos": [w["label"] for w in weapons],
        "Estilos de combate comuns": info["styles"],
        "Faixas de alcance prováveis": sorted({f'{w["label"]}: {w["band"]}' for w in weapons}),
        "Possíveis tanques": info["tanks"],
        "Velocidade típica": info["speed"],
        "EWAR/Tackle possíveis": info["ewar"] or ["nenhum típico (confirmar)"],
    }

    threats = list(info["threats"])
    if any(w["label"] == "Drones" for w in weapons):
        threats.append("Drones: dano não depende do tracking da nave — observe o que atacam")
    if any("neutral" in e.lower() for e in info["ewar"]):
        threats.append("Neutralizadores: pressão sobre seu capacitor")

    advantages, strategy, retreat = [], [], []
    p = player_profile or {}
    my_tackle = " ".join(p.get("tackle", [])).lower()
    my_prop = (p.get("propulsion") or "").lower()
    can_kite = bool(p) and ("scrambler" in my_tackle or "disruptor" in my_tackle) and bool(my_prop)

    if short_range and not long_range and can_kite:
        advantages.append("Se ele estiver realmente com armas de curto alcance, controlar a distância pode reduzir o dano recebido.")
        strategy.append("Tente abrir distância adequada ao SEU alcance efetivo; confirme o fitting dele pelo que o Overview/danos mostram.")
    if long_range and not short_range:
        advantages.append("Se ele usar armas de longo alcance, fechar distância pode ser vantajoso (se você tiver tackle e velocidade).")
        strategy.append("Considere aproximação em ângulo/manual para reduzir tempo sob fogo de longa distância.")
    if any(w["label"] == "Mísseis leves" or w["label"] == "Foguetes" for w in weapons):
        strategy.append("Contra mísseis/foguetes, orbitar só para aumentar velocidade angular NÃO é suficiente: priorize velocidade, assinatura e controle de distância.")
    if any(e.lower().startswith(("ecm", "sensor", "tracking")) for e in info["ewar"]):
        strategy.append("EWAR possível: elimine/ignore conforme o efeito sentido; confirme o módulo em uso antes de reagir.")
    if "rápida" in info["speed"] or "extrema" in info["speed"]:
        strategy.append("Alvo tende a ser rápido: webifier e pilotagem manual ajudam a evitar ser mantido fora do alcance.")
    if not strategy:
        strategy.append("Observe distância e dano recebido nos primeiros segundos para confirmar qual hipótese vale.")

    retreat.append("Retire-se se perder o controle da distância planejada sem conseguir recuperá-la.")
    if info["class"] in ("Cruiser", "Destroyer"):
        retreat.append("Nave maior que fragata: avalie retirada se seu dano aplicado não reduzir o tank dele rapidamente.")
    retreat.append("Retire-se se aparecerem inimigos adicionais (superioridade numérica) ou capacitor crítico.")

    return {
        "known": True, "name": info["name"], "risk_hint": "AVALIAR",
        "message": "Fitting inimigo DESCONHECIDO: tudo abaixo é hipótese baseada no modelo da nave.",
        "facts": facts, "hypotheses": hypotheses, "threats": threats,
        "advantages": advantages or ["Sem vantagem clara sem conhecer o fitting inimigo."],
        "strategy": strategy, "retreat": retreat,
        "class": info["class"], "weapon_families": info["weapons"],
    }
