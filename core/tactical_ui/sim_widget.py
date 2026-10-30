# -*- coding: utf-8 -*-
"""
Visual relative motion simulator widget for EVE Online PvP Tactical Copilot.
Displays top-down view of player ship vs enemy ship, relative trajectory,
range rings, angular velocity, and interactive controls (AB, Web, Ammo, Mode).
"""
import math
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QSpinBox, QCheckBox, QFrame, QTextEdit
)
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from core.tactical.simulator import RelativeMotionSim

class SimCanvas(QWidget):
    def __init__(self, sim: RelativeMotionSim, parent=None):
        super().__init__(parent)
        self.sim = sim
        self.setMinimumHeight(240)
        self.setStyleSheet("background: #080a0f; border: 1px solid rgba(0, 229, 255, 0.2);")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # Escala: 1 pixel = escala em metros (ex: 15.000m cabem no widget)
        # raio visual máximo ~ min(cx, cy) - 20
        max_r = max(10, min(cx, cy) - 20)
        max_dist_m = 12000.0
        scale = max_r / max_dist_m

        # Fundo grade tática
        painter.setPen(QPen(QColor(30, 45, 60, 100), 1, Qt.PenStyle.DotLine))
        painter.drawLine(0, int(cy), w, int(cy))
        painter.drawLine(int(cx), 0, int(cx), h)

        # Anéis de alcance concêntricos (2km, 4km, 8km, 10km)
        rings = [2000, 4000, 7000, 10000]
        painter.setFont(QFont("Share Tech Mono", 8))
        for r_m in rings:
            r_px = r_m * scale
            painter.setPen(QPen(QColor(0, 229, 255, 40), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(cx, cy), r_px, r_px)
            painter.setPen(QColor(0, 229, 255, 80))
            painter.drawText(int(cx + r_px + 2), int(cy - 2), f"{r_m//1000}k")

        # Posição do jogador no centro visual (ou relativo)
        # Vamos manter o Player no centro (cx, cy) e desenhar o inimigo relativo a ele
        px, py = cx, cy

        # Inimigo relativo
        dx = self.sim.e[0] - self.sim.p[0]
        dy = self.sim.e[1] - self.sim.p[1]
        dist = math.hypot(dx, dy)

        ex = cx + dx * scale
        ey = cy + dy * scale

        # Linha de engajamento
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(px), int(py), int(ex), int(ey))

        # Vetores de velocidade
        # Jogador vel
        pvx, pvy = self.sim.pv[0], self.sim.pv[1]
        painter.setPen(QPen(QColor(0, 229, 255, 200), 2))
        painter.drawLine(int(px), int(py), int(px + pvx * scale * 4.0), int(py + pvy * scale * 4.0))

        # Inimigo vel
        evx, evil_y = self.sim.ev[0], self.sim.ev[1]
        painter.setPen(QPen(QColor(255, 75, 75, 200), 2))
        painter.drawLine(int(ex), int(ey), int(ex + evx * scale * 4.0), int(ey + evil_y * scale * 4.0))

        # Desenhar Player (Tormentor / Sua Nave)
        painter.setPen(QPen(QColor(0, 229, 255), 2))
        painter.setBrush(QBrush(QColor(0, 229, 255, 120)))
        painter.drawEllipse(QPointF(px, py), 6, 6)
        painter.setPen(QColor(0, 229, 255))
        painter.drawText(int(px - 30), int(py + 18), "VOCÊ")

        # Desenhar Inimigo
        painter.setPen(QPen(QColor(255, 75, 75), 2))
        painter.setBrush(QBrush(QColor(255, 75, 75, 120)))
        painter.drawEllipse(QPointF(ex, ey), 6, 6)
        painter.setPen(QColor(255, 120, 120))
        painter.drawText(int(ex - 25), int(ey - 10), f"INIMIGO ({int(dist)}m)")

        # Indicador de Webifier se ativo
        if self.sim.player_web_on_enemy:
            painter.setPen(QPen(QColor(255, 215, 0, 180), 1, Qt.PenStyle.DotLine))
            painter.drawEllipse(QPointF(ex, ey), 12, 12)


class TacticalSimulatorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sim = RelativeMotionSim()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_tick)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Barra de status superior
        top_box = QFrame()
        top_box.setStyleSheet("background: rgba(14, 18, 24, 0.7); border: 1px solid rgba(120, 120, 120, 0.2);")
        t_layout = QHBoxLayout(top_box)
        t_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_metrics = QLabel("DISTÂNCIA: 9.000 m | ANGULAR: 0.000 rad/s | SEU VETOR: 0 m/s")
        self.lbl_metrics.setStyleSheet("font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #00e5ff; font-weight: bold;")
        t_layout.addWidget(self.lbl_metrics)
        layout.addWidget(top_box)

        # Canvas visual
        self.canvas = SimCanvas(self.sim, self)
        layout.addWidget(self.canvas)

        # Controles táticos do piloto
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("background: rgba(12, 14, 18, 0.85); border: 1px solid rgba(120, 120, 120, 0.2);")
        c_layout = QVBoxLayout(ctrl_frame)
        c_layout.setContentsMargins(8, 6, 8, 6)
        c_layout.setSpacing(4)

        # Linha 1: Modos
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Comando Piloto:"))
        self.cmb_player_mode = QComboBox()
        self.cmb_player_mode.addItems(["KEEP AT RANGE", "ORBIT", "MANUAL LATERAL", "PARADO"])
        self.cmb_player_mode.currentTextChanged.connect(self._on_player_mode_changed)
        row1.addWidget(self.cmb_player_mode)

        row1.addWidget(QLabel("Distância Desejada (m):"))
        self.spn_range = QSpinBox()
        self.spn_range.setRange(500, 15000)
        self.spn_range.setSingleStep(500)
        self.spn_range.setValue(4000)
        self.spn_range.valueChanged.connect(self._on_range_changed)
        row1.addWidget(self.spn_range)

        row1.addWidget(QLabel("Comportamento Inimigo:"))
        self.cmb_enemy_mode = QComboBox()
        self.cmb_enemy_mode.addItems(["APROXIMAR", "MANTER DISTÂNCIA (KITE)", "ORBITAR VOCÊ", "PARADO"])
        self.cmb_enemy_mode.currentTextChanged.connect(self._on_enemy_mode_changed)
        row1.addWidget(self.cmb_enemy_mode)

        c_layout.addLayout(row1)

        # Linha 2: Módulos táticos
        row2 = QHBoxLayout()
        self.chk_enemy_ab = QCheckBox("Inimigo AB (Afterburner)")
        self.chk_enemy_ab.toggled.connect(self._on_enemy_ab_toggled)
        row2.addWidget(self.chk_enemy_ab)

        self.chk_player_web = QCheckBox("Aplicar Webifier no Inimigo")
        self.chk_player_web.toggled.connect(self._on_player_web_toggled)
        row2.addWidget(self.chk_player_web)

        self.chk_enemy_web = QCheckBox("Inimigo Aplicou Webifier em Você")
        self.chk_enemy_web.toggled.connect(self._on_enemy_web_toggled)
        row2.addWidget(self.chk_enemy_web)

        btn_reset = QPushButton("Resetar Simulação")
        btn_reset.clicked.connect(self._reset_sim)
        row2.addWidget(btn_reset)

        self.btn_run = QPushButton("▶ Iniciar")
        self.btn_run.clicked.connect(self._toggle_run)
        row2.addWidget(self.btn_run)

        c_layout.addLayout(row2)
        layout.addWidget(ctrl_frame)

        # Caixa explicativa e conselhos
        self.txt_explain = QTextEdit()
        self.txt_explain.setReadOnly(True)
        self.txt_explain.setMaximumHeight(85)
        self.txt_explain.setStyleSheet("font-family: 'Share Tech Mono', monospace; font-size: 10px; color: #d0d0d0;")
        layout.addWidget(self.txt_explain)

        self._update_text()

    def _toggle_run(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn_run.setText("▶ Iniciar")
        else:
            self.timer.start(50) # 20 FPS
            self.btn_run.setText("⏸ Pausar")

    def _reset_sim(self):
        self.sim.reset()
        self.sim.player_mode = self.cmb_player_mode.currentText()
        self.sim.player_range = float(self.spn_range.value())
        self.sim.enemy_mode = self.cmb_enemy_mode.currentText()
        self.sim.enemy_ab_on = self.chk_enemy_ab.isChecked()
        self.sim.player_web_on_enemy = self.chk_player_web.isChecked()
        self.sim.enemy_web_on_player = self.chk_enemy_web.isChecked()
        self.canvas.update()
        self._update_text()

    def _on_player_mode_changed(self, mode):
        self.sim.player_mode = mode
        self._update_text()

    def _on_enemy_mode_changed(self, mode):
        self.sim.enemy_mode = mode
        self._update_text()

    def _on_range_changed(self, val):
        self.sim.player_range = float(val)
        self._update_text()

    def _on_enemy_ab_toggled(self, checked):
        self.sim.enemy_ab_on = checked
        self.sim.set_flag("enemy_ab", checked, f"Inimigo {'ativou' if checked else 'desativou'} Afterburner.")
        self._update_text()

    def _on_player_web_toggled(self, checked):
        self.sim.player_web_on_enemy = checked
        self.sim.set_flag("p_web", checked, f"Você {'aplicou' if checked else 'desativou'} Stasis Webifier.")
        self._update_text()

    def _on_enemy_web_toggled(self, checked):
        self.sim.enemy_web_on_player = checked
        self.sim.set_flag("e_web", checked, f"Inimigo {'aplicou' if checked else 'desativou'} Webifier em você.")
        self._update_text()

    def _on_tick(self):
        self.sim.step(0.05)
        self.canvas.update()
        m = self.sim.metrics()
        self.lbl_metrics.setText(
            f"DISTÂNCIA: {int(m['distance'])} m | "
            f"ANGULAR: {m['angular']:.4f} rad/s | "
            f"RADIAL: {int(m['radial_speed'])} m/s | "
            f"SEU VETOR: {int(m['player_speed'])} m/s"
        )
        self._update_text()

    def _update_text(self):
        tips = self.sim.explain()
        recent_log = [msg for _, msg in self.sim.log[-2:]]
        content = "💡 ANÁLISE DE VOO:\n" + "\n".join(f"• {t}" for t in tips)
        if recent_log:
            content += "\n\n⚠️ EVENTOS RECENTES:\n" + "\n".join(f"» {l}" for l in recent_log)
        self.txt_explain.setText(content)
