# -*- coding: utf-8 -*-
"""
EVE Online Realtime Combat & Game Log Monitor
Lê o log de combate mais recente do Lutris/Wine, limpa tags HTML do EVE e emite eventos de combate em tempo real.
Inclui telemetria e contador de acertos, erros (misses) e taxa de evasão transversal.
"""

import os
import glob
import re
import time
import threading
from collections import Counter

KNOWN_VERBS = {"hits", "glances off", "grazes", "penetrates", "smashes", "wrecks"}

def parse_log_session_stats(filepath):
    """
    Lê um arquivo de log completo do EVE Online e compila métricas acumuladas:
    - Total de disparos recebidos
    - Acertos (Hits) e Erros (Misses)
    - Taxa de evasão (%)
    - Dano total absorvido (HP)
    - Qualidade dos impactos (Wrecks, Smashes, Penetrates, Hits, Glances Off, Grazes)
    - Top atacantes
    """
    if not filepath or not os.path.exists(filepath):
        return None

    html_strip = re.compile(r'<[^>]+>')
    inc_hit_re = re.compile(r'\(combat\)\s+([0-9,.]+)\s+from\s+(.*?)(?:\s+-\s+(.*?))?$', re.IGNORECASE)
    inc_miss_re = re.compile(r'\(combat\)\s+(.*?)\s+misses you completely', re.IGNORECASE)

    total_hits = 0
    total_misses = 0
    total_dmg = 0.0
    quality_counts = Counter()
    attackers = Counter()

    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                clean = html_strip.sub('', line).strip()
                if not clean:
                    continue

                m_miss = inc_miss_re.search(clean)
                if m_miss:
                    total_misses += 1
                    att = m_miss.group(1).strip()
                    attackers[att] += 1
                    continue

                m_hit = inc_hit_re.search(clean)
                if m_hit:
                    total_hits += 1
                    try:
                        dmg = float(m_hit.group(1).replace(',', ''))
                    except ValueError:
                        dmg = 0.0
                    total_dmg += dmg
                    att = m_hit.group(2).strip()
                    attackers[att] += 1

                    rest = m_hit.group(3).strip() if m_hit.group(3) else 'Hits'
                    verb = 'Hits'
                    if ' - ' in rest:
                        _, v_part = rest.rsplit(' - ', 1)
                        if v_part.lower() in KNOWN_VERBS:
                            verb = v_part.title()
                    elif rest.lower() in KNOWN_VERBS:
                        verb = rest.title()
                    quality_counts[verb] += 1

        total_shots = total_hits + total_misses
        evasion_pct = (total_misses / total_shots * 100.0) if total_shots > 0 else 0.0
        hit_pct = (total_hits / total_shots * 100.0) if total_shots > 0 else 0.0

        return {
            "total_shots": total_shots,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "evasion_pct": evasion_pct,
            "hit_pct": hit_pct,
            "total_damage": total_dmg,
            "quality_counts": dict(quality_counts),
            "top_attackers": attackers.most_common(10)
        }
    except Exception as e:
        print(f"Erro ao analisar sessão de log {filepath}: {e}")
        return None

KNOWN_DRONE_KEYWORDS = (
    "hobgoblin", "warrior", "hornet", "acolyte", "hammerhead", "valkyrie",
    "infiltrator", "vespa", "ogre", "berserker", "praetor", "warden",
    "bouncer", "curator", "sentry", "gecko", "gardist", "drone"
)

class EveLogWatcher:
    def __init__(self, log_dir, on_event_callback=None):
        self.log_dir = log_dir
        self.on_event_callback = on_event_callback
        self.current_file = None
        self.file_handle = None
        self.running = False
        self.thread = None

        # Regex para limpar formatações HTML do EVE Online (<color=...>, <font size=...>, <b>, etc.)
        self.html_strip = re.compile(r'<[^>]+>')

        # Padrões de combate do EVE Online:
        # Ex 1: (combat) 46 from Caldari Navy Soldier - Scourge Light Missile - Hits
        # Ex 2: (combat) 46 from Guristas Soldier to Hobgoblin I - Scourge Light Missile - Hits
        self.incoming_damage_regex = re.compile(
            r'\(combat\)\s+([0-9,.]+)\s+from\s+(.*?)(?:\s+to\s+(.*?))?(?:\s+-\s+(.*?))?(?:$|\n)',
            re.IGNORECASE
        )
        # Ex: (combat) 67 to Caldari Navy Soldier - Hobgoblin I - Smashes
        self.outgoing_damage_regex = re.compile(
            r'\(combat\)\s+([0-9,.]+)\s+to\s+(.*?)(?:\s+-\s+(.*?))?(?:$|\n)',
            re.IGNORECASE
        )
        # E-War: warp scramble, web, neut, ecm, jammer
        self.ewar_regex = re.compile(
            r'(warp scramble|warp disrupt|stasis web|energy neutralize|energy drain|target paint|tracking disrupt|ecm|jammed|jamming)',
            re.IGNORECASE
        )
        # Detecção de tentativa de tackle/ewar contra a nave do jogador revelando o casco
        # Ex: "Warp disruption attempt from Keeper Rupture to Imperial Maller"
        self.player_ship_ewar_regex = re.compile(
            r'from\s+(.*?)\s+to\s+(?:Imperial|Republic|Caldari|Federation)?\s*([A-Za-z0-9\s]+)',
            re.IGNORECASE
        )
        # Seus tiros que erraram o alvo completamente (ex.: "(combat) Your Pulse Laser misses X completely")
        self.own_miss_regex = re.compile(
            r'\(combat\)\s+Your\s+(.*?)\s+misses\s+(.*?)\s+completely',
            re.IGNORECASE
        )
        # Tiros hostis que erraram você completamente
        self.miss_regex = re.compile(
            r'\(combat\)\s+(.*?)\s+misses you completely',
            re.IGNORECASE
        )
        # Drones engajando
        self.drone_engage_regex = re.compile(
            r'\(notify\)\s+Drones engaging\s+(.*)',
            re.IGNORECASE
        )
        # Drones ociosos / sem alvo
        self.drone_no_target_regex = re.compile(
            r'\(notify\)\s+Combat Drone cannot be commanded to work on a target that is no longer present',
            re.IGNORECASE
        )
        self.drone_not_present_regex = re.compile(
            r'\(notify\)\s+Drone cannot be commanded as it is not actually present',
            re.IGNORECASE
        )
        self.drone_not_responding_regex = re.compile(
            r'\(notify\)\s+Combat Drone does not respond to your commands',
            re.IGNORECASE
        )
        # Salto de stargate ou warp do piloto
        self.jump_regex = re.compile(
            r'(?:\(None\)|\(notify\))\s+Jumping from\s+(.*?)\s+to\s+(.*)',
            re.IGNORECASE
        )
        self.warp_regex = re.compile(
            r'\(notify\)\s+(?:Autopilot\s+)?warping to\s+(.*)',
            re.IGNORECASE
        )
        self.undock_regex = re.compile(
            r'\(None\)\s+Undocking from\s+(.*?)\s+to\s+(.*?)\s+solar system',
            re.IGNORECASE
        )
        self.drones_in_space = False

    def find_latest_log(self):
        if not os.path.exists(self.log_dir):
            return None
        files = glob.glob(os.path.join(self.log_dir, "*.txt"))
        if not files:
            return None
        # Retorna o arquivo mais recente
        return max(files, key=os.path.getmtime)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.file_handle:
            try:
                self.file_handle.close()
            except:
                pass

    def _monitor_loop(self):
        while self.running:
            latest = self.find_latest_log()
            if latest and latest != self.current_file:
                if self.file_handle:
                    self.file_handle.close()
                self.current_file = latest
                try:
                    # Carrega métricas acumuladas da sessão completa
                    stats = parse_log_session_stats(self.current_file)
                    if stats and self.on_event_callback:
                        self.on_event_callback({
                            "type": "session_stats_loaded",
                            "stats": stats,
                            "filename": os.path.basename(self.current_file)
                        })

                    self.file_handle = open(self.current_file, 'r', encoding='utf-8', errors='ignore')
                    # Lê os últimos 20 eventos para popular o chat inicial
                    all_lines = self.file_handle.readlines()
                    recent = all_lines[-20:] if len(all_lines) > 20 else all_lines
                    for r_line in recent:
                        self._parse_line(r_line, emit_stats=False)
                    
                    if self.on_event_callback:
                        self.on_event_callback({
                            "type": "system",
                            "message": f"Conectado ao log ativo: {os.path.basename(self.current_file)}"
                        })
                except Exception:
                    self.file_handle = None

            if self.file_handle:
                line = self.file_handle.readline()
                if line:
                    self._parse_line(line, emit_stats=True)
                else:
                    time.sleep(0.1)
            else:
                time.sleep(1.0)

    def _parse_line(self, line, emit_stats=True):
        if not line or not self.on_event_callback:
            return

        clean = self.html_strip.sub('', line).strip()
        if not clean:
            return

        # 0. Seu tiro errou o alvo (Outgoing Miss) — alimenta o alerta de TRACKING INEFICIENTE
        own_miss = self.own_miss_regex.search(clean)
        if own_miss:
            self.on_event_callback({
                "type": "own_shot_missed",
                "weapon": own_miss.group(1).strip(),
                "target": own_miss.group(2).strip(),
                "emit_stats": emit_stats,
                "raw": clean
            })
            return

        # 1. Inimigo errou o tiro contra você (Incoming Miss)
        miss_match = self.miss_regex.search(clean)
        if miss_match:
            attacker = miss_match.group(1).replace("(combat)", "").strip()
            self.on_event_callback({
                "type": "shot_missed",
                "attacker": attacker,
                "emit_stats": emit_stats,
                "raw": clean
            })
            return

        # 2. Dano Recebido (Incoming Damage / Hit)
        inc_match = self.incoming_damage_regex.search(clean)
        if inc_match:
            try:
                dmg = float(inc_match.group(1).replace(',', ''))
                attacker = inc_match.group(2).strip()
                target_entity = inc_match.group(3).strip() if inc_match.group(3) else ""
                rest = inc_match.group(4).strip() if inc_match.group(4) else "Hits"
                weapon = ""
                verb = "Hits"
                if " - " in rest:
                    w_part, v_part = rest.rsplit(" - ", 1)
                    if v_part.lower() in KNOWN_VERBS:
                        weapon = w_part.strip()
                        verb = v_part.title()
                    else:
                        weapon = rest.strip()
                elif rest.lower() in KNOWN_VERBS:
                    verb = rest.title()
                else:
                    weapon = rest.strip()

                # Verifica se o alvo atingido é um drone
                is_drone = False
                if target_entity and any(k in target_entity.lower() for k in KNOWN_DRONE_KEYWORDS):
                    is_drone = True

                if is_drone:
                    self.on_event_callback({
                        "type": "drone_under_attack",
                        "damage": dmg,
                        "attacker": attacker,
                        "drone": target_entity,
                        "weapon": weapon,
                        "verb": verb,
                        "emit_stats": emit_stats,
                        "raw": clean
                    })
                    return

                self.on_event_callback({
                    "type": "damage_received",
                    "damage": dmg,
                    "attacker": attacker,
                    "target": target_entity or "Sua Nave",
                    "weapon": weapon,
                    "verb": verb,
                    "emit_stats": emit_stats,
                    "raw": clean
                })
                return
            except Exception:
                pass

        # 3. Dano Causado (Outgoing Damage)
        out_match = self.outgoing_damage_regex.search(clean)
        if out_match:
            try:
                dmg = float(out_match.group(1).replace(',', ''))
                target = out_match.group(2).strip()
                raw_weapon = out_match.group(3).strip() if out_match.group(3) else "Sua Arma"
                # Separa arma e verbo de qualidade (ex: Dual Modulated Pulse Beam I - Smashes)
                weapon = raw_weapon
                quality = "Hits"
                if " - " in raw_weapon:
                    w_sub, v_sub = raw_weapon.rsplit(" - ", 1)
                    if v_sub.lower() in KNOWN_VERBS:
                        weapon = w_sub.strip()
                        quality = v_sub.title()
                
                self.on_event_callback({
                    "type": "damage_dealt",
                    "damage": dmg,
                    "target": target,
                    "weapon": weapon,
                    "quality": quality,
                    "raw": clean
                })
                return
            except Exception:
                pass

        # 4. Alertas de E-War e Identificação do Casco do Jogador
        ewar_match = self.ewar_regex.search(clean)
        if ewar_match:
            effect = ewar_match.group(1).upper()
            player_ship = None
            ps_match = self.player_ship_ewar_regex.search(clean)
            if ps_match:
                candidate = ps_match.group(2).strip()
                if candidate and candidate.lower() != "you!":
                    player_ship = candidate

            self.on_event_callback({
                "type": "ewar_alert",
                "effect": effect,
                "player_ship": player_ship,
                "raw": clean
            })
            return

        # 5. Drones engajando alvo
        drone_match = self.drone_engage_regex.search(clean)
        if drone_match:
            target = drone_match.group(1).strip()
            self.drones_in_space = True
            self.on_event_callback({
                "type": "target_spotted",
                "target": target,
                "note": "Drones engajando"
            })
            return

        # 6. Alvo morreu e os drones ficaram ociosos
        if self.drone_no_target_regex.search(clean):
            self.on_event_callback({
                "type": "drone_idle",
                "note": "Alvo destruído. Seus drones estão ociosos no espaço. Recolha antes de saltar."
            })
            return

        # 7. Drone fora de alcance ou não presente
        if self.drone_not_present_regex.search(clean) or self.drone_not_responding_regex.search(clean):
            self.on_event_callback({
                "type": "drone_not_present",
                "note": "Aviso: Drone não localizado no grid de combate."
            })
            return

        # 8. Salto de stargate
        jump_match = self.jump_regex.search(clean)
        if jump_match:
            orig = jump_match.group(1).strip()
            dest = jump_match.group(2).strip()
            drones_warning = self.drones_in_space
            self.drones_in_space = False
            self.on_event_callback({
                "type": "stargate_jump",
                "origin": orig,
                "destination": dest,
                "drones_were_out": drones_warning
            })
            return

        # 9. Entrada em warp
        warp_match = self.warp_regex.search(clean)
        if warp_match:
            dest = warp_match.group(1).strip()
            if self.drones_in_space:
                self.drones_in_space = False
                self.on_event_callback({
                    "type": "drone_left_behind",
                    "destination": dest
                })
            return

        # 10. Desacoplagem de estação
        undock_match = self.undock_regex.search(clean)
        if undock_match:
            station = undock_match.group(1).strip()
            solarsystem = undock_match.group(2).strip()
            self.drones_in_space = False
            self.on_event_callback({
                "type": "undocked",
                "station": station,
                "system": solarsystem
            })
            return
