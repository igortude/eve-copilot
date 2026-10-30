# -*- coding: utf-8 -*-
"""
EVE Online Hacking Minigame Engine
Simulador fiel do minigame de exploração (Relic & Data Sites) do EVE Online.
- Grade hexagonal de nós cibernéticos com topologia em rede
- Sistema de Coerência (HP) e Força (Ataque) do Vírus do jogador
- Subsistemas de defesa: Firewall, Anti-Virus, Nó Restaurador, Supressor de Vírus
- Utilitários: Auto-Reparo, Escudo Polimórfico, Kernel Rot, Vetor Secundário
- Indicadores de distância (Data Indicators 1-5)
- Regra do Seis (Rule of Six) oficial do EVE Online
- Núcleo do Sistema (System Core) e recompensas simuladas em ISK/Loot
"""

import os
import glob
import re
import random
import math
from collections import deque

# Tipos de Nós
NODE_EMPTY = "empty"
NODE_START = "start"
NODE_CORE = "core"
NODE_CACHE = "data_cache"
NODE_FIREWALL = "firewall"
NODE_ANTIVIRUS = "antivirus"
NODE_RESTORATION = "restoration"
NODE_SUPPRESSOR = "suppressor"

# Utilitários coletáveis
UTIL_REPAIR = "self_repair"
UTIL_SHIELD = "shield"
UTIL_KERNEL_ROT = "kernel_rot"
UTIL_VECTOR = "secondary_vector"

DIFFICULTIES = {
    "easy": {
        "name": "Data Site (High-Sec)",
        "node_count": 22,
        "core_hp": 60,
        "core_atk": 10,
        "defenses": [NODE_FIREWALL, NODE_FIREWALL, NODE_ANTIVIRUS],
        "caches": 2,
        "loot_min": 2_000_000,
        "loot_max": 8_000_000
    },
    "medium": {
        "name": "Relic Site (Low-Sec)",
        "node_count": 28,
        "core_hp": 80,
        "core_atk": 15,
        "defenses": [NODE_FIREWALL, NODE_FIREWALL, NODE_ANTIVIRUS, NODE_ANTIVIRUS, NODE_SUPPRESSOR],
        "caches": 3,
        "loot_min": 10_000_000,
        "loot_max": 35_000_000
    },
    "hard": {
        "name": "Sleeper / Ghost Site (Null/WH)",
        "node_count": 34,
        "core_hp": 100,
        "core_atk": 20,
        "defenses": [NODE_FIREWALL, NODE_ANTIVIRUS, NODE_ANTIVIRUS, NODE_RESTORATION, NODE_SUPPRESSOR, NODE_FIREWALL],
        "caches": 3,
        "loot_min": 30_000_000,
        "loot_max": 90_000_000
    }
}

ANALYZERS = {
    "t1": {"name": "Analyzer I (T1)", "hp": 60, "strength": 25},
    "t2": {"name": "Analyzer II (T2)", "hp": 100, "strength": 35},
    "elite": {"name": "Zeugma / Blackglass", "hp": 120, "strength": 40}
}

# 6 Direções da grade hexagonal axial (q, r)
AXIAL_DIRECTIONS = [
    (+1, 0), (+1, -1), (0, -1),
    (-1, 0), (-1, +1), (0, +1)
]

def axial_distance(n1, n2):
    q1, r1 = n1
    q2, r2 = n2
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

class HackingGame:
    def __init__(self, difficulty="medium", analyzer="t2"):
        self.difficulty_key = difficulty
        self.analyzer_key = analyzer
        self.diff_cfg = DIFFICULTIES.get(difficulty, DIFFICULTIES["medium"])
        self.analyzer_cfg = ANALYZERS.get(analyzer, ANALYZERS["t2"])

        self.max_hp = self.analyzer_cfg["hp"]
        self.hp = self.max_hp
        self.base_strength = self.analyzer_cfg["strength"]

        self.shield_charges = 0
        self.repair_turns = 0
        self.utilities = [] # Até 3 utilitários
        self.active_vectors = [] # Lista de nós sofrendo dano por turno

        self.nodes = {} # (q, r) -> dict de dados do nó
        self.edges = set() # frozenset({(q1, r1), (q2, r2)})
        self.start_coord = None
        self.core_coord = None

        self.game_over = False
        self.victory = False
        self.loot_isk = 0
        self.log_messages = []

        self._generate_map()
        self.add_log(f"⚡ Sistema cibernético inicializado: {self.diff_cfg['name']}.")
        self.add_log(f"🛡️ Vírus equipado: {self.analyzer_cfg['name']} ({self.hp} Coerência / {self.base_strength} Força).")

    @property
    def current_strength(self):
        # Cada Nó Supressor ativo reduz a força em 10 (mínimo de 10)
        suppressors = sum(
            1 for n in self.nodes.values() 
            if n["revealed"] and not n["defeated"] and n["type"] == NODE_SUPPRESSOR
        )
        return max(10, self.base_strength - (suppressors * 10))

    def add_log(self, msg):
        self.log_messages.append(msg)
        if len(self.log_messages) > 60:
            self.log_messages.pop(0)

    def _generate_map(self):
        """Gera um labirinto hexagonal orgânico com caminhos ramificados."""
        target_count = self.diff_cfg["node_count"]
        # Grade limite: largura ~ 7-8, altura ~ 5-6
        cols, rows = 7, 5
        grid_candidates = []
        for r in range(rows):
            r_offset = r // 2
            for q in range(-r_offset, cols - r_offset):
                grid_candidates.append((q, r))

        # Caminho gerado a partir de caminhada aleatória com conexões
        start = (0, random.randint(1, rows - 2))
        selected = {start}
        frontier = [start]

        while len(selected) < target_count and frontier:
            curr = frontier.pop(random.randint(0, len(frontier) - 1))
            neighbors = [(curr[0] + dq, curr[1] + dr) for dq, dr in AXIAL_DIRECTIONS]
            random.shuffle(neighbors)
            added_any = False
            for n in neighbors:
                if n in grid_candidates and n not in selected:
                    selected.add(n)
                    frontier.append(n)
                    added_any = True
                    if len(selected) >= target_count:
                        break
            if not added_any and selected:
                frontier.append(random.choice(list(selected)))

        # Conecta nós adjacentes com probabilidade para formar um grafo em malha
        nodes_list = list(selected)
        adj_map = {n: set() for n in nodes_list}

        for n1 in nodes_list:
            for dq, dr in AXIAL_DIRECTIONS:
                n2 = (n1[0] + dq, n1[1] + dr)
                if n2 in selected:
                    # Conecta quase todos os vizinhos imediatos para criar múltiplos caminhos
                    self.edges.add(frozenset({n1, n2}))
                    adj_map[n1].add(n2)
                    adj_map[n2].add(n1)

        # Garante que o grafo é totalmente conexo a partir de 'start'
        visited = set()
        queue = deque([start])
        while queue:
            curr = queue.popleft()
            if curr in visited:
                continue
            visited.add(curr)
            for nbr in adj_map[curr]:
                if nbr not in visited:
                    queue.append(nbr)

        # Remove ilhas desconectadas caso existam
        selected = visited
        nodes_list = list(selected)
        self.edges = {e for e in self.edges if all(n in selected for n in e)}
        adj_map = {n: {nbr for nbr in adj_map[n] if nbr in selected} for n in selected}

        # Encontra o nó mais distante do início para ser o NÚCLEO (Core)
        def bfs_distances(origin):
            dists = {origin: 0}
            q = deque([origin])
            while q:
                c = q.popleft()
                d = dists[c]
                for nb in adj_map[c]:
                    if nb not in dists:
                        dists[nb] = d + 1
                        q.append(nb)
            return dists

        dists_from_start = bfs_distances(start)
        farthest_candidates = sorted(nodes_list, key=lambda n: dists_from_start.get(n, 0), reverse=True)
        core = farthest_candidates[0]

        self.start_coord = start
        self.core_coord = core

        # Atribuição de tipos aos nós
        # Regra do Seis de EVE Online: Nós cercados por 6 vizinhos NUNCA contêm subsistemas de defesa normais!
        def has_six_neighbors(n):
            return len(adj_map[n]) >= 6

        available_for_defenses = [
            n for n in nodes_list 
            if n != start and n != core and not has_six_neighbors(n) and dists_from_start.get(n, 0) > 1
        ]
        random.shuffle(available_for_defenses)

        defenses_to_place = list(self.diff_cfg["defenses"])
        caches_to_place = self.diff_cfg["caches"]

        node_types = {}
        node_types[start] = NODE_START
        node_types[core] = NODE_CORE

        for d in defenses_to_place:
            if available_for_defenses:
                pos = available_for_defenses.pop()
                node_types[pos] = d

        # Caches podem cair em qualquer nó não ocupado
        available_for_caches = [n for n in nodes_list if n not in node_types and n != start and n != core]
        random.shuffle(available_for_caches)
        for _ in range(caches_to_place):
            if available_for_caches:
                pos = available_for_caches.pop()
                node_types[pos] = NODE_CACHE

        # Todos os outros são nós vazios com distância
        for n in nodes_list:
            if n not in node_types:
                node_types[n] = NODE_EMPTY

        # Inicializa estruturas de dados de cada nó
        for n in nodes_list:
            ntype = node_types[n]
            hp, max_hp, atk = 0, 0, 0
            if ntype == NODE_CORE:
                hp = max_hp = self.diff_cfg["core_hp"]
                atk = self.diff_cfg["core_atk"]
            elif ntype == NODE_FIREWALL:
                hp = max_hp = 60
                atk = 10
            elif ntype == NODE_ANTIVIRUS:
                hp = max_hp = 40
                atk = 20
            elif ntype == NODE_RESTORATION:
                hp = max_hp = 35
                atk = 10
            elif ntype == NODE_SUPPRESSOR:
                hp = max_hp = 40
                atk = 10

            self.nodes[n] = {
                "coord": n,
                "type": ntype,
                "revealed": (n == start),
                "defeated": (n == start),
                "hp": hp,
                "max_hp": max_hp,
                "attack": atk,
                "has_six_rule": has_six_neighbors(n),
                "neighbors": list(adj_map[n]),
                "distance_hint": 0 # Será recalculado dinamicamente
            }

        self._recalculate_distance_hints()

    def _recalculate_distance_hints(self):
        """Calcula para nós vazios a distância mais curta até o Core ou Utilitário."""
        # Alvos 'positivos' que geram leitura no indicador: Core e Caches não derrotados
        positive_targets = [
            n for n, d in self.nodes.items() 
            if d["type"] in [NODE_CORE, NODE_CACHE] and not d["defeated"]
        ]

        if not positive_targets:
            return

        for coord, data in self.nodes.items():
            if data["type"] == NODE_EMPTY:
                min_hops = 999
                # BFS simples no grafo
                q = deque([(coord, 0)])
                visited = {coord}
                while q:
                    c, dist = q.popleft()
                    if c in positive_targets and c != coord:
                        min_hops = min(min_hops, dist)
                        break
                    for nb in self.nodes[c]["neighbors"]:
                        if nb not in visited:
                            visited.add(nb)
                            q.append((nb, dist + 1))
                data["distance_hint"] = min(5, max(1, min_hops))

    def get_accessible_nodes(self):
        """Retorna as coordenadas dos nós que o jogador pode clicar/explorar atualmente."""
        accessible = set()
        for coord, data in self.nodes.items():
            if data["revealed"] and data["defeated"]:
                # Pode avançar para todos os vizinhos imediatos
                for nb in data["neighbors"]:
                    accessible.add(nb)
            elif data["revealed"] and not data["defeated"]:
                # Nó hostil revelado pode ser atacado
                accessible.add(coord)
        return accessible

    def click_node(self, coord):
        """Ação principal do jogador ao clicar em um nó na rede."""
        if self.game_over:
            return False, "O hack já foi finalizado."

        if coord not in self.nodes:
            return False, "Nó inexistente."

        data = self.nodes[coord]
        accessible = self.get_accessible_nodes()

        if coord not in accessible:
            return False, "Nó fora do alcance cibernético! Avance pelos nós adjacentes limpos."

        # CASO 1: NÓ AINDA NÃO REVELADO -> REVELAÇÃO
        if not data["revealed"]:
            data["revealed"] = True
            ntype = data["type"]

            if ntype == NODE_EMPTY:
                data["defeated"] = True
                self.add_log(f"🔍 Nó vazio explorado. Indicador de proximidade: [{data['distance_hint']}].")
                self._apply_end_of_turn()
                return True, "Nó vazio explorado."

            elif ntype == NODE_CACHE:
                # Cache misterioso: 60% utilitário, 40% armadilha
                if random.random() < 0.65:
                    tool = random.choice([UTIL_REPAIR, UTIL_SHIELD, UTIL_KERNEL_ROT, UTIL_VECTOR])
                    data["defeated"] = True
                    tool_names = {
                        UTIL_REPAIR: "Sub-rotina de Auto-Reparo (+30 HP)",
                        UTIL_SHIELD: "Escudo Polimórfico (Bloqueia 2 ataques)",
                        UTIL_KERNEL_ROT: "Kernel Rot (Causa dano massivo)",
                        UTIL_VECTOR: "Vetor Secundário (Dano contínuo)"
                    }
                    if len(self.utilities) < 3:
                        self.utilities.append(tool)
                        self.add_log(f"📦 Data Cache aberto: Adquirido [{tool_names[tool]}]!")
                    else:
                        self.add_log(f"📦 Data Cache aberto, mas inventário cheio ({tool_names[tool]} descartado).")
                else:
                    # Armadilha: transforma-se em Anti-Vírus
                    data["type"] = NODE_ANTIVIRUS
                    data["hp"] = data["max_hp"] = 40
                    data["attack"] = 20
                    self.add_log("⚠️ ALARME: Data Cache era uma armadilha e ativou um Anti-Vírus!")
                self._apply_end_of_turn()
                return True, "Data Cache aberto."

            elif ntype in [NODE_FIREWALL, NODE_ANTIVIRUS, NODE_RESTORATION, NODE_SUPPRESSOR]:
                names = {
                    NODE_FIREWALL: "Firewall Defensivo",
                    NODE_ANTIVIRUS: "Anti-Vírus Invasor",
                    NODE_RESTORATION: "Nó Restaurador",
                    NODE_SUPPRESSOR: "Supressor de Força"
                }
                self.add_log(f"🛡️ Subsistema hostil detectado: [{names[ntype]}] (HP: {data['hp']}, Atk: {data['attack']}).")
                self._apply_end_of_turn()
                return True, f"Subsistema {names[ntype]} revelado."

            elif ntype == NODE_CORE:
                self.add_log(f"💎 NÚCLEO DO SISTEMA LOCALIZADO! HP: {data['hp']} / Atk: {data['attack']}. Destrua-o para obter acesso!")
                self._apply_end_of_turn()
                return True, "Núcleo localizado!"

        # CASO 2: NÓ REVELADO E HOSTIL -> ATAQUE DIRETO
        elif not data["defeated"]:
            self._combat_exchange(coord)
            self._apply_end_of_turn()
            return True, "Ataque efetuado."

        return False, "Nó já explorado."

    def _combat_exchange(self, coord):
        """Troca de dano entre o jogador e um nó hostil."""
        data = self.nodes[coord]
        atk_power = self.current_strength
        retaliation = data["attack"]

        # Aplica dano no nó
        data["hp"] -= atk_power
        self.add_log(f"⚔️ Você atacou [{data['type'].upper()}] causando {atk_power} de dano!")

        # Verifica se o nó foi destruído
        if data["hp"] <= 0:
            data["hp"] = 0
            data["defeated"] = True
            self.add_log(f"💥 [{data['type'].upper()}] foi destruído com sucesso!")

            if data["type"] == NODE_CORE:
                # VITÓRIA!
                self.game_over = True
                self.victory = True
                self.loot_isk = random.randint(self.diff_cfg["loot_min"], self.diff_cfg["loot_max"])
                self.add_log(f"🎉 ACESSO CONCEDIDO! Sistema violado com sucesso!")
                self.add_log(f"💰 Recompensa estimada de exploração: {self.loot_isk:,.0f} ISK!")
                return
        else:
            # Retaliação do nó contra o jogador (se não foi absorvido por escudo)
            if self.shield_charges > 0:
                self.shield_charges -= 1
                self.add_log(f"🛡️ ESCUDO POLIMÓRFICO absorveu os {retaliation} de retaliação! (Cargas restantes: {self.shield_charges})")
            else:
                self.hp -= retaliation
                self.add_log(f"💥 Você sofreu {retaliation} de dano de retaliação do subsistema.")

            if self.hp <= 0:
                self.hp = 0
                self.game_over = True
                self.victory = False
                self.add_log("💀 COERÊNCIA ZERADA! Seu vírus foi purgado pelo sistema de defesa. HACK FALHOU!")

    def use_utility(self, index, target_coord=None):
        """Ativa uma ferramenta utilitária do inventário."""
        if self.game_over:
            return False, "Hack já finalizado."
        if index < 0 or index >= len(self.utilities):
            return False, "Índice de utilitário inválido."

        tool = self.utilities.pop(index)

        if tool == UTIL_REPAIR:
            heal = 30
            self.hp = min(self.max_hp, self.hp + heal)
            self.add_log(f"💉 Auto-Reparo ativado: +{heal} de Coerência restaurada (Atual: {self.hp}/{self.max_hp})!")
            return True, "Auto-Reparo utilizado."

        elif tool == UTIL_SHIELD:
            self.shield_charges += 2
            self.add_log(f"🛡️ Escudo Polimórfico ativado: As próximas {self.shield_charges} retaliações serão bloqueadas!")
            return True, "Escudo ativado."

        elif tool == UTIL_KERNEL_ROT:
            # Alvo padrão: se não fornecido, ataca o nó hostil com maior HP
            if not target_coord or target_coord not in self.nodes:
                hostiles = [
                    c for c, d in self.nodes.items() 
                    if d["revealed"] and not d["defeated"] and d["hp"] > 0
                ]
                if not hostiles:
                    self.utilities.insert(index, tool) # Devolve se não há alvo
                    return False, "Nenhum subsistema hostil visível para aplicar o Kernel Rot."
                target_coord = max(hostiles, key=lambda c: self.nodes[c]["hp"])

            target = self.nodes[target_coord]
            dmg = max(35, int(target["max_hp"] * 0.5))
            target["hp"] -= dmg
            self.add_log(f"☣️ KERNEL ROT aplicado em [{target['type'].upper()}]: Causou {dmg} de dano corrosivo imediato!")
            if target["hp"] <= 0:
                target["hp"] = 0
                target["defeated"] = True
                self.add_log(f"💥 [{target['type'].upper()}] dissolvido pelo Kernel Rot!")
                if target["type"] == NODE_CORE:
                    self.game_over = True
                    self.victory = True
                    self.loot_isk = random.randint(self.diff_cfg["loot_min"], self.diff_cfg["loot_max"])
                    self.add_log(f"🎉 ACESSO CONCEDIDO! Sistema violado com sucesso!")
            return True, "Kernel Rot executado."

        elif tool == UTIL_VECTOR:
            # Dano contínuo
            if not target_coord or target_coord not in self.nodes:
                hostiles = [
                    c for c, d in self.nodes.items() 
                    if d["revealed"] and not d["defeated"] and d["hp"] > 0
                ]
                if not hostiles:
                    self.utilities.insert(index, tool)
                    return False, "Nenhum alvo para o Vetor Secundário."
                target_coord = max(hostiles, key=lambda c: self.nodes[c]["hp"])

            self.active_vectors.append({"coord": target_coord, "turns": 3, "dmg": 20})
            self.add_log(f"⚡ Vetor Secundário anexado ao alvo! Causará 20 de dano por 3 turnos.")
            return True, "Vetor Secundário implantado."

        return False, "Utilitário desconhecido."

    def _apply_end_of_turn(self):
        """Aplica os efeitos passivos e temporais ao final de cada ação."""
        if self.game_over:
            return

        # 1. Processa Nós Restauradores ativos
        restorers = [
            c for c, d in self.nodes.items() 
            if d["revealed"] and not d["defeated"] and d["type"] == NODE_RESTORATION
        ]
        if restorers:
            for r in restorers:
                # Cura todos os outros nós de defesa feridos
                healed_any = False
                for c, d in self.nodes.items():
                    if d["revealed"] and not d["defeated"] and d["type"] != NODE_RESTORATION and d["hp"] < d["max_hp"]:
                        d["hp"] = min(d["max_hp"], d["hp"] + 15)
                        healed_any = True
                if healed_any:
                    self.add_log("💉 NÓ RESTAURADOR emitiu pulso: +15 HP para os subsistemas defensivos!")

        # 2. Processa Vetores Secundários ativos
        remaining_vectors = []
        for v in self.active_vectors:
            coord = v["coord"]
            if coord in self.nodes and not self.nodes[coord]["defeated"]:
                target = self.nodes[coord]
                target["hp"] -= v["dmg"]
                self.add_log(f"⚡ Vetor Secundário causou {v['dmg']} de dano contínuo em [{target['type'].upper()}].")
                if target["hp"] <= 0:
                    target["hp"] = 0
                    target["defeated"] = True
                    self.add_log(f"💥 [{target['type'].upper()}] eliminado pelo Vetor Secundário!")
                    if target["type"] == NODE_CORE:
                        self.game_over = True
                        self.victory = True
                        self.loot_isk = random.randint(self.diff_cfg["loot_min"], self.diff_cfg["loot_max"])
                        self.add_log(f"🎉 ACESSO CONCEDIDO! Sistema violado com sucesso!")
                else:
                    v["turns"] -= 1
                    if v["turns"] > 0:
                        remaining_vectors.append(v)
        self.active_vectors = remaining_vectors

        # Atualiza leituras de distância
        self._recalculate_distance_hints()

def auto_detect_hack_environment(log_dir=None, target_name=None, system_security=0.5):
    """
    Detecta automaticamente o módulo de hack do piloto (Analyzer I, II ou Zeugma) e a dificuldade/tipo
    do container (High-Sec / Low-Sec / Null-WH) sem que o jogador precise selecionar nada.
    """
    analyzer_key = "t1"
    analyzer_name = "Data/Relic Analyzer I"

    if log_dir and os.path.exists(log_dir):
        files = glob.glob(os.path.join(log_dir, "*.txt"))
        recent_files = sorted(files, key=os.path.getmtime, reverse=True)[:5]

        analyzer_pats = [
            (re.compile(r'(Zeugma|Blackglass|Ligature)', re.I), "elite", "Zeugma / Ligature Elite (120 HP)"),
            (re.compile(r'(Data Analyzer II|Relic Analyzer II)', re.I), "t2", "Analyzer II (T2 - 100 HP)"),
            (re.compile(r'(Data Analyzer I|Relic Analyzer I)', re.I), "t1", "Data Analyzer I (60 HP)")
        ]

        found_analyzer = False
        for fpath in recent_files:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    for pat, a_key, a_name in analyzer_pats:
                        if pat.search(content):
                            analyzer_key = a_key
                            analyzer_name = a_name
                            found_analyzer = True
                            break
            except Exception:
                pass
            if found_analyzer:
                break

    diff_key = "easy"
    diff_name = "Data Site (High-Sec)"
    reason = "High-Sec"

    if target_name:
        t_clean = target_name.lower().strip()
        is_relic = any(w in t_clean for w in ["relic", "debris", "monument", "remains", "ruin"])
        site_kind = "Relic Site" if is_relic else "Data Site"

        if any(w in t_clean for w in ["ruined", "decrepit", "survey", "simple", "basic", "training", "array"]):
            diff_key = "easy"
            diff_name = f"{site_kind} ({target_name.title()})"
            reason = f"Alvo: {target_name}"
        elif any(w in t_clean for w in ["battered", "standard", "major", "frontier"]):
            diff_key = "medium"
            diff_name = f"{site_kind} ({target_name.title()})"
            reason = f"Alvo: {target_name}"
        elif any(w in t_clean for w in ["intact", "sleeper", "ghost", "covert", "superior", "vault"]):
            diff_key = "hard"
            diff_name = f"Sleeper/Ghost ({target_name.title()})"
            reason = f"Alvo: {target_name}"
        else:
            if system_security >= 0.45:
                diff_key = "easy"
                diff_name = f"{site_kind} (High-Sec)"
            elif system_security >= 0.05:
                diff_key = "medium"
                diff_name = f"{site_kind} (Low-Sec)"
            else:
                diff_key = "hard"
                diff_name = f"{site_kind} (Null/WH)"
            reason = f"Alvo: {target_name} • Seg: {system_security:.1f}"
    else:
        if system_security >= 0.45:
            diff_key = "easy"
            diff_name = "Data Site (High-Sec)"
            reason = f"Segurança High-Sec ({system_security:.1f})"
        elif system_security >= 0.05:
            diff_key = "medium"
            diff_name = "Relic Site (Low-Sec)"
            reason = f"Segurança Low-Sec ({system_security:.1f})"
        else:
            diff_key = "hard"
            diff_name = "Sleeper / Ghost (Null/WH)"
            reason = f"Segurança Null/WH ({system_security:.1f})"

    return {
        "analyzer_key": analyzer_key,
        "analyzer_name": analyzer_name,
        "difficulty_key": diff_key,
        "difficulty_name": diff_name,
        "source_reason": reason
    }

