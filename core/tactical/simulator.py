# -*- coding: utf-8 -*-
"""
Simulador visual de movimentação relativa (melhoria sugerida no manual).

Vista de cima de duas naves. Serve para ENSINAR o conceito (KAR vs Orbit, velocidade angular,
efeito de afterburner/webifier e troca de cristal) — não prevê resultados reais do jogo.
Os parâmetros (velocidades, % de web, inércia) são do simulador, ajustáveis, e não representam
atributos reais de nenhuma nave.

Modelo (simplificado e documentado):
  * Keep at Range: aproxima até a distância escolhida e então mantém (não recua sozinho).
  * Orbit: trajetória circular de raio R na velocidade máxima (ω = v/R, melhor caso).
  * Pilotagem manual (lateral): movimento perpendicular à linha de visada com correção suave de distância.
  * Inércia: aproximação exponencial da velocidade desejada.
"""
import math

from .engine import weapon_application


def _unit(x, y):
    n = math.hypot(x, y)
    return (x / n, y / n) if n > 1e-9 else (0.0, 0.0)


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class RelativeMotionSim:
    MODES_PLAYER = ("KEEP AT RANGE", "ORBIT", "MANUAL LATERAL", "PARADO")
    MODES_ENEMY = ("APROXIMAR", "MANTER DISTÂNCIA (KITE)", "ORBITAR VOCÊ", "PARADO")

    def __init__(self):
        self.reset()

    def reset(self):
        self.t = 0.0
        self.p = [0.0, 0.0]
        self.pv = [0.0, 0.0]
        self.e = [9000.0, 0.0]
        self.ev = [0.0, 0.0]
        self.player_mode = "KEEP AT RANGE"
        self.enemy_mode = "APROXIMAR"
        self.player_range = 4000.0
        self.enemy_range = 1000.0
        self.player_speed = 300.0
        self.enemy_speed = 350.0
        self.enemy_ab_on = False
        self.enemy_ab_bonus = 1.8          # fator de velocidade com AB (parâmetro do simulador)
        self.player_web_on_enemy = False   # você aplica webifier no inimigo
        self.enemy_web_on_player = False   # inimigo aplica webifier em você
        self.web_slow = 0.5                # fração removida da velocidade (parâmetro do simulador)
        self.tau = 1.5                     # inércia (s)
        self.log = []
        self.weapon = {"optimal_m": None, "falloff_m": None, "tracking_rad_s": None,
                       "sig_res_m": None, "target_sig_m": None, "nominal_dps": None}
        self._last_flags = {}

    # ----- controle -----
    def set_flag(self, name, value, message):
        if self._last_flags.get(name) != value:
            self._last_flags[name] = value
            self.log.append((round(self.t, 1), message))
            self.log = self.log[-40:]

    def _eff_speed(self, base, webbed, ab):
        s = base * (self.enemy_ab_bonus if ab else 1.0)
        return s * (1.0 - self.web_slow) if webbed else s

    def _desired(self, mode, pos, tpos, speed, rng):
        dx, dy = tpos[0] - pos[0], tpos[1] - pos[1]
        dist = math.hypot(dx, dy)
        ux, uy = _unit(dx, dy)          # em direção ao alvo
        tx, ty = -uy, ux                # tangente
        if mode == "PARADO":
            return 0.0, 0.0
        if mode in ("KEEP AT RANGE", "MANTER DISTÂNCIA (KITE)"):
            if mode == "MANTER DISTÂNCIA (KITE)" and dist < rng:
                return -ux * speed, -uy * speed   # kite recua para reabrir distância
            if dist > rng:
                return ux * speed, uy * speed
            return 0.0, 0.0                       # KAR: chegou ao range e para; não recua sozinho
        if mode == "APROXIMAR":
            return (ux * speed, uy * speed) if dist > rng else (0.0, 0.0)
        if mode in ("ORBIT", "ORBITAR VOCÊ"):
            err = dist - rng
            radial = _clamp(err * 0.5, -speed * 0.9, speed * 0.9)
            tang = math.sqrt(max(speed * speed - radial * radial, 0.0))
            return ux * radial + tx * tang, uy * radial + ty * tang
        if mode == "MANUAL LATERAL":
            err = dist - rng
            radial = _clamp(err * 0.3, -speed * 0.6, speed * 0.6)
            tang = math.sqrt(max(speed * speed - radial * radial, 0.0))
            sign = 1 if int(self.t // 6) % 2 == 0 else -1   # inverte o lado periodicamente
            return ux * radial + tx * tang * sign, uy * radial + ty * tang * sign
        return 0.0, 0.0

    # ----- física -----
    def step(self, dt=0.1):
        pspeed = self._eff_speed(self.player_speed, self.enemy_web_on_player, False)
        espeed = self._eff_speed(self.enemy_speed, self.player_web_on_enemy, self.enemy_ab_on)
        pd = self._desired(self.player_mode, self.p, self.e, pspeed, self.player_range)
        ed = self._desired(self.enemy_mode, self.e, self.p, espeed, self.enemy_range)
        k = 1.0 - math.exp(-dt / max(self.tau, 0.05))
        self.pv[0] += (pd[0] - self.pv[0]) * k
        self.pv[1] += (pd[1] - self.pv[1]) * k
        self.ev[0] += (ed[0] - self.ev[0]) * k
        self.ev[1] += (ed[1] - self.ev[1]) * k
        self.p[0] += self.pv[0] * dt
        self.p[1] += self.pv[1] * dt
        self.e[0] += self.ev[0] * dt
        self.e[1] += self.ev[1] * dt
        self.t += dt
        m = self.metrics()
        if self.player_mode == "KEEP AT RANGE" and m["distance"] < self.player_range * 0.75:
            self.set_flag("kar_lost", True, "Inimigo entrou abaixo do seu range: KEEP AT RANGE não recuou — range perdido.")
        elif self.player_mode == "KEEP AT RANGE" and m["distance"] >= self.player_range * 0.75:
            self.set_flag("kar_lost", False, "Range sob controle.")
        return m

    def metrics(self):
        dx, dy = self.e[0] - self.p[0], self.e[1] - self.p[1]
        dist = math.hypot(dx, dy)
        ux, uy = _unit(dx, dy)
        rvx, rvy = self.ev[0] - self.pv[0], self.ev[1] - self.pv[1]
        radial = rvx * ux + rvy * uy
        transversal = abs(-rvx * uy + rvy * ux)
        ang = transversal / dist if dist > 1 else 0.0
        res = {"distance": dist, "radial_speed": radial, "transversal": transversal, "angular": ang,
               "player_speed": math.hypot(*self.pv), "enemy_speed": math.hypot(*self.ev), "application": None}
        w = self.weapon
        if all(w.get(k) for k in ("optimal_m", "falloff_m", "tracking_rad_s", "sig_res_m", "target_sig_m")):
            res["application"] = weapon_application(
                optimal_m=w["optimal_m"], falloff_m=w["falloff_m"], tracking_rad_s=w["tracking_rad_s"],
                sig_res_m=w["sig_res_m"], target_sig_m=w["target_sig_m"], distance_m=max(dist, 1.0),
                angular_rad_s=ang, nominal_dps=w.get("nominal_dps"))
        return res

    def explain(self):
        """Texto didático dinâmico sobre o que está acontecendo."""
        m = self.metrics()
        tips = []
        if self.player_mode == "KEEP AT RANGE":
            tips.append("KEEP AT RANGE: você se aproxima até a distância escolhida e para; trajetórias tendem a ser retas, "
                        "o que facilita seu tracking, mas NÃO impede o inimigo de fechar a distância.")
        elif self.player_mode == "ORBIT":
            tips.append(f"ORBIT: velocidade angular ≈ {m['angular']:.3f} rad/s. Valor alto atrapalha torretas inimigas com tracking fraco "
                        "— e também as suas.")
        elif self.player_mode == "MANUAL LATERAL":
            tips.append("PILOTAGEM MANUAL: movimento lateral cria velocidade transversal e permite corrigir distância na hora.")
        if self.enemy_ab_on:
            tips.append("Inimigo com Afterburner: maior velocidade — ele fecha ou abre distância mais rápido.")
        if self.player_web_on_enemy:
            tips.append("Seu Webifier reduz a velocidade dele: ajuda a manter/fechar distância.")
        if self.enemy_web_on_player:
            tips.append("Webifier inimigo reduz sua velocidade: sua capacidade de controlar range cai.")
        app = m.get("application")
        if app and app.get("status") == "OK":
            tips.append(app["message"])
        return tips
