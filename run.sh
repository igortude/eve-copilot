#!/bin/bash
# Inicia o EVE Tactical Copilot
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Garante que o Ollama está rodando
if ! pgrep -x "ollama" > /dev/null; then
    echo "Iniciando serviço do Ollama..."
    ollama serve > /dev/null 2>&1 &
    sleep 2
fi

echo "Iniciando EVE Tactical Copilot Overlay..."
python3 app.py
