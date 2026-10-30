# -*- coding: utf-8 -*-
"""
Ship Recommendation Engine (manual, seção 20).

Regras do manual:
  * Não ficar limitado à Tormentor.
  * Considerar conta Alpha/Omega, habilidades, orçamento, estilo, experiência, complexos FW e estética.
  * NÃO recomendar automaticamente naves mais caras (mais cara != melhor para aprender PvP).
  * Explicar vantagens e desvantagens de cada alternativa.
Custos são faixas qualitativas ('baixo' < 'médio' < 'alto'); confirme preços no mercado.
"""

COST_RANK = {"baixo": 1, "médio": 2, "alto": 3}

# alpha: True = hulls T1 racial; None = verificar disponibilidade p/ Alpha no jogo
SHIP_CATALOG = [
    {"name": "Tormentor", "race": "Amarr", "class": "Frigate", "styles": ["scram kite", "brawl"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Lasers com bom controle de range", "Drones", "Combina com seu estilo atual"],
     "cons": ["Pressão sobre capacitor", "Velocidade limitada"]},
    {"name": "Punisher", "race": "Amarr", "class": "Frigate", "styles": ["brawl"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Tank de armadura resistente", "Barata — boa para aprender perdendo pouco"],
     "cons": ["Menos mobilidade para kiting"]},
    {"name": "Executioner", "race": "Amarr", "class": "Frigate", "styles": ["kite", "scram kite"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Mobilidade para treinar controle de distância", "Barata"],
     "cons": ["Tank frágil; erros custam rápido"]},
    {"name": "Imperial Navy Slicer", "race": "Amarr", "class": "Frigate", "styles": ["kite", "brawl"], "cost": "médio",
     "alpha": None, "fw": ["Novice", "Small"], "learning": 2,
     "pros": ["Dano e mobilidade acima de T1", "Estética Amarr"],
     "cons": ["Mais cara: perder dói mais", "Verifique se sua conta Alpha pode pilotar"]},
    {"name": "Coercer", "race": "Amarr", "class": "Destroyer", "styles": ["kite", "brawl"], "cost": "baixo",
     "alpha": True, "fw": ["Small"], "learning": 2,
     "pros": ["Muitas torretas de energia (DPS potencial)", "Boa para treinar aplicação de lasers"],
     "cons": ["Capacitor exigente", "Assinatura grande vs fragatas"]},
    {"name": "Rifter", "race": "Minmatar", "class": "Frigate", "styles": ["brawl", "kite"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Versátil (vários estilos)", "Muito usada: fácil achar fittings"],
     "cons": ["Fora da sua preferência estética Amarr"]},
    {"name": "Merlin", "race": "Caldari", "class": "Frigate", "styles": ["kite", "brawl"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Tank de escudo", "Boa para treinar kiting com híbridos"],
     "cons": ["Fit híbrido muda muito o comportamento"]},
    {"name": "Incursus", "race": "Gallente", "class": "Frigate", "styles": ["brawl"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Excelente para aprender brawl", "Barata"],
     "cons": ["Exige fechar distância; vulnerável a kiting"]},
    {"name": "Tristan", "race": "Gallente", "class": "Frigate", "styles": ["brawl", "drones"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 3,
     "pros": ["Drones + armas", "Útil para treinar gestão de drones"],
     "cons": ["Mais coisas para gerenciar ao mesmo tempo"]},
    {"name": "Atron", "race": "Gallente", "class": "Frigate", "styles": ["brawl"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 2,
     "pros": ["Muito rápida para treinar aproximação", "Barata"],
     "cons": ["Tank fraco: precisa vencer rápido"]},
    {"name": "Kestrel", "race": "Caldari", "class": "Frigate", "styles": ["kite"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 2,
     "pros": ["Mísseis: aplicação independe de tracking", "Boa para entender mecânicas de mísseis"],
     "cons": ["Dano depende de velocidade/assinatura do alvo"]},
    {"name": "Slasher", "race": "Minmatar", "class": "Frigate", "styles": ["kite", "scram kite"], "cost": "baixo",
     "alpha": True, "fw": ["Novice", "Small"], "learning": 2,
     "pros": ["Muito rápida: ótima para treinar controle de range", "Barata"],
     "cons": ["Tank frágil"]},
    {"name": "Thrasher", "race": "Minmatar", "class": "Destroyer", "styles": ["brawl", "kite"], "cost": "baixo",
     "alpha": True, "fw": ["Small"], "learning": 2,
     "pros": ["Muitas torretas; DPS potencial alto"],
     "cons": ["Frágil contra tackle/neut"]},
]


def recommend(prefs: dict, top_n: int = 5) -> list:
    """
    prefs: account ('Alpha'|'Omega'), budget ('baixo'|'médio'|'alto'), style (str), experience,
           fw_complex ('Novice'...|None), faction_pref (str|None), skills_ok (set de nomes de nave) opcional.
    """
    account = prefs.get("account", "Alpha")
    budget = COST_RANK.get(prefs.get("budget", "baixo"), 1)
    style = (prefs.get("style") or "").lower()
    exp = prefs.get("experience", "Beginner")
    fw = prefs.get("fw_complex")
    fav = (prefs.get("faction_pref") or "Amarr").lower()
    skills_ok = prefs.get("skills_ok")

    scored = []
    for s in SHIP_CATALOG:
        notes, score = [], 0
        if COST_RANK[s["cost"]] > budget:
            continue
        if account == "Alpha" and s["alpha"] is None:
            notes.append("Verifique se sua conta Alpha pode pilotar esta nave.")
            score -= 1
        if skills_ok is not None and s["name"] not in skills_ok:
            notes.append("Você ainda não declarou habilidade para esta nave.")
            score -= 1
        if style and any(style in st or st in style for st in s["styles"]):
            score += 2
            notes.append(f"Combina com o estilo '{style}'.")
        if fw and fw in s["fw"]:
            score += 1
            notes.append(f"Provável bom ajuste para complexos {fw} (verifique a restrição no jogo).")
        if s["race"].lower() == fav:
            score += 1
            notes.append("Preferência estética/facção atendida.")
        if exp == "Beginner":
            score += s["learning"] - 2  # valor didático
        # custo menor desempata (não privilegia nave cara)
        score -= COST_RANK[s["cost"]] * 0.3
        scored.append((score, s, notes))

    scored.sort(key=lambda x: -x[0])
    out = []
    for score, s, notes in scored[:top_n]:
        out.append({"name": s["name"], "race": s["race"], "class": s["class"], "cost": s["cost"],
                    "pros": s["pros"], "cons": s["cons"], "notes": notes, "score": round(score, 2),
                    "reminder": "Nave mais cara não é necessariamente melhor para aprender PvP."})
    return out
