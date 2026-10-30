# ◈ EVE Tactical Copilot

Overlay tático (*always-on-top*) em **PyQt6** para **EVE Online** no Linux (Lutris/Wine), com voz de bordo em PT-BR, análise de combate, gerenciador de naves, assistente de Faction Warfare, cotador de mercado e treino de PvP. Funciona de forma **offline-first**: a IA é local (Ollama) e a internet só é usada em consultas públicas (ESI/zKillboard) e na síntese de voz.

> ⚠️ **Status: arquivado.** Parei de jogar EVE, então o projeto não tem mais manutenção ativa. O código está completo e funcional (41 testes passando), e fica aqui como referência ou ponto de partida. Fique à vontade para fazer fork.

> **Aviso:** projeto de fã, não afiliado à CCP Games. *EVE Online* é marca registrada da CCP hf. O Copilot **recomenda**, nunca executa ações no jogo. Veja [Segurança e política da CCP](#-segurança-e-política-da-ccp).

---

## ✨ Recursos

O app tem 13 painéis (abas), que podem ser destacados em janelas independentes e têm posição e visibilidade salvas em `config.json`.

| Painel | O que faz |
|---|---|
| **General** | Visão geral do HUD, estado da voz, fonte, opacidade e trava de posição. |
| **Tactics & Combat** | Seleção de alvo inimigo com separação de **fatos vs. hipóteses**, classificação de risco (*Favorável / Equilibrado / Desfavorável / Desconhecido*, **sem percentuais inventados**), recomendação de movimento (Keep at Range / Orbit / Approach / manual / retirada), análise de aplicação de dano, munição, capacitor e armadura. Inclui o **Combat Mode**, com informação mínima durante a luta. |
| **Ship Manager** | Múltiplas naves, importador de fittings **EFT**, validação de estrutura (CPU/PG ficam como *pendente* quando não há dados, **sem inventar atributos**) e perfil de combate editável com recálculo de alcance. |
| **Tactical Simulator** | Simulador visual de movimentação relativa (vista de cima): trajetória, anéis de alcance, velocidade angular, com controles de AB, Web, munição e modo (KAR / Orbit). |
| **FW & D-Scan** | Tabela de complexos de Faction Warfare, parser de **D-Scan** colado, classificação de ameaças e orientação de captura. |
| **Training & AAR** | 10 exercícios práticos, quiz conceitual que explica o porquê, **After Action Review** baseado em fatos (logs/killmail) e histórico do piloto com detecção de padrões. |
| **Copilot** | Scanner da Overview (`Ctrl+C`) que mostra munição, drones, distância e prioridade de abate. |
| **Market & Fit** | Cota fittings EFT, listas e inventário em ordens de venda ao vivo (ESI) dentro de um raio de *X* jumps, com lista pronta para o **Multibuy**. |
| **Loot Triage** | Classifica cargo em 4 grupos: usar na nave, vender (Jita/hub), guardar no hangar ou reprocessar/descartar, com estimativa de ISK via ESI. |
| **Hacking** | Simulador do minigame de hacking (Relic/Data sites), com mapa em grafo e OCR opcional via Tesseract. |
| **Combat Log** | Lê o log de combate do Wine em tempo real: acertos, erros, taxa de evasão transversal e identificação da arma hostil. |
| **Missions** | Cole a descrição da missão em inglês e o modelo local extrai objetivo, inimigos, tanque e perigos em português. |
| **Advisor** | Chat com o consultor de voo para dúvidas sobre fittings e mecânicas. |

### 🎙️ Voz tática (TTS)

- Vozes **Aura** (feminina) e **Jarvis** (masculina), geradas com [`edge-tts`](https://github.com/rany2/edge-tts), em PT-BR.
- **Cache permanente em disco:** a mesma frase é sintetizada uma única vez e depois toca na hora.
- Avisos falados para: drone sob ataque, drones ociosos/esquecidos antes de saltar, *Warp Scrambler*, *Stasis Web*, *Neut*, ECM, arma hostil detectada e manobra recomendada.
- Botão no topo do HUD alterna Aura, Jarvis e mudo.
- Para pré-gerar as frases de combate (resposta quase instantânea): `python3 scripts/precache_tactical_voices.py`.

### 🧠 Princípios de design

Os requisitos estão em [`manual`](manual) (o prompt-especificação original). Em resumo:

- **Ensinar, não só mandar:** explica *por que* manter 4 km, *quando* orbitar etc.
- **Não inventar dados:** sem informação suficiente, o resultado é `DESCONHECIDO`.
- **Não assumir o fitting do inimigo** só pelo modelo da nave.
- **DPS nominal ≠ dano aplicado:** considera alcance, tracking, assinatura e velocidade angular.

---

## 📦 Instalação

### Requisitos

- Linux (testado em KDE/Wayland, com EVE via Lutris/Wine)
- Python 3.10+ (desenvolvido em 3.14)
- Opcionais:
  - [**Ollama**](https://ollama.com) para Missions, Advisor e análise de screenshot
  - **mpv**, `pw-play`, `paplay` ou `aplay` para tocar o áudio (o primeiro disponível é usado)
  - **Tesseract** para o OCR do painel de Hacking

### Passos

```bash
git clone https://github.com/igortude/eve-copilot.git
cd eve-copilot

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# opcional: modelo local para missões/advisor
ollama pull qwen2.5:7b

./run.sh        # ou: python3 app.py
```

O `run.sh` inicia o `ollama serve` caso ele ainda não esteja rodando.

---

## ⚙️ Configuração (`config.json`)

| Chave | Descrição |
|---|---|
| `log_dir` | **Ajuste para o seu caminho.** Pasta `Gamelogs` do EVE (ex.: `~/Games/eve-online/drive_c/users/<você>/Documents/EVE/logs/Gamelogs`). |
| `ollama_host` / `ollama_model` | Servidor e modelo local (padrão: `http://localhost:11434` / `qwen2.5:7b`). |
| `ollama_vision_model` | Modelo de visão (ex.: `llava`, `qwen2.5vl`) para o analisador de screenshot. Sem ele, o recurso fica desativado. |
| `voice_persona` | `aura` ou `jarvis`. |
| `sound_alerts` | Liga/desliga os alertas sonoros. |
| `overlay_opacity`, `font_delta`, `is_locked`, `pos_x`, `pos_y` | Aparência e posição do overlay. |
| `windows_state` | Estado de cada painel (destacado/visível). Gerenciado pelo app. |

Perfil do piloto, naves e histórico de treino são salvos em `data/` (JSON).

---

## 🕹️ Uso rápido

1. Abra o EVE e o Copilot (o HUD flutua sobre o jogo; arraste pela barra superior).
2. **Scanner de alvo:** clique numa nave na Overview e pressione `Ctrl+C`. O Copilot lê a área de transferência (polling contínuo, funciona em Wayland) e fala a recomendação.
3. **Fittings:** no EVE, copie o fitting como EFT e cole no *Ship Manager* ou no *Market & Fit*.
4. **D-Scan:** copie o resultado do D-Scan e cole no painel *FW & D-Scan*.
5. **Pós-combate:** cole um killmail (JSON da ESI, URL da ESI ou link do zKillboard) no *Training & AAR*.

---

## 🧪 Testes

```bash
pip install pytest
python3 -m pytest -q
```

Os testes cobrem o núcleo tático (`core/tactical`), que é lógica pura, sem dependência de UI.

---

## 🗂️ Estrutura

```
app.py                      # HUD principal (PyQt6) e orquestração dos painéis
run.sh                      # inicia Ollama (se preciso) + app
manual                      # especificação original do PvP Copilot
config.json                 # configuração local

core/
├── tactical/               # núcleo tático (lógica pura, testável)
│   ├── engine.py           #   risco, range, decisão, aplicação de dano, ammo, cap, armadura
│   ├── ships.py            #   Ship Manager + importador/validador EFT
│   ├── enemies.py          #   Enemy Ship Analyzer
│   ├── fw.py               #   Faction Warfare + D-Scan + Capture
│   ├── training.py         #   exercícios, quiz, AAR, histórico e padrões
│   ├── killmail.py         #   killmails via ESI/zKillboard (dados públicos)
│   ├── recommend.py        #   recomendação de naves
│   ├── simulator.py        #   simulador de movimentação relativa
│   ├── vision.py           #   analisador de screenshot (Ollama vision)
│   └── profile.py          #   perfil do piloto
├── tactical_ui/            # widgets dos painéis táticos
├── log_parser.py           # monitor do log de combate
├── target_scanner.py       # scanner da Overview via clipboard
├── sound_player.py         # voz (edge-tts) + cache + player
├── market_checker.py       # cotação ESI concorrente
├── loot_evaluator.py       # triagem de loot
├── mission_helper.py       # tradutor/consultor via Ollama
├── hacking_game.py / hacking_ui.py
└── database.py             # base de conhecimento tática

data/                       # dados estáticos (naves, preços) e perfil do piloto
sounds/                     # alertas sonoros
scripts/                    # utilitários (pré-cache de voz)
tests/                      # testes do núcleo tático
```

---

## 🔒 Segurança e política da CCP

O projeto foi desenhado para ficar do lado seguro das regras, mas **a responsabilidade pelo uso é sua**:

- **Não** injeta comandos no cliente, **não** automatiza combate, **não** lê a memória do jogo.
- Fontes de dados: logs de jogo que o próprio cliente grava em disco, texto que **você** copia (clipboard/EFT/D-Scan/killmail), e APIs públicas (ESI e zKillboard).
- O analisador de screenshot só processa imagens que **você** fornece.
- Overlays e leitura de logs podem ser tratados de forma diferente conforme a política vigente da CCP. **Confira os termos atuais antes de usar.**

---

## 📝 Licença

Ainda não há licença definida. Sem uma licença explícita, todos os direitos são reservados; se quiser reutilizar o código, abra uma *issue*.
