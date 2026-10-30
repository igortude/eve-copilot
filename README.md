# 🚀 EVE Tactical Copilot — HUD Overlay

Assistente tático de voo e combate transparente (*Always-on-Top*) para **EVE Online** no Linux (Lutris/Wine), 100% seguro contra banimentos da CCP Games.

---

## 🌟 Recursos Exclusivos

1. **Design Oficial Sci-Fi (EVE Neocom HUD):**
   - Janela translúcida de acrílico espacial escuro com bordas em ciano neon (`#00e5ff`).
   - Flutua diretamente sobre a tela do jogo sem bloquear sua visão do espaço.
   - Arraste suave segurando qualquer ponto da barra superior (`◈ EVE TACTICAL COPILOT`).
   - Botão de minimizar rápido (`—`) para recolher o HUD em uma fita fina tática.

2. **Scanner Instantâneo de Alvos da Overview (<kbd>Ctrl</kbd> + <kbd>C</kbd>):**
   - Ao entrar na missão ou no cinturão de asteroides, clique em qualquer nave na sua **Overview** (ou no espaço) e aperte <kbd>Ctrl</kbd> + <kbd>C</kbd>.
   - O Copiloto assume a voz tática de bordo e exibe instantaneamente:
     - 💥 **Munição Recomendada** (ex: Mísseis Scourge / EMP / Antimatter)
     - 🛸 **Tipo de Drones a Lançar** (Caldari/Kinetic, Gallente/Thermal, Amarr/EM ou Minmatar/Explosive)
     - 📏 **Distância Recomendada para Evitar Tiro** (Kiting a >25km ou fechar distância)
     - 🎯 **Prioridade de Abate** (Fragatas de teia e interceptação primeiro)

3. **Voz Sintetizada Tática (TTS Estilo 'Aura' ou 'Jarvis' em PT-BR):**
   - Substitui bipes e ruídos secos por instruções faladas com voz neural realista de computador de bordo.
   - **Dicas de Drones:** Avisa verbalmente se um drone estiver sob ataque (*"Atenção: drone sob ataque, recolha com Shift R"*), se os drones ficaram ociosos após a destruição do alvo (*"Alvo abatido, recolha os drones antes de saltar"*) ou se foram esquecidos no setor antes de um salto/dobra.
   - **Alertas de E-WAR:** Fala tática instantânea para *Warp Scrambler*, *Stasis Web*, *Neuts* e *ECM*.
   - **Identificação de Alvos:** Anuncia verbalmente a fraqueza primária do alvo ao escanear com Ctrl+C.
   - **Botão Rápido no HUD (`🎙️ Aura` / `🎙️ Jarvis`):** Clique direto no topo da janela para alternar entre a voz feminina da CCP (Aura) e a masculina britânica (Jarvis) ou silenciar.

4. **Oficial Tático de Voo & Balística (Tactical Flight Advisor):**
   - Ao receber o primeiro impacto inimigo, identifica instantaneamente o tipo exato da arma hostil (Blasters, Railguns, Autocannons, Artilharia, Lasers, Mísseis, Drones ou Triglaviano).
   - A **Aura / Jarvis** orienta em áudio a manobra exata a executar:
     - *Blasters/Autocannons:* Acionar Afterburner e fazer kiting a mais de 18 km para sair do alcance letal.
     - *Railguns/Beam Lasers:* Ligar Afterburner e estabelecer órbita transversal fechada a 10 km para quebrar o tracking speed das armas.
     - *Mísseis/Torpedos:* Manter velocidade máxima para mitigar o raio da explosão.
   - Exibição em tempo real no HUD de **Arma Detectada**, **Manobra Recomendada** e **Vetor de Voo**.

4. **Alarme Visual de E-WAR & Dano em Tempo Real:**

4. **Tradutor Tático de Missões via Ollama (IA Local):**
   - Cole a descrição da missão em inglês.
   - O modelo local extrai o objetivo em português, inimigos, tanque necessário e alertas de perigo.

5. **Consultor de Voo & Fittings:**
   - Pergunte ao seu navegador de bordo qualquer dúvida sobre velocidade transversal, fittings de naves ou mecânicas de combate.

---

## 🎮 Como Executar

No terminal:

```bash
cd /home/igor/Desktop/eve-copilot
./run.sh
```

Ou diretamente:
```bash
python3 /home/igor/Desktop/eve-copilot/app.py
```
