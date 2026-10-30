# -*- coding: utf-8 -*-
"""
EVE PvP Tactical Copilot — núcleo tático (lógica pura, sem dependência de UI).

Princípios (manual, seções 3, 5, 6, 21 e 23):
  * Nunca inventar atributos: quando faltam dados, o resultado é "PENDENTE" / "DESCONHECIDO".
  * Distinguir FATOS conhecidos de HIPÓTESES.
  * Sem percentuais de vitória inventados.
  * O assistente RECOMENDA, nunca executa ações no jogo (nada de automação/overlay de leitura de memória).
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")

UNKNOWN = "DESCONHECIDO"
PENDING = "PENDENTE"


def data_path(filename: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, filename)


def load_json(filename: str, default):
    try:
        with open(data_path(filename), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(filename: str, payload) -> bool:
    try:
        tmp = data_path(filename) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        os.replace(tmp, data_path(filename))
        return True
    except Exception:
        return False


def fmt_m(value) -> str:
    """Formata metros no padrão pt-BR (4.000 m / 4,5 km)."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{int(round(v)):,}".replace(",", ".") + " m"
