"""
core/tactical_ui/tactics_widget.py - Painel Tático Unificado e Combat Mode.
Atende rigorosamente às Seções 4, 5, 6, 7, 8, 9, 10, 11 e 14 do Manual:
- Seletor de alvo inimigo com separação explícita de Fatos vs Hipóteses (Seção 4).
- Classificação de Risco (Verde/Amarelo/Vermelho) SEM percentuais de vitória (Seção 5).
- Motor de Decisão com Cenários A, B, C, D, E e recomendação de abordagem (Seção 7).
- Controle de Alcance: Kiting, Brawling, Scram Kiting e zonas de perigo (Seção 6).
- Ammo Advisor inteligente (Seção 8).
- Capacitor e Armor Advisors (Seções 9 e 10).
- Alertas Táticos em tempo real (Seção 11).
- Botão "COMBAT MODE" que alterna para visão ultra-limpa e focada em combate (Seção 14).
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QFrame, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from core.tactical import UNKNOWN, PENDING
from core.tactical.ships import ShipManager, template_for, recommended_range_m
from core.tactical.enemies import known_ships, analyze_enemy
from core.tactical.engine import (
    classify_engagement, decide, advise_movement, 
    recommend_ammo, capacitor_advice, armor_advice, generate_alerts, combat_card
)

class TacticalHUDWidget(QWidget):
    """Widget principal de Táticas e Análise de Combate."""
    combat_alert_triggered = pyqtSignal(str)
    tactical_guidance_ready = pyqtSignal(dict)

    def __init__(self, ship_mgr: ShipManager = None, parent=None):
        super().__init__(parent)
        self.ship_mgr = ship_mgr or ShipManager()
        names = self.ship_mgr.names()
        initial_ship = names[0] if names else "Tormentor"
        self.current_my_fit = self.ship_mgr.get(initial_ship) or template_for(initial_ship)
        self.enemy_name = "Kestrel"
        self.init_ui()

    def init_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)

        # Stacked layout para alternar entre Modo Normal e COMBAT MODE (Seção 14)
        self.stack = QStackedWidget()
        self.normal_view = self.create_normal_view()
        self.combat_mode_view = self.create_combat_mode_view()
        
        self.stack.addWidget(self.normal_view)
        self.stack.addWidget(self.combat_mode_view)
        
        self.main_layout.addWidget(self.stack)
        self.update_tactical_analysis()

    def create_normal_view(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Top Bar: Seletores e Botão Combat Mode
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Minha Nave:"))
        self.lbl_my_ship_name = QLabel(f"<b>{self.current_my_fit.get('ship', 'Nave')}</b>")
        self.lbl_my_ship_name.setStyleSheet("color: #58a6ff;")
        top_bar.addWidget(self.lbl_my_ship_name)

        top_bar.addSpacing(20)
        top_bar.addWidget(QLabel("Alvo Inimigo:"))
        self.combo_enemy = QComboBox()
        for name in known_ships():
            self.combo_enemy.addItem(name, name)
        
        idx = self.combo_enemy.findText(self.enemy_name)
        if idx >= 0:
            self.combo_enemy.setCurrentIndex(idx)
        self.combo_enemy.currentTextChanged.connect(self.on_enemy_changed)
        top_bar.addWidget(self.combo_enemy, 1)

        self.btn_toggle_combat_mode = QPushButton("⚡ MODO COMBATE (FOCADO)")
        self.btn_toggle_combat_mode.setStyleSheet(
            "background-color: #da3633; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px;"
        )
        self.btn_toggle_combat_mode.clicked.connect(self.enter_combat_mode)
        top_bar.addWidget(self.btn_toggle_combat_mode)

        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: Fatos vs Hipóteses + Avaliação de Risco
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        # Card de Risco & Decisão
        self.risk_box = QGroupBox("Avaliação Tática & Motor de Decisão (Cenários A-E)")
        risk_l = QVBoxLayout(self.risk_box)

        self.lbl_risk_level = QLabel("CLASSIFICAÇÃO: CALCULANDO...")
        self.lbl_risk_level.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        risk_l.addWidget(self.lbl_risk_level)

        self.lbl_decision = QLabel("Recomendação: ...")
        self.lbl_decision.setWordWrap(True)
        self.lbl_decision.setStyleSheet("font-size: 12px; padding: 4px 0;")
        risk_l.addWidget(self.lbl_decision)

        self.lbl_action = QLabel("Ação de Combate: ...")
        self.lbl_action.setWordWrap(True)
        self.lbl_action.setStyleSheet("color: #7ee787; font-weight: bold; padding-top: 4px;")
        risk_l.addWidget(self.lbl_action)

        left_layout.addWidget(self.risk_box)

        # Separador Fatos vs Hipóteses (Seção 4)
        intel_box = QGroupBox("Inteligência do Alvo: Fatos Garantidos vs Hipóteses Prováveis")
        intel_l = QVBoxLayout(intel_box)

        self.lbl_facts = QLabel("<b>FATOS GARANTIDOS (CASCO):</b><br>• ...")
        self.lbl_facts.setWordWrap(True)
        self.lbl_facts.setStyleSheet("color: #58a6ff; font-size: 11px;")
        intel_l.addWidget(self.lbl_facts)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #30363d;")
        intel_l.addWidget(line)

        self.lbl_hypo = QLabel("<b>HIPÓTESES PROVÁVEIS (METAGAME / FIT COMUM):</b><br>• ...")
        self.lbl_hypo.setWordWrap(True)
        self.lbl_hypo.setStyleSheet("color: #d29922; font-size: 11px;")
        intel_l.addWidget(self.lbl_hypo)

        left_layout.addWidget(intel_box, 1)
        splitter.addWidget(left_widget)

        # Painel Direito: Advisors (Alcance, Munição, Capacitor, Alertas)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        # Advisors Grid
        adv_box = QGroupBox("Advisors Táticos em Tempo Real")
        adv_l = QVBoxLayout(adv_box)

        self.lbl_range_adv = QLabel("<b>Alcance Recomendado:</b> ...")
        self.lbl_range_adv.setWordWrap(True)
        adv_l.addWidget(self.lbl_range_adv)

        self.lbl_ammo_adv = QLabel("<b>Munição Ideal:</b> ...")
        self.lbl_ammo_adv.setWordWrap(True)
        adv_l.addWidget(self.lbl_ammo_adv)

        self.lbl_cap_adv = QLabel("<b>Gerenciamento de Capacitor:</b> ...")
        self.lbl_cap_adv.setWordWrap(True)
        adv_l.addWidget(self.lbl_cap_adv)

        self.lbl_armor_adv = QLabel("<b>Ciclo do Armor Repairer:</b> ...")
        self.lbl_armor_adv.setWordWrap(True)
        adv_l.addWidget(self.lbl_armor_adv)

        right_layout.addWidget(adv_box)

        # Feed de Alertas Táticos Imediatos (Seção 11)
        alerts_box = QGroupBox("Alertas Táticos do Piloto (Exclusivo)")
        alerts_l = QVBoxLayout(alerts_box)
        self.lbl_tactical_alerts = QLabel("Nenhum alerta crítico ativo.")
        self.lbl_tactical_alerts.setWordWrap(True)
        self.lbl_tactical_alerts.setStyleSheet("padding: 8px; border-radius: 4px; background: #161b22; color: #8b949e;")
        alerts_l.addWidget(self.lbl_tactical_alerts)
        right_layout.addWidget(alerts_box, 1)

        splitter.addWidget(right_widget)
        splitter.setSizes([420, 420])
        layout.addWidget(splitter, 1)

        return w

    def create_combat_mode_view(self):
        """Visão simplificada com fonte ampliada para durante o combate (Seção 14)."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        # Header Combat Mode
        head = QHBoxLayout()
        lbl_cm_title = QLabel("⚡ MODO DE COMBATE ATIVO")
        lbl_cm_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f85149;")
        head.addWidget(lbl_cm_title)
        head.addStretch()

        btn_exit_cm = QPushButton("Sair do Modo Combate ✖")
        btn_exit_cm.setStyleSheet("background-color: #30363d; color: white; padding: 6px 12px; border-radius: 4px;")
        btn_exit_cm.clicked.connect(self.exit_combat_mode)
        head.addWidget(btn_exit_cm)
        layout.addLayout(head)

        # Cartão de Decisão Rápida
        self.cm_lbl_decision = QLabel("DECISÃO: ...")
        self.cm_lbl_decision.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.cm_lbl_decision.setStyleSheet("background: #161b22; padding: 12px; border-radius: 6px; border-left: 6px solid #58a6ff;")
        layout.addWidget(self.cm_lbl_decision)

        # Grade de Alvos e Distâncias
        grid = QHBoxLayout()

        self.cm_lbl_target = QLabel("ALVO:\n-")
        self.cm_lbl_target.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.cm_lbl_target.setStyleSheet("background: #0d1117; padding: 10px; border-radius: 6px;")
        grid.addWidget(self.cm_lbl_target, 1)

        self.cm_lbl_orbit = QLabel("DISTÂNCIA ÓTIMA:\n-")
        self.cm_lbl_orbit.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.cm_lbl_orbit.setStyleSheet("background: #0d1117; padding: 10px; border-radius: 6px; color: #7ee787;")
        grid.addWidget(self.cm_lbl_orbit, 1)

        self.cm_lbl_ammo = QLabel("MUNIÇÃO:\n-")
        self.cm_lbl_ammo.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.cm_lbl_ammo.setStyleSheet("background: #0d1117; padding: 10px; border-radius: 6px; color: #e3b341;")
        grid.addWidget(self.cm_lbl_ammo, 1)

        layout.addLayout(grid)

        # Banner de Alertas Críticos
        self.cm_lbl_alert = QLabel("STATUS: MONITORANDO REDE DE SENSORES")
        self.cm_lbl_alert.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self.cm_lbl_alert.setStyleSheet("background: #161b22; color: #58a6ff; padding: 12px; border-radius: 6px;")
        layout.addWidget(self.cm_lbl_alert, 1)

        return w

    def enter_combat_mode(self):
        self.stack.setCurrentIndex(1)

    def exit_combat_mode(self):
        self.stack.setCurrentIndex(0)

    def on_enemy_changed(self, enemy_name):
        self.enemy_name = enemy_name
        self.update_tactical_analysis()

    def set_active_fit(self, profile: dict):
        self.current_my_fit = profile
        self.lbl_my_ship_name.setText(f"<b>{profile.get('ship', 'Nave')}</b>")
        self.update_tactical_analysis()

    def update_tactical_analysis(self):
        if not self.current_my_fit:
            return

        enemy_intel = analyze_enemy(self.enemy_name, self.current_my_fit)
        
        ctx = {
            "player": self.current_my_fit,
            "enemy": self.enemy_name,
            "enemy_info": enemy_intel.get("raw"),
            "distance_m": 7500,
            "has_propulsion_advantage": True
        }

        # 1. Risco & Decisão
        risk_res = classify_engagement(ctx)
        dec_res = decide(ctx)

        level = risk_res.get("classification", "DESCONHECIDO")
        if level == "FAVORÁVEL":
            color = "#238636"
        elif level == "EQUILIBRADO":
            color = "#d29922"
        elif level == "DESFAVORÁVEL":
            color = "#da3633"
        else:
            color = "#58a6ff"

        self.risk_box.setStyleSheet(f"QGroupBox {{ border: 2px solid {color}; }}")
        
        # Formata os fatores que podem ser strings ou tuplas (sinal, descrição)
        factor_items = []
        for f in risk_res.get("factors", []):
            if isinstance(f, (list, tuple)) and len(f) >= 2:
                factor_items.append(f"{f[0]} {f[1]}")
            else:
                factor_items.append(str(f))
        
        reasons = "; ".join(factor_items) if factor_items else "Aguardando mais dados de telemetria"
        self.lbl_risk_level.setText(f"RISCO: {level} ({reasons})")
        self.lbl_risk_level.setStyleSheet(f"color: {color}; font-size: 13px;")

        scenarios_str = ", ".join(dec_res.get("scenarios", [])) or "—"
        why_str = " ".join(dec_res.get("why", []))
        self.lbl_decision.setText(f"<b>Cenário {scenarios_str}:</b> {why_str}")
        
        action_str = f"Movimento: {dec_res.get('movement', '—')} | Prioridade: {dec_res.get('priority', '—')}"
        self.lbl_action.setText(f"AÇÃO: {action_str}")

        # 2. Fatos vs Hipóteses
        facts = enemy_intel.get("facts", {})
        facts_text = "<b>FATOS GARANTIDOS (ATRIBUTOS DE CASCO):</b><br>"
        for k, v in facts.items():
            facts_text += f"• {k}: {v}<br>"
        self.lbl_facts.setText(facts_text)

        hypo = enemy_intel.get("hypotheses", {})
        hypo_text = "<b>HIPÓTESES PROVÁVEIS (METAGAME / FITTING COMUM):</b><br>"
        for k, v in hypo.items():
            if isinstance(v, list):
                hypo_text += f"• {k}: {', '.join(v)}<br>"
            else:
                hypo_text += f"• {k}: {v}<br>"
        self.lbl_hypo.setText(hypo_text)

        # 3. Advisors
        mov_res = advise_movement(ctx)
        mov_rec = mov_res.get("recommendation", "—")
        mov_why = " ".join(mov_res.get("why", []))
        self.lbl_range_adv.setText(
            f"<b>Comando de Movimento:</b> {mov_rec} ({mov_res.get('distance', '—')})<br>"
            f"<i>{mov_why}</i>"
        )

        ammo_res = recommend_ammo(distance_m=7500, profile=self.current_my_fit, enemy_info=enemy_intel.get("raw"))
        ammo_rec = ammo_res.get("recommended") or ammo_res.get("crystal") or "—"
        ammo_motive = " ".join(ammo_res.get("motive", []))
        self.lbl_ammo_adv.setText(
            f"<b>Munição Ideal:</b> <font color='#58a6ff'>{ammo_rec}</font><br><i>{ammo_motive}</i>"
        )

        cap_res = capacitor_advice(cap_pct=100.0, profile=self.current_my_fit)
        self.lbl_cap_adv.setText(f"<b>Capacitor:</b> {cap_res.get('action')}")

        armor_res = armor_advice(armor_pct=100.0, profile=self.current_my_fit)
        self.lbl_armor_adv.setText(f"<b>Armor Repairer:</b> {armor_res.get('action')} - <i>{armor_res.get('reason')}</i>")

        # Alertas Táticos
        state = {
            "profile": self.current_my_fit,
            "cap_pct": 100.0,
            "armor_pct": 100.0,
            "distance_m": 7500,
            "target_range_lost": False
        }
        alerts = generate_alerts(state)
        if alerts:
            al_txt = "<br>".join([f"⚠️ <b>{a.get('type')}:</b> {a.get('msg')} (<i>{a.get('action')}</i>)" for a in alerts])
            self.lbl_tactical_alerts.setText(al_txt)
            self.lbl_tactical_alerts.setStyleSheet("padding: 8px; border-radius: 4px; background: #2b1111; color: #f85149; border: 1px solid #da3633;")
        else:
            self.lbl_tactical_alerts.setText("✅ Nenhum alerta crítico ativo no momento.")
            self.lbl_tactical_alerts.setStyleSheet("padding: 8px; border-radius: 4px; background: #161b22; color: #7ee787;")

        # Atualiza Combat Mode View (Cartão de Combate da Seção 14)
        card = combat_card(ctx)
        card_dec = card.get("decision", {})
        self.cm_lbl_decision.setText(f"{scenarios_str}: {dec_res.get('movement', '—')} | {dec_res.get('priority', '—')}")
        self.cm_lbl_decision.setStyleSheet(f"background: #161b22; padding: 12px; border-radius: 6px; border-left: 6px solid {color};")
        self.cm_lbl_target.setText(f"ALVO:\n{self.enemy_name}")
        self.cm_lbl_orbit.setText(f"DISTÂNCIA / MOV:\n{card_dec.get('movement', '—')}\n({card_dec.get('distance', '—')})")
        self.cm_lbl_ammo.setText(f"MUNIÇÃO:\n{card_dec.get('ammo', ammo_rec)}")

        # Emite instrução de voz falada
        self.tactical_guidance_ready.emit({
            "target": self.enemy_name,
            "movement": mov_rec,
            "distance": mov_res.get('distance', '—'),
            "ammo": ammo_rec,
            "priority": dec_res.get('priority', '—'),
            "scenario": scenarios_str
        })

    def trigger_tactical_alert(self, alert_text: str):
        self.cm_lbl_alert.setText(f"⚠️ {alert_text}")
        self.cm_lbl_alert.setStyleSheet("background: #490202; color: #f85149; font-weight: bold; padding: 12px; border-radius: 6px;")
        self.combat_alert_triggered.emit(alert_text)
