# -*- coding: utf-8 -*-
"""
EVE Online Tactical Assistant & Mission Translator via Ollama
Gera conselhos de voo, fraquezas de inimigos e tradução tática de missões.
"""

import json
import urllib.request
import urllib.error

class OllamaAdvisor:
    def __init__(self, host="http://localhost:11434", model="qwen2.5:7b"):
        self.host = host
        self.model = model

    def check_connection(self):
        try:
            req = urllib.request.Request(f"{self.host}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                models = [m.get('name') for m in data.get('models', [])]
                return True, models
        except Exception as e:
            return False, str(e)

    def analyze_mission(self, mission_text):
        """
        Traduz e extrai inteligência de combate de missões do EVE Online.
        """
        system_prompt = (
            "Você é o 'EVE Tactical Copilot', um comandante experiente e navegador tático do jogo EVE Online. "
            "Sua missão é analisar o texto da missão (em inglês), traduzir o objetivo para português e fornecer "
            "instruções de combate diretas e vitais para o piloto.\n\n"
            "Seu formato de resposta DEVE ser rigorosamente este:\n"
            "🎯 OBJETIVO: (Resumo claro em português do que fazer)\n"
            "⚔️ INIMIGOS & FACÇÃO: (Quais são os NPCs, ex: Guristas, Serpentis, etc)\n"
            "💥 MUNIÇÃO A USAR: (Qual dano explorar: EM, Thermal, Kinetic ou Explosive)\n"
            "🛡️ TANQUE RECOMENDADO: (Quais resistências priorizar no escudo/blindagem)\n"
            "⚠️ ALERTA TÁTICO: (Avisos de perigo: triggers de spawn, teias/webs, drenagem de capacitor)\n"
            "Seja conciso, direto e tático. Fale como um oficial de nave espacial."
        )

        prompt = f"Analise a seguinte missão do EVE Online:\n\n{mission_text}"

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\nPiloto: {prompt}\nCopiloto:",
            "stream": False,
            "options": {
                "temperature": 0.3,
                "top_p": 0.9
            }
        }

        try:
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=40) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get('response', 'Sem resposta do Copiloto.')
        except urllib.error.URLError as e:
            return f"❌ Erro de conexão com o Ollama: Certifique-se de que o Ollama está rodando (ollama serve). Detalhe: {e}"
        except Exception as e:
            return f"❌ Erro ao processar inteligência tática: {str(e)}"

    def ask_tactical_advice(self, user_question, current_ship="Desconhecida"):
        """
        Responde a dúvidas táticas de pilotagem, fitting, distâncias de tiro e táticas de combate.
        """
        system_prompt = (
            f"Você é o copiloto tático do EVE Online. A nave atual do piloto é '{current_ship}'. "
            "Responda a dúvidas sobre táticas de combate (velocidade transversal, controle de range, "
            "otimização de capacitor, kiting vs brawling, fraquezas de alvos e sugestões de módulos/upgrades). "
            "Dê respostas práticas, curtas e de aplicação imediata no combate."
        )

        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\nPiloto pergunta: {user_question}\nCopiloto responde:",
            "stream": False,
            "options": {
                "temperature": 0.4
            }
        }

        try:
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result.get('response', 'Sem resposta.')
        except Exception as e:
            return f"Erro de comunicação tática: {e}"
