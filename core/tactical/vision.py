# -*- coding: utf-8 -*-
"""
Combat Screenshot Analyzer (manual, seção 14).

Somente capturas ENVIADAS PELO USUÁRIO (arquivo ou área de transferência). Não há captura contínua,
OCR em tempo real, overlay de leitura nem acesso à memória do jogo (manual, seção 21).
Requer um modelo de visão no Ollama (config: "ollama_vision_model", ex.: llava, qwen2.5vl, llama3.2-vision).
"""
import base64
import json
import re
import urllib.request

FIELDS = [
    ("nave_atual", "Nave atual"), ("alvo_selecionado", "Alvo selecionado"), ("distancia_alvo", "Distância do alvo"),
    ("velocidade", "Velocidade"), ("capacitor", "Capacitor"), ("escudo", "Escudo"), ("armadura", "Armadura"),
    ("estrutura", "Estrutura"), ("modulos_ativos", "Módulos ativos"), ("municao", "Munição"),
    ("overview", "Informações visíveis no Overview"),
]

SYSTEM_PROMPT = (
    "Você analisa UMA captura de tela do EVE Online fornecida pelo jogador. Responda SOMENTE com JSON válido, "
    "com exatamente estas chaves: " + ", ".join(k for k, _ in FIELDS) + ". "
    "Regras: use null para qualquer informação que NÃO esteja legível/visível; NÃO invente valores; "
    "NÃO infira movimentos ou ações que a imagem não mostra (a captura é só um instante do combate). "
    "Valores curtos, em português, com a unidade como aparece na tela."
)


def image_to_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def extract_json(text: str) -> dict | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def format_result(data: dict | None) -> str:
    if data is None:
        return ("Não foi possível interpretar a resposta do modelo de visão. "
                "Nenhum valor foi inventado — tente outra captura ou outro modelo.")
    lines = ["ANÁLISE DA CAPTURA (instante único — nada além do visível é afirmado):", ""]
    for key, label in FIELDS:
        v = data.get(key)
        if v in (None, "", [], "null"):
            v = "DESCONHECIDO (não legível na captura)"
        elif isinstance(v, list):
            v = ", ".join(str(x) for x in v)
        lines.append(f"• {label}: {v}")
    return "\n".join(lines)


def analyze_image(path_or_b64: str, host: str, model: str, is_b64: bool = False, timeout: int = 120) -> dict:
    """Rede/bloqueante: execute em thread."""
    if not model:
        return {"ok": False, "text": ("Configure um modelo de visão no config.json (chave 'ollama_vision_model'), "
                                      "por exemplo 'llava' ou 'qwen2.5vl'. Nenhum modelo de visão foi encontrado.")}
    try:
        b64 = path_or_b64 if is_b64 else image_to_b64(path_or_b64)
        payload = {"model": model, "prompt": SYSTEM_PROMPT, "images": [b64], "stream": False,
                   "format": "json", "options": {"temperature": 0.0}}
        req = urllib.request.Request(f"{host}/api/generate", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode("utf-8"))
        data = extract_json(resp.get("response", ""))
        return {"ok": data is not None, "data": data, "text": format_result(data)}
    except Exception as e:
        return {"ok": False, "text": f"Erro ao consultar o modelo de visão: {e}"}
