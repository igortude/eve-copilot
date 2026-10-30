# -*- coding: utf-8 -*-
"""
EVE Online Tactical Knowledge Base Avançada
Informações sobre fraquezas de facções, impérios, tipos de armas, drones e distâncias de engajamento.
"""

FACTIONS = {
    "caldari": {
        "name": "Caldari Navy / Caldari State",
        "damage_dealt": ["Kinetic (Mísseis / Railguns)", "Thermal (Híbridas)"],
        "weakness": "EM",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Munição EMP, Lentes Multifrequency (EM) ou Antimatter (Thermal)",
        "drones_to_use": "Drones Amarr (Acolyte / Infiltrator - EM) ou Gallente (Hobgoblin - Thermal)",
        "optimal_distance": "Mantenha velocidade transversal angular alta contra os Railguns. Orbite a 15-25km para mitigar impacto de mísseis.",
        "danger_level": "ALTO (ECM Jamming quebra seus locks + Mísseis Kinetic)",
        "priority": "Elimine primeiro Griffins e Blackbirds (usam ECM Jammer para travar seu lock)."
    },
    "guristas": {
        "name": "Guristas Pirates",
        "damage_dealt": ["Kinetic (Predominante)", "Thermal"],
        "weakness": "Kinetic",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Mísseis Scourge / Titanium Sabot ou Phased Plasma",
        "drones_to_use": "Drones Caldari (Hornet / Vespa / Wasp - Dano KINETIC)",
        "optimal_distance": "Mantenha velocidade alta e orbite além de 20-30km se possível, ou feche distância com Afterburner para mitigar explosão de mísseis.",
        "danger_level": "ALTO (Mísseis não erram tiro por tracking e eles usam Jamming ECM)",
        "priority": "Elimine primeiro as Fragatas (Kestrel/Corpii) que usam teia e ECM, depois Cruisers e Battleships."
    },
    "blood": {
        "name": "Blood Raiders",
        "damage_dealt": ["EM (Eletromagnético)", "Thermal"],
        "weakness": "EM",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Lentes Multifrequency / Munição EMP ou Fusion",
        "drones_to_use": "Drones Amarr (Acolyte / Infiltrator / Praetor - Dano EM)",
        "optimal_distance": "CRÍTICO: Fique LONGE (>25km)! Se você chegar perto (<15km), eles drenam seu capacitor a ZERO em segundos.",
        "danger_level": "EXTREMO (Drenagem de Capacitor / Neut)",
        "priority": "Destrua primeiro as fragatas com Energy Vampire/Neut para proteger seu capacitor."
    },
    "sansha": {
        "name": "Sansha's Nation",
        "damage_dealt": ["EM", "Thermal"],
        "weakness": "EM",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Lentes de Laser Standard/Radio para distância, ou EMP em balística",
        "drones_to_use": "Drones Amarr (Dano EM)",
        "optimal_distance": "Mantenha velocidade transversal angular alta se eles usarem lasers, mas cuidado se eles aplicarem Tracking Disruptor.",
        "danger_level": "ALTO (Tracking Disruption + Dano EM pesado)",
        "priority": "Elimine fragatas de interdição imediatamente."
    },
    "serpentis": {
        "name": "Serpentis",
        "damage_dealt": ["Thermal", "Kinetic"],
        "weakness": "Thermal",
        "secondary_weakness": "Kinetic",
        "ammo_to_use": "Lentes Microwave/Infrared ou Munição Plasma / Antimatter",
        "drones_to_use": "Drones Gallente (Hobgoblin / Hammerhead / Ogre - Maior DPS do jogo, Dano THERMAL)",
        "optimal_distance": "Eles usam armas híbridas (Blasters e Railguns). Se você ficar a menos de 10km, o dano dos Blasters deles é devastador. KITE a 20km+!",
        "danger_level": "MÉDIO-ALTO (Se você tomar Web/Teia, o dano sobe drasticamente)",
        "priority": "Nave com ícone de teia (Stasis Web) é prioridade absoluta número 1."
    },
    "gallente": {
        "name": "Gallente Federation / Navy",
        "damage_dealt": ["Thermal", "Kinetic (Blasters/Railguns e Drones)"],
        "weakness": "Kinetic",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Munição Titanium Sabot / Scourge (Kinetic)",
        "drones_to_use": "Drones Caldari (Hornet / Vespa - Kinetic)",
        "optimal_distance": "Evite combate de curta distância (<10km) contra blasters Gallente. Kite a 18km+!",
        "danger_level": "MÉDIO-ALTO (Alto DPS de curto alcance)",
        "priority": "Fragatas rápidas com scrambler e web."
    },
    "amarr": {
        "name": "Amarr Empire / Navy",
        "damage_dealt": ["EM", "Thermal (Lasers de Energia)"],
        "weakness": "EM",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Munição EMP / Lentes Multifrequency",
        "drones_to_use": "Drones Amarr (Acolyte / Infiltrator)",
        "optimal_distance": "Mantenha órbita transversal fechada para quebrar o tracking dos lasers de grande porte.",
        "danger_level": "MÉDIO-ALTO (Capacitor Neuts e dano concentrado)",
        "priority": "Fragatas com neuts de capacitor."
    },
    "minmatar": {
        "name": "Minmatar Republic / Fleet",
        "damage_dealt": ["Explosive", "Kinetic (Projéteis Balísticos)"],
        "weakness": "Explosive",
        "secondary_weakness": "Kinetic",
        "ammo_to_use": "Munição Fusion / Mísseis Nova (Explosive)",
        "drones_to_use": "Drones Minmatar (Warrior / Valkyrie)",
        "optimal_distance": "Eles são velozes. Use teias (Web) para reduzir a velocidade deles.",
        "danger_level": "ALTO (Alta velocidade e dano instantâneo)",
        "priority": "Fragatas com Target Painter e teias."
    },
    "angel": {
        "name": "Angel Cartel",
        "damage_dealt": ["Explosive", "Kinetic"],
        "weakness": "Explosive",
        "secondary_weakness": "Kinetic",
        "ammo_to_use": "Mísseis Nova / Munição Fusion (Dano Explosive)",
        "drones_to_use": "Drones Minmatar (Warrior / Valkyrie / Berserker - Os drones mais velozes do jogo)",
        "optimal_distance": "Eles são as naves mais rápidas do jogo. Use armas de rastreamento rápido (AutoCannons ou mísseis leves). Se tentar fugir em linha reta, eles te alcançam.",
        "danger_level": "ALTO (Velocidade e dano Alpha explosivo)",
        "priority": "Fragatas rápidas e naves com Target Painter."
    },
    "drone": {
        "name": "Rogue Drones",
        "damage_dealt": ["Omni (Todos os tipos)", "Kinetic", "Explosive"],
        "weakness": "EM (no Escudo) / Explosive (na Blindagem)",
        "secondary_weakness": "Thermal",
        "ammo_to_use": "Munição EMP ou Fusion",
        "drones_to_use": "Drones Amarr (EM) ou Minmatar (Velozes)",
        "optimal_distance": "Drones menores tentam enxamear sua nave. Use drones leves em modo agressivo para matar os scouts.",
        "danger_level": "MÉDIO",
        "priority": "Drones pequenos (Decimator / Sunderer) para não acumular dano."
    },
    "triglavian": {
        "name": "Triglavian Collective",
        "damage_dealt": ["Thermal", "Explosive (Entropic Disintegrator)"],
        "weakness": "Thermal",
        "secondary_weakness": "Explosive",
        "ammo_to_use": "Munição Plasma / Fusion / Antimatter",
        "drones_to_use": "Drones Gallente (Thermal) ou Minmatar (Explosive)",
        "optimal_distance": "EXTREMO: O dano do Desintegrador Triglaviano MULTIPLICA exponencialmente a cada segundo! Quebre o lock ou saia do alcance!",
        "danger_level": "LETAL",
        "priority": "Destrua ou saia do grid imediatamente."
    }
}

SHIP_CLASSES = {
    "griffin": "Fragata de Guerra Eletrônica (ECM Jammer perigoso!)",
    "kestrel": "Fragata de Mísseis (Dano cinético constante)",
    "merlin": "Fragata de Combate (Canhões híbridos e escudo reforçado)",
    "condor": "Fragata Interceptora rápida (Tackle e mísseis leves)",
    "corax": "Destróier de Mísseis (Alto DPS à distância)",
    "cormorant": "Destróier Sniper de Railguns (Alcance extremo)",
    "caracal": "Cruzador de Mísseis Pesados (Dano constante a 50km+)",
    "moa": "Cruzador de Combate de Escudo e Railguns",
    "scout": "Batedor Rápido (Prioridade para evitar tackle)",
    "soldier": "Soldado / Guarda de Linha de Frente",
    "leader": "Líder de Esquadrão / Comandante",
    "frigate": "Fragata (Pequena e rápida)",
    "destroyer": "Destróier (Muitas armas leves)",
    "cruiser": "Cruzador (Médio porte)",
    "battlecruiser": "Cruzador de Batalha",
    "battleship": "Couraçado (Grande porte e armas pesadas)"
}

def analyze_target_text(text):
    text_lower = text.lower()

    # Ignora itens e módulos de nave copiados por engano
    if any(item in text_lower for item in ["amplifier", "blueprint", "shield booster", "armor repairer", "afterburner", "microwarpdrive", "ammo"]):
        return None, "Módulo / Item"

    matched_faction = None
    if "caldari" in text_lower:
        matched_faction = FACTIONS["caldari"]
    elif "guristas" in text_lower or any(w in text_lower for w in ["pithi", "pithum", "pith", "scourge"]):
        matched_faction = FACTIONS["guristas"]
    elif "blood" in text_lower or any(w in text_lower for w in ["corpii", "corpum", "corpus"]):
        matched_faction = FACTIONS["blood"]
    elif "sansha" in text_lower or any(w in text_lower for w in ["centii", "centum", "centus"]):
        matched_faction = FACTIONS["sansha"]
    elif "serpentis" in text_lower or any(w in text_lower for w in ["coreli", "coreum", "core"]):
        matched_faction = FACTIONS["serpentis"]
    elif "angel" in text_lower or any(w in text_lower for w in ["gistii", "gistum", "gist"]):
        matched_faction = FACTIONS["angel"]
    elif "gallente" in text_lower:
        matched_faction = FACTIONS["gallente"]
    elif "amarr" in text_lower:
        matched_faction = FACTIONS["amarr"]
    elif "minmatar" in text_lower:
        matched_faction = FACTIONS["minmatar"]
    elif "rogue drone" in text_lower or any(w in text_lower for w in ["decimator", "sunderer", "alvus", "strain"]):
        matched_faction = FACTIONS["drone"]
    elif "triglavian" in text_lower or "leshak" in text_lower or "drekavac" in text_lower:
        matched_faction = FACTIONS["triglavian"]

    matched_size = None
    for key, desc in SHIP_CLASSES.items():
        if key in text_lower:
            matched_size = desc
            break

    return matched_faction, matched_size


# ==============================================================================
# BASE DE DADOS DE BALÍSTICA E RECOMENDAÇÕES TÁTICAS DE VOO (FLIGHT ADVISOR)
# ==============================================================================

WEAPON_TACTICS = {
    "blaster": {
        "category": "Canhão Híbrido de Curto Alcance (Blaster)",
        "effective_range": "< 8 km",
        "danger_zone": "< 10 km",
        "recommended_maneuver": "Kiting (> 18 km)",
        "propulsion": "Ligar Afterburner / MWD",
        "flight_advice": "Inimigo armado com Blasters! Dano devastador à queima-roupa. Ligue o Afterburner e faça kiting a mais de 18 km para anular completamente o dano.",
        "voice_advice": "Inimigo armado com Blasters. Ligue o Afterburner imediatamente e faça kiting a mais de 18 km.",
        "cache_key": "weapon_blaster"
    },
    "railgun": {
        "category": "Canhão Híbrido Sniper de Longo Alcance (Railgun)",
        "effective_range": "20 - 60 km",
        "danger_zone": "> 25 km",
        "recommended_maneuver": "Órbita Transversal Fechada (10-12 km)",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Canhões Railguns detectados! Eles têm alcance longo mas péssimo tracking. Ligue o Afterburner e entre em órbita transversal fechada a 10 km para quebrar o rastreamento das armas.",
        "voice_advice": "Railguns inimigos detectados. Ligue o Afterburner e entre em órbita transversal para quebrar o tracking das armas.",
        "cache_key": "weapon_railgun"
    },
    "autocannon": {
        "category": "Metralhadora Balística de Curta Distância (Autocannon)",
        "effective_range": "< 10 km",
        "danger_zone": "< 12 km",
        "recommended_maneuver": "Kiting (> 18 km)",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Inimigo usando Autocannons balísticos com alto DPS à queima-roupa. Mantenha Afterburner ativo e mantenha distância superior a 18 km.",
        "voice_advice": "Autocannons balísticos detectados. Ligue o Afterburner e faça kiting a mais de 18 km.",
        "cache_key": "weapon_autocannon"
    },
    "artillery": {
        "category": "Bateria de Artilharia Pesada (Artillery Cannon)",
        "effective_range": "30 - 70 km",
        "danger_zone": "Qualquer distância em linha reta (Dano Alpha instantâneo)",
        "recommended_maneuver": "Aproximação em Espiral Transversal",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Artilharia pesada detectada! Dano instantâneo destrutivo. NUNCA voe em linha reta em direção ao inimigo. Voe em espiral transversal e aproxime-se para menos de 15 km.",
        "voice_advice": "Artilharia pesada detectada. Não voe em linha reta. Aumente a velocidade transversal angular para quebrar o tiro.",
        "cache_key": "weapon_artillery"
    },
    "pulse_laser": {
        "category": "Laser de Energia de Curto Alcance (Pulse Laser)",
        "effective_range": "< 12 km",
        "danger_zone": "< 15 km",
        "recommended_maneuver": "Kiting (> 20 km)",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Lasers de pulso detectados (Dano EM/Térmico). Afaste-se com Afterburner para além de 20 km para sair do alcance de tiro ideal.",
        "voice_advice": "Lasers de pulso detectados. Ligue a propulsão e recue para além de 20 km.",
        "cache_key": "weapon_pulse_laser"
    },
    "beam_laser": {
        "category": "Laser de Feixe de Longo Alcance (Beam Laser)",
        "effective_range": "25 - 60 km",
        "danger_zone": "> 20 km",
        "recommended_maneuver": "Órbita Transversal Fechada (10 km)",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Beam Lasers de sniper detectados! Feixes de longo alcance com baixa velocidade de rotação. Acelere o Afterburner e orbite a 10 km.",
        "voice_advice": "Beam Lasers detectados. Ligue o Afterburner e estabeleça órbita fechada a 10 km para quebrar a mira dos lasers.",
        "cache_key": "weapon_beam_laser"
    },
    "missile": {
        "category": "Mísseis Guiados (Light/Heavy/Cruise Missile)",
        "effective_range": "30 - 80 km",
        "danger_zone": "Qualquer distância",
        "recommended_maneuver": "Velocidade Máxima Contínua",
        "propulsion": "Manter Afterburner Ligado",
        "flight_advice": "Mísseis hostis em voo! Mísseis não erram por mira, mas o dano é reduzido drasticamente pela sua velocidade de voo. Mantenha o Afterburner 100% ativo para mitigar a explosão.",
        "voice_advice": "Mísseis hostis detectados. Mantenha o Afterburner ligado em velocidade máxima para mitigar o dano da explosão.",
        "cache_key": "weapon_missile"
    },
    "rocket": {
        "category": "Foguetes Não-Guiados (Rockets)",
        "effective_range": "< 12 km",
        "danger_zone": "< 12 km",
        "recommended_maneuver": "Kiting (> 16 km)",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Foguetes de curta distância detectados! Ligue o Afterburner e recue para além de 16 km.",
        "voice_advice": "Foguetes de curta distância detectados. Ligue o Afterburner e mantenha distância acima de 16 km.",
        "cache_key": "weapon_rocket"
    },
    "torpedo": {
        "category": "Torpedos Pesados (Torpedos)",
        "effective_range": "15 - 40 km",
        "danger_zone": "Letal para naves paradas",
        "recommended_maneuver": "Velocidade Angular Alta",
        "propulsion": "Manter Propulsão Máxima",
        "flight_advice": "Torpedos pesados detectados! Explosão de raio imenso. Mantenha velocidade máxima com Afterburner ligado para que a onda de choque cause o mínimo de dano.",
        "voice_advice": "Torpedos pesados a caminho. Mantenha propulsão máxima para mitigar a explosão.",
        "cache_key": "weapon_torpedo"
    },
    "drone_swarm": {
        "category": "Enxame de Drones de Combate Hostis",
        "effective_range": "< 15 km",
        "danger_zone": "< 10 km",
        "recommended_maneuver": "Kiting / Destruição de Drones",
        "propulsion": "Ligar Afterburner",
        "flight_advice": "Drones hostis engajando sua nave! Ligue o Afterburner para esticar a linha de drones e elimine-os com suas armas ou ordene seus drones a atacá-los.",
        "voice_advice": "Drones inimigos atacando sua nave. Ligue a propulsão e ordene seus drones para neutralizá-los.",
        "cache_key": "weapon_drones"
    },
    "disintegrator": {
        "category": "Desintegrador Entrópico Triglaviano",
        "effective_range": "15 - 35 km",
        "danger_zone": "Qualquer distância se o feixe continuar aceso",
        "recommended_maneuver": "Quebrar Linha de Visada / Fora de 40 km",
        "propulsion": "Ligar Afterburner / MicroWarpdrive",
        "flight_advice": "ALERTA MÁXIMO: Raio Desintegrador Triglaviano ativo! O dano MULTIPLICA exponencialmente a cada segundo. Ligue o Afterburner imediatamente e fuja para além de 40 km!",
        "voice_advice": "Perigo extremo. Raio Triglaviano ativo. O dano multiplica a cada ciclo. Saia do alcance imediatamente.",
        "cache_key": "weapon_disintegrator"
    }
}


def analyze_incoming_weapon(weapon_name, attacker_name=""):
    """
    Identifica o tipo de arma que atingiu a nave e retorna a recomendação balística e tática de voo.
    """
    if not weapon_name and not attacker_name:
        return None

    w_lower = (weapon_name or "").lower()
    att_lower = (attacker_name or "").lower()
    combined = f"{w_lower} {att_lower}"

    # 1. Desintegrador Triglaviano
    if any(k in combined for k in ["disintegrator", "entropic", "supratidal", "subtidal"]):
        return WEAPON_TACTICS["disintegrator"]

    # 2. Drones
    if any(k in combined for k in ["hobgoblin", "warrior", "acolyte", "hornet", "hammerhead", "valkyrie", "infiltrator", "vespa", "ogre", "praetor", "berserker", "bouncer", "warden", "curator", "gardist"]):
        return WEAPON_TACTICS["drone_swarm"]

    # 3. Torpedos
    if "torpedo" in combined:
        return WEAPON_TACTICS["torpedo"]

    # 4. Foguetes (Rockets)
    if "rocket" in combined:
        return WEAPON_TACTICS["rocket"]

    # 5. Mísseis
    if any(k in combined for k in ["missile", "scourge", "inferno", "nova", "mjolnir", "heavy missile", "light missile", "cruise missile"]):
        return WEAPON_TACTICS["missile"]

    # 6. Blasters
    if any(k in combined for k in ["blaster", "electron", "neutron", "ion blaster"]):
        return WEAPON_TACTICS["blaster"]

    # 7. Railguns
    if any(k in combined for k in ["railgun", "rail", "75mm", "125mm", "150mm", "250mm", "350mm", "425mm"]):
        return WEAPON_TACTICS["railgun"]

    # 8. Autocannons
    if any(k in combined for k in ["autocannon", "auto cannon", "gatling", "repeater", "125mm auto", "150mm auto", "200mm auto", "220mm vulcan", "425mm auto", "800mm repeating"]):
        return WEAPON_TACTICS["autocannon"]

    # 9. Artilharia (Artillery)
    if any(k in combined for k in ["artillery", "howitzer", "280mm", "650mm", "720mm", "1200mm", "1400mm"]):
        return WEAPON_TACTICS["artillery"]

    # 10. Lasers de Pulso (Pulse)
    if any(k in combined for k in ["pulse laser", "pulse", "focused pulse", "heavy pulse", "mega pulse"]):
        return WEAPON_TACTICS["pulse_laser"]

    # 11. Lasers de Feixe (Beam)
    if any(k in combined for k in ["beam laser", "beam", "focused beam", "heavy beam", "tachyon"]):
        return WEAPON_TACTICS["beam_laser"]

    # 12. Padrões por Facção Inimiga quando a arma não for explicitada no log
    if any(k in att_lower for k in ["guristas", "pithi", "pithum", "pith"]):
        return WEAPON_TACTICS["missile"]
    elif any(k in att_lower for k in ["serpentis", "coreli", "coreum", "core"]):
        return WEAPON_TACTICS["blaster"]
    elif any(k in att_lower for k in ["blood", "corpii", "corpum", "corpus", "sansha", "centii", "centum"]):
        return WEAPON_TACTICS["beam_laser"]
    elif any(k in att_lower for k in ["angel", "gistii", "gistum", "gist"]):
        return WEAPON_TACTICS["autocannon"]

    return None


