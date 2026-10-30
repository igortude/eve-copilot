# -*- coding: utf-8 -*-
"""
Gerenciador Tático de Voz & Áudio (TTS Sci-Fi) para o EVE Tactical Copilot
Estilo 'Aura' (IA da nave no EVE Online) ou 'Jarvis' (IA tática do Homem de Ferro).
Fornece instruções e dicas em áudio em português (PT-BR) com baixíssima latência e cache permanente.
"""

import os
import shutil
import subprocess
import threading
import time
import queue
import hashlib
import asyncio

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False


VOICE_PROFILES = {
    "aura": {
        "voice": "pt-BR-FranciscaNeural",
        "name": "Aura (Computador de Bordo - CCP)"
    },
    "jarvis": {
        "voice": "pt-BR-AntonioNeural",
        "name": "Jarvis (Assistente Tático)"
    }
}


class VoiceManager:
    def __init__(self, cache_dir=None, sounds_dir=None, enabled=True, persona="aura"):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cache_dir = cache_dir or os.path.join(base_dir, "data", "tts_cache")
        self.sounds_dir = sounds_dir or os.path.join(base_dir, "sounds")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.enabled = enabled
        self.persona = persona if persona in VOICE_PROFILES else "aura"
        self.last_played = {}
        self.speech_queue = queue.PriorityQueue()
        self.player_cmd = self._detect_player()
        self._counter = 0
        self._lock = threading.Lock()

        # Worker thread dedicado para reprodução sequencial sem sobreposição de falas
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()

    def set_persona(self, persona):
        if persona in VOICE_PROFILES:
            self.persona = persona

    def _detect_player(self):
        if shutil.which("mpv"):
            return "mpv"
        elif shutil.which("pw-play"):
            return "pw-play"
        elif shutil.which("paplay"):
            return "paplay"
        elif shutil.which("aplay"):
            return "aplay"
        return None

    def _play_audio_file(self, file_path):
        if not self.player_cmd or not os.path.exists(file_path):
            return
        try:
            if self.player_cmd == "mpv":
                cmd = ["mpv", "--no-video", "--volume=100", file_path]
            elif self.player_cmd == "aplay":
                cmd = ["aplay", "-q", file_path]
            else:
                cmd = [self.player_cmd, file_path]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception as e:
            print(f"[VoiceManager] Erro ao reproduzir {file_path}: {e}")

    def _fallback_spd_say(self, text):
        if shutil.which("spd-say"):
            try:
                voice_type = "female1" if self.persona == "aura" else "male1"
                subprocess.run(
                    ["spd-say", "-l", "pt-br", "-t", voice_type, "-r", "-5", text],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False
                )
            except Exception:
                pass

    def _speech_worker(self):
        while True:
            try:
                # PriorityQueue retorna tuplas: (priority_score, counter, task_dict)
                _, _, item = self.speech_queue.get()
                audio_path = item.get("audio_path")
                text = item.get("text")

                if audio_path and os.path.exists(audio_path):
                    self._play_audio_file(audio_path)
                elif text:
                    # Gera e reproduz dinamicamente
                    generated_path = self._generate_tts_sync(text, item.get("cache_key"))
                    if generated_path and os.path.exists(generated_path):
                        self._play_audio_file(generated_path)
                    else:
                        self._fallback_spd_say(text)

                time.sleep(0.3)
                self.speech_queue.task_done()
            except Exception as e:
                time.sleep(0.2)

    def _generate_tts_sync(self, text, cache_key=None):
        if not HAS_EDGE_TTS:
            return None

        if cache_key:
            fname = f"{self.persona}_{cache_key}.mp3"
        else:
            h = hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
            fname = f"{self.persona}_{h}.mp3"

        out_path = os.path.join(self.cache_dir, fname)
        if os.path.exists(out_path):
            return out_path

        try:
            voice_id = VOICE_PROFILES[self.persona]["voice"]
            communicate = edge_tts.Communicate(text, voice_id)
            asyncio.run(communicate.save(out_path))
            return out_path
        except Exception as e:
            print(f"[VoiceManager] Falha ao sintetizar voz via edge-tts: {e}")
            return None

    def speak(self, text, cache_key=None, priority=False, cooldown=3.0):
        """
        Enfileira uma fala com voz de IA tática (Aura/Jarvis).
        Usa cache instantâneo se disponível, ou sintetiza em background.
        """
        if not self.enabled:
            return

        now = time.time()
        ck = cache_key or hashlib.md5(text.encode("utf-8")).hexdigest()[:12]
        with self._lock:
            last = self.last_played.get(ck, 0.0)
            if (now - last) < cooldown:
                return
            self.last_played[ck] = now
            self._counter += 1
            counter = self._counter

        # Prioridade: 1 para emergências (scramble/drone sob ataque), 5 para dicas informativas
        prio_score = 1 if priority else 5

        # Checa se o arquivo de cache já existe
        cached_file = os.path.join(self.cache_dir, f"{self.persona}_{ck}.mp3")
        if os.path.exists(cached_file):
            self.speech_queue.put((prio_score, counter, {"audio_path": cached_file, "text": text}))
        else:
            self.speech_queue.put((prio_score, counter, {"audio_path": None, "text": text, "cache_key": ck}))

    def play(self, sound_filename, cooldown=2.5):
        """
        Substitui os sons legados (.wav de alarme e explosão) por falas inteligentes de IA.
        Mantém total retrocompatibilidade de API.
        """
        if not self.enabled:
            return

        if sound_filename == "eve_drone_alarm.wav":
            self.speak(
                "Atenção, piloto. Seu drone está sob ataque. Pressione Shift R para recolhê-lo à baía.",
                cache_key="drone_under_attack",
                priority=True,
                cooldown=cooldown
            )
        elif sound_filename == "eve_ui_warning.wav":
            self.speak(
                "Alerta tático: interferência hostil detectada nos sistemas da nave.",
                cache_key="scram_alert",
                priority=True,
                cooldown=cooldown
            )
        elif sound_filename == "eve_combat_alert.wav":
            self.speak(
                "Aviso de integridade: dano pesado recebido na blindagem.",
                cache_key="heavy_damage",
                priority=False,
                cooldown=cooldown
            )
        else:
            # Arquivo arbitrário
            sound_path = os.path.join(self.sounds_dir, sound_filename)
            if os.path.exists(sound_path):
                now = time.time()
                with self._lock:
                    if (now - self.last_played.get(sound_filename, 0.0)) < cooldown:
                        return
                    self.last_played[sound_filename] = now
                    self._counter += 1
                    counter = self._counter
                self.speech_queue.put((5, counter, {"audio_path": sound_path, "text": None}))


# Alias para retrocompatibilidade
SoundManager = VoiceManager
