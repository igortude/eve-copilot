#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Pré-Geração do Cache de Voz dos Conselhos Táticos de Voo (Aura & Jarvis)
Gera os arquivos .mp3 com antecedência para resposta imediata (<10ms) em combate.
"""

import os
import sys
import asyncio
import edge_tts

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "data", "tts_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

VOICES = {
    "aura": "pt-BR-FranciscaNeural",
    "jarvis": "pt-BR-AntonioNeural"
}

PHRASES = {
    "weapon_blaster": "Inimigo armado com Blasters. Ligue o Afterburner imediatamente e faça kiting a mais de 18 km.",
    "weapon_railgun": "Railguns inimigos detectados. Ligue o Afterburner e entre em órbita transversal para quebrar o tracking das armas.",
    "weapon_autocannon": "Autocannons balísticos detectados. Ligue o Afterburner e faça kiting a mais de 18 km.",
    "weapon_artillery": "Artilharia pesada detectada. Não voe em linha reta. Aumente a velocidade transversal angular para quebrar o tiro.",
    "weapon_pulse_laser": "Lasers de pulso detectados. Ligue a propulsão e recue para além de 20 km.",
    "weapon_beam_laser": "Beam Lasers detectados. Ligue o Afterburner e estabeleça órbita fechada a 10 km para quebrar a mira dos lasers.",
    "weapon_missile": "Mísseis hostis detectados. Mantenha o Afterburner ligado em velocidade máxima para mitigar o dano da explosão.",
    "weapon_rocket": "Foguetes de curta distância detectados. Ligue o Afterburner e mantenha distância acima de 16 km.",
    "weapon_torpedo": "Torpedos pesados a caminho. Mantenha propulsão máxima para mitigar a explosão.",
    "weapon_drones": "Drones inimigos atacando sua nave. Ligue a propulsão e ordene seus drones para neutralizá-los.",
    "weapon_disintegrator": "Perigo extremo. Raio Triglaviano ativo. O dano multiplica a cada ciclo. Saia do alcance imediatamente."
}

async def generate_cache():
    print("🚀 Pré-gerando arquivos de áudio táticos balísticos...")
    total = len(VOICES) * len(PHRASES)
    count = 0
    for persona, voice_name in VOICES.items():
        for key, text in PHRASES.items():
            filename = f"{persona}_{key}.mp3"
            filepath = os.path.join(CACHE_DIR, filename)
            if not os.path.exists(filepath):
                print(f"[{persona.upper()}] Gerando: {key} -> {filename}...")
                communicate = edge_tts.Communicate(text, voice_name)
                await communicate.save(filepath)
                count += 1
            else:
                print(f"[{persona.upper()}] Já em cache: {filename}")
    print(f"✅ Concluído! {count} novos áudios gerados no cache.")

if __name__ == "__main__":
    asyncio.run(generate_cache())
