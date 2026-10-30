# -*- coding: utf-8 -*-
"""
EVE Online - Tactical Overview Copilot (Monochrome Photon Edition)
Construído estritamente sobre o modelo HTML/CSS fornecido pelo usuário:
- Estilo monocromático industrial fiel ao EVE Online (cinza escuro, semi-transparente, blur de fundo)
- Botão de Trava de Janela (Lock 🔒 / 🔓) para congelar a posição na tela
- Integração completa: Scanner de Overview (Ctrl+C), Logs em tempo real, Tradutor de Missões (Ollama)
  e Base de Dados tática (fraquezas, munições, drones e vetor de voo).
- Compatibilidade KDE Plasma / Wayland Always-on-Top contra Fixed Window.
"""

import sys
import os
import json
import subprocess
import threading
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QLineEdit, QTabWidget,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QSizeGrip, QAbstractItemView, QSpinBox, QComboBox, QProgressBar,
    QMenu
)
from PyQt6.QtGui import QFont, QCursor, QMouseEvent, QColor, QAction

from core.database import FACTIONS, analyze_target_text, analyze_incoming_weapon, WEAPON_TACTICS
from core.log_parser import EveLogWatcher, parse_log_session_stats
from core.target_scanner import TargetScanner
from core.mission_helper import OllamaAdvisor
from core.market_checker import quote_fitting_near, detect_system_from_logs
from core.hacking_ui import HackingTabWidget
from core.sound_player import SoundManager
from core.loot_evaluator import LootEvaluator, LootTriageReport

from core.tactical.ships import ShipManager
from core.tactical_ui.ships_widget import ShipManagerWidget
from core.tactical_ui.tactics_widget import TacticalHUDWidget
from core.tactical_ui.sim_widget import TacticalSimulatorWidget
from core.tactical_ui.fw_widget import FWAssistantWidget
from core.tactical_ui.training_widget import TrainingTabWidget

class LogBridge(QObject):
    event_received = pyqtSignal(dict)

class MarketBridge(QObject):
    quote_ready = pyqtSignal(object)
    quote_error = pyqtSignal(str)

class LootBridge(QObject):
    loot_ready = pyqtSignal(object)
    loot_error = pyqtSignal(str)

# ==========================================
# BARRA DE TÍTULO MONOCROMÁTICA DO USUÁRIO
# ==========================================
class OverviewHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setStyleSheet("""
            background: rgba(25, 25, 25, 0.50);
            border-bottom: 1px solid rgba(120, 120, 120, 0.15);
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 8, 2)
        layout.setSpacing(6)

        # Título da Barra
        self.title_lbl = QLabel("OVERVIEW [COPILOT - TACTICAL]")
        self.title_lbl.setStyleSheet("""
            color: #eaeaea; 
            font-family: 'Inter', 'Segoe UI', sans-serif; 
            font-size: 11px; 
            font-weight: 700; 
            letter-spacing: 0.5px;
        """)

        # Controles Monocromáticos do Usuário
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(6)

        # 0. Controle de Zoom / Tamanho da Letra (A- / 120% / A+)
        self.btn_font_dec = QPushButton("A-")
        self.btn_font_dec.setFixedSize(22, 20)
        self.btn_font_dec.setToolTip("Diminuir tamanho da letra (Ctrl -)")
        self.btn_font_dec.setStyleSheet(self._font_btn_style())
        self.btn_font_dec.clicked.connect(lambda: self.parent_window.change_font_size(-1))

        self.lbl_font_size = QLabel("120%")
        self.lbl_font_size.setToolTip("Tamanho atual da fonte (Ctrl + / - ou Ctrl + Scroll)")
        self.lbl_font_size.setStyleSheet("color: #888888; font-size: 10px; font-family: 'Share Tech Mono', monospace; min-width: 32px;")
        self.lbl_font_size.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_font_inc = QPushButton("A+")
        self.btn_font_inc.setFixedSize(22, 20)
        self.btn_font_inc.setToolTip("Aumentar tamanho da letra (Ctrl +)")
        self.btn_font_inc.setStyleSheet(self._font_btn_style())
        self.btn_font_inc.clicked.connect(lambda: self.parent_window.change_font_size(+1))

        controls_layout.addWidget(self.btn_font_dec)
        controls_layout.addWidget(self.lbl_font_size)
        controls_layout.addWidget(self.btn_font_inc)

        # Divisor sutil 1
        sep_font = QFrame()
        sep_font.setFrameShape(QFrame.Shape.VLine)
        sep_font.setFrameShadow(QFrame.Shadow.Sunken)
        sep_font.setStyleSheet("color: rgba(120, 120, 120, 0.25); max-height: 14px;")
        controls_layout.addWidget(sep_font)

        # Controle de Escuridão / Opacidade do Fundo (◐- / 88% / ◐+)
        self.btn_dark_dec = QPushButton("◐-")
        self.btn_dark_dec.setFixedSize(22, 20)
        self.btn_dark_dec.setToolTip("Diminuir escuridão / Fundo mais translúcido (Alt -)")
        self.btn_dark_dec.setStyleSheet(self._font_btn_style())
        self.btn_dark_dec.clicked.connect(lambda: self.parent_window.change_darkness(-0.05))

        init_op = int(round(self.parent_window.overlay_opacity * 100)) if hasattr(self.parent_window, 'overlay_opacity') else 88
        self.lbl_darkness = QLabel(f"{init_op}%")
        self.lbl_darkness.setToolTip("Escuridão do fundo da janela (Alt + / - ou clique para alternar)")
        self.lbl_darkness.setStyleSheet("color: #888888; font-size: 10px; font-family: 'Share Tech Mono', monospace; min-width: 30px;")
        self.lbl_darkness.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_darkness.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_darkness.mousePressEvent = lambda e: self.parent_window.cycle_darkness()

        self.btn_dark_inc = QPushButton("◐+")
        self.btn_dark_inc.setFixedSize(22, 20)
        self.btn_dark_inc.setToolTip("Aumentar escuridão / Fundo mais escuro e sólido (Alt +)")
        self.btn_dark_inc.setStyleSheet(self._font_btn_style())
        self.btn_dark_inc.clicked.connect(lambda: self.parent_window.change_darkness(+0.05))

        controls_layout.addWidget(self.btn_dark_dec)
        controls_layout.addWidget(self.lbl_darkness)
        controls_layout.addWidget(self.btn_dark_inc)

        # Divisor sutil 2
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setStyleSheet("color: rgba(120, 120, 120, 0.25); max-height: 14px;")
        controls_layout.addWidget(sep)

        # 1. Botão de Trava (Lock 🔓 / 🔒)
        self.btn_lock = QPushButton("🔓")
        self.btn_lock.setFixedSize(20, 20)
        self.btn_lock.setToolTip("Travar/Destravar posição da janela na tela")
        self.btn_lock.setStyleSheet(self._control_btn_style())
        self.btn_lock.clicked.connect(self.parent_window.toggle_lock)

        # 2. Botão Recolher (◽)
        self.btn_roll = QPushButton("◽")
        self.btn_roll.setFixedSize(20, 20)
        self.btn_roll.setToolTip("Recolher / Expandir Janela")
        self.btn_roll.setStyleSheet(self._control_btn_style())
        self.btn_roll.clicked.connect(self.parent_window.toggle_collapse)

        # 3. Botão Escanear Clipboard (📋)
        self.btn_clipboard = QPushButton("📋")
        self.btn_clipboard.setFixedSize(20, 20)
        self.btn_clipboard.setToolTip("Escanear área de transferência (Ctrl+C no jogo)")
        self.btn_clipboard.setStyleSheet(self._control_btn_style())
        self.btn_clipboard.clicked.connect(self.parent_window.manual_clipboard_scan)

        # 4. Botão Fechar (✕)
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setToolTip("Fechar")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #666666;
                border: none;
                font-family: 'Share Tech Mono', 'DejaVu Sans Mono', monospace;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                color: #f03e3e;
            }
        """)
        self.btn_close.clicked.connect(self.parent_window.close)

        # 0. Botão Menu de Janelas / Neocom (◈ JANELAS ▾)
        self.btn_windows = QPushButton("◈ JANELAS ▾")
        self.btn_windows.setToolTip("Gerenciador de Janelas do HUD (Ativar / Desativar módulos)")
        self.btn_windows.setStyleSheet("""
            QPushButton {
                background: rgba(35, 35, 35, 0.60);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.25);
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.15);
                color: #ffffff;
                border: 1px solid rgba(0, 229, 255, 0.60);
            }
        """)
        self.btn_windows.clicked.connect(self._show_windows_menu)

        # 0c. Botão de Voz Tática (🎙️ Aura / Jarvis / Mudo)
        current_persona = "aura"
        if hasattr(self.parent_window, "config"):
            current_persona = self.parent_window.config.get("voice_persona", "aura")
        is_voice_on = True
        if hasattr(self.parent_window, "config"):
            is_voice_on = self.parent_window.config.get("sound_alerts", True)
        label_text = f"🎙️ {current_persona.title()}" if is_voice_on else "🔇 Mudo"

        self.btn_voice = QPushButton(label_text)
        self.btn_voice.setFixedHeight(20)
        self.btn_voice.setToolTip("Voz do Copiloto (Clique para alternar Aura / Jarvis / Mudo)")
        self.btn_voice.setStyleSheet("""
            QPushButton {
                background: rgba(35, 35, 35, 0.60);
                color: #ffd43b;
                border: 1px solid rgba(255, 212, 59, 0.25);
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background: rgba(255, 212, 59, 0.15);
                color: #ffffff;
                border: 1px solid rgba(255, 212, 59, 0.60);
            }
        """)
        self.btn_voice.clicked.connect(lambda: self.parent_window.cycle_voice_persona())

        # Botão Destacar Aba (⧉)
        self.btn_detach = QPushButton("⧉")
        self.btn_detach.setFixedSize(20, 20)
        self.btn_detach.setToolTip("Destacar aba atual em janela flutuante independente")
        self.btn_detach.setStyleSheet(self._control_btn_style())
        self.btn_detach.clicked.connect(self._detach_current_tab)

        # Botão Re-acoplar Todas as Janelas (📥)
        self.btn_dock_all = QPushButton("📥")
        self.btn_dock_all.setFixedSize(20, 20)
        self.btn_dock_all.setToolTip("Acoplar todas as janelas flutuantes de volta como abas no Copilot")
        self.btn_dock_all.setStyleSheet("""
            QPushButton {
                background: rgba(35, 35, 35, 0.60);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.30);
                font-family: 'Share Tech Mono', monospace;
                font-size: 11px;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.25);
                color: #ffffff;
                border: 1px solid #00e5ff;
            }
        """)
        self.btn_dock_all.clicked.connect(lambda: self.parent_window.dock_all_windows())

        controls_layout.addWidget(self.btn_voice)
        controls_layout.addWidget(self.btn_windows)
        controls_layout.addWidget(self.btn_detach)
        controls_layout.addWidget(self.btn_dock_all)

        controls_layout.addWidget(self.btn_lock)
        controls_layout.addWidget(self.btn_roll)
        controls_layout.addWidget(self.btn_clipboard)
        controls_layout.addWidget(self.btn_close)

        layout.addWidget(self.title_lbl)
        layout.addStretch()
        layout.addLayout(controls_layout)

    def _show_windows_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121212;
                color: #cccccc;
                border: 1px solid rgba(120, 120, 120, 0.35);
                font-family: 'Inter', sans-serif;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 22px 5px 18px;
            }
            QMenu::item:selected {
                background-color: rgba(255, 255, 255, 0.10);
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(120, 120, 120, 0.20);
                margin: 4px 0px;
            }
        """)
        if hasattr(self.parent_window, "populate_windows_menu"):
            self.parent_window.populate_windows_menu(menu)
        menu.exec(QCursor.pos())

    def _detach_current_tab(self):
        if hasattr(self.parent_window, "detach_active_tab"):
            self.parent_window.detach_active_tab()

    def _font_btn_style(self):
        return """
            QPushButton {
                background: rgba(35, 35, 35, 0.60);
                color: #aaaaaa;
                border: 1px solid rgba(120, 120, 120, 0.20);
                font-family: 'Inter', sans-serif;
                font-size: 10px;
                font-weight: 700;
                padding: 0;
            }
            QPushButton:hover {
                background: rgba(60, 60, 60, 0.85);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.35);
            }
            QPushButton:pressed {
                background: rgba(20, 20, 20, 0.95);
            }
        """

    def _control_btn_style(self):
        return """
            QPushButton {
                background: transparent;
                color: #666666;
                border: none;
                font-family: 'Share Tech Mono', 'DejaVu Sans Mono', monospace;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.parent_window.is_locked:
                event.accept()
                return
            wh = self.parent_window.windowHandle()
            if wh and hasattr(wh, 'startSystemMove'):
                wh.startSystemMove()
            else:
                self.parent_window.drag_pos = event.globalPosition().toPoint() - self.parent_window.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.parent_window.is_locked and event.buttons() == Qt.MouseButton.LeftButton and hasattr(self.parent_window, 'drag_pos'):
            self.parent_window.move(event.globalPosition().toPoint() - self.parent_window.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.parent_window.toggle_collapse()
            event.accept()


# ==========================================
# JANELA DESTACADA / FLUTUANTE (EVE STYLE)
# ==========================================
# CABEÇALHO DA JANELA DESTACADA
# ==========================================
class EveDetachedHeader(QWidget):
    def __init__(self, detached_window):
        super().__init__(detached_window)
        self.detached_window = detached_window
        self.setFixedHeight(26)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        self.lbl_title = QLabel(f"HUD // {detached_window.title_str.upper()}")
        self.lbl_title.setStyleSheet("""
            color: #eaeaea; 
            font-family: 'Inter', 'Segoe UI', sans-serif; 
            font-size: 11px; 
            font-weight: 700; 
            letter-spacing: 0.5px;
        """)

        # Botão Re-acoplar em Aba com destaque visual EVE Neon Ciano
        self.btn_dock = QPushButton("📥 Acoplar")
        self.btn_dock.setFixedHeight(20)
        self.btn_dock.setToolTip(f"Re-acoplar '{detached_window.title_str}' como aba no Copilot Principal")
        self.btn_dock.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.18);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.45);
                font-family: 'Share Tech Mono', 'Inter', sans-serif;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 7px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.35);
                color: #ffffff;
                border: 1px solid #00e5ff;
            }
        """)
        self.btn_dock.clicked.connect(self.detached_window.dock_back)

        # Botão Travar (🔓 / 🔒)
        self.btn_lock = QPushButton("🔓")
        self.btn_lock.setFixedSize(20, 20)
        self.btn_lock.setToolTip("Travar posição da janela")
        self.btn_lock.setStyleSheet(self._btn_style())
        self.btn_lock.clicked.connect(self.detached_window.toggle_lock)

        # Botão Recolher (◽)
        self.btn_roll = QPushButton("◽")
        self.btn_roll.setFixedSize(20, 20)
        self.btn_roll.setToolTip("Recolher / Expandir")
        self.btn_roll.setStyleSheet(self._btn_style())
        self.btn_roll.clicked.connect(self.detached_window.toggle_collapse)

        # Botão Fechar / Re-acoplar (✕)
        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(20, 20)
        self.btn_close.setToolTip(f"Fechar janela flutuante e re-acoplar '{detached_window.title_str}' como aba no Copilot")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                font-family: 'Share Tech Mono', monospace;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                color: #f03e3e;
            }
        """)
        self.btn_close.clicked.connect(self.detached_window.dock_back)

        layout.addWidget(self.lbl_title)
        layout.addStretch()
        layout.addWidget(self.btn_dock)
        layout.addWidget(self.btn_lock)
        layout.addWidget(self.btn_roll)
        layout.addWidget(self.btn_close)

    def _btn_style(self):
        return """
            QPushButton {
                background: transparent;
                color: #888888;
                border: none;
                font-family: 'Share Tech Mono', monospace;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                color: #ffffff;
            }
        """

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121212;
                color: #cccccc;
                border: 1px solid rgba(120, 120, 120, 0.35);
                font-family: 'Inter', sans-serif;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 22px 5px 18px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 229, 255, 0.20);
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(120, 120, 120, 0.20);
                margin: 4px 0px;
            }
        """)
        act_dock = menu.addAction(f"📥 Re-acoplar '{self.detached_window.title_str}' como Aba")
        act_dock.triggered.connect(self.detached_window.dock_back)

        act_dock_all = menu.addAction("📥 Re-acoplar TODAS as Janelas no Copilot")
        act_dock_all.triggered.connect(self.detached_window.main_window.dock_all_windows)

        menu.addSeparator()
        lock_txt = "🔓 Destravar Posição" if self.detached_window.is_locked else "🔒 Travar Posição"
        act_lock = menu.addAction(lock_txt)
        act_lock.triggered.connect(self.detached_window.toggle_lock)

        act_roll = menu.addAction("◽ Recolher / Expandir")
        act_roll.triggered.connect(self.detached_window.toggle_collapse)

        menu.exec(event.globalPos())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.detached_window.is_locked:
                event.accept()
                return
            wh = self.detached_window.windowHandle()
            if wh and hasattr(wh, 'startSystemMove'):
                wh.startSystemMove()
            else:
                self.detached_window.drag_pos = event.globalPosition().toPoint() - self.detached_window.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.detached_window.is_locked and event.buttons() == Qt.MouseButton.LeftButton and hasattr(self.detached_window, 'drag_pos'):
            self.detached_window.move(event.globalPosition().toPoint() - self.detached_window.drag_pos)
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Duplo clique no cabeçalho também re-acopla a janela na principal
            self.detached_window.dock_back()
            event.accept()


# ==========================================
# JANELA DESTACADA / FLUTUANTE (EVE STYLE)
# ==========================================
class EveDetachedWindow(QWidget):
    BORDER_MARGIN = 6

    def __init__(self, key, title, content_widget, main_window):
        super().__init__()
        self.key = key
        self.title_str = title
        self.content_widget = content_widget
        self.main_window = main_window

        self.drag_pos = QPoint()
        self.is_collapsed = False
        self.is_locked = False
        self.saved_height = 450
        self.saved_width = 480

        self.setObjectName(f"eve-detached-{key}")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle(f"EVE HUD - {title}")
        self.setMinimumSize(300, 150)
        self.resize(self.saved_width, self.saved_height)

        self._build_ui()
        self.update_style()

        # Timer Keep-Above reforçado igual à janela principal
        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self._keep_above)
        self.top_timer.start(1000)

    def _keep_above(self):
        if self.isVisible() and not self.isMinimized():
            self.raise_()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.container = QFrame(self)
        self.container.setObjectName("detachedContainer")
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # Cabeçalho da janela destacada (classe dedicada)
        self.header = EveDetachedHeader(self)
        container_layout.addWidget(self.header)

        # Área de Conteúdo
        self.content_area = QWidget(self)
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.content_widget)
        self.content_widget.setVisible(True)

        # Rodapé com SizeGrip
        self.footer = QWidget(self)
        self.footer.setFixedHeight(18)
        f_layout = QHBoxLayout(self.footer)
        f_layout.setContentsMargins(8, 0, 4, 0)
        f_layout.setSpacing(4)
        lbl_status = QLabel("HUD Detached Mode")
        lbl_status.setStyleSheet("color: #555555; font-size: 9px; font-family: 'Inter', sans-serif;")
        grip = QSizeGrip(self)
        grip.setFixedSize(12, 12)
        f_layout.addWidget(lbl_status)
        f_layout.addStretch()
        f_layout.addWidget(grip)

        content_layout.addWidget(self.footer)
        container_layout.addWidget(self.content_area)
        root_layout.addWidget(self.container)

        self.container.setMouseTracking(True)
        self.container.installEventFilter(self)
        self.content_area.setMouseTracking(True)
        self.content_area.installEventFilter(self)

    def update_style(self):
        op = getattr(self.main_window, 'overlay_opacity', 0.88)
        d = getattr(self.main_window, 'font_delta', 2)
        f_base = max(9, 11 + d)

        self.container.setStyleSheet(f"""
            #detachedContainer {{
                background: rgba(14, 14, 14, {op:.2f});
                border: 1px solid rgba(120, 120, 120, 0.25);
            }}
        """)
        h_op = min(1.0, max(0.40, op * 0.95))
        self.header.setStyleSheet(f"""
            background: rgba(20, 20, 20, {h_op:.2f});
            border-bottom: 1px solid rgba(120, 120, 120, 0.15);
        """)
        self.footer.setStyleSheet(f"""
            background: rgba(10, 10, 10, {h_op:.2f});
            border-top: 1px solid rgba(120, 120, 120, 0.10);
        """)
        if hasattr(self.header, 'lbl_title'):
            self.header.lbl_title.setStyleSheet(f"""
                color: #eaeaea; 
                font-family: 'Inter', 'Segoe UI', sans-serif; 
                font-size: {f_base}px; 
                font-weight: 700; 
                letter-spacing: 0.5px;
            """)

    def toggle_lock(self):
        self.is_locked = not self.is_locked
        if self.is_locked:
            self.header.btn_lock.setText("🔒")
            self.header.lbl_title.setText(f"HUD // {self.title_str.upper()} [LOCKED]")
        else:
            self.header.btn_lock.setText("🔓")
            self.header.lbl_title.setText(f"HUD // {self.title_str.upper()}")

    def toggle_collapse(self):
        if not self.is_collapsed:
            self.saved_height = self.height()
            self.saved_width = self.width()
            self.content_area.hide()
            self.resize(self.width(), 26)
            self.header.btn_roll.setText("◻")
            self.is_collapsed = True
        else:
            self.content_area.show()
            self.resize(self.saved_width, self.saved_height)
            self.header.btn_roll.setText("◽")
            self.is_collapsed = False

    def dock_back(self):
        self.main_window.dock_window(self.key)

    def closeEvent(self, event):
        if hasattr(self, 'top_timer'):
            try:
                self.top_timer.stop()
            except Exception:
                pass
        if hasattr(self, 'main_window') and self.key in getattr(self.main_window, 'detached_windows', {}):
            self.main_window.dock_window(self.key)
        super().closeEvent(event)

    def _get_resize_edge(self, pos: QPoint):
        x, y = pos.x(), pos.y()
        w, h = self.width(), self.height()
        m = self.BORDER_MARGIN
        left = x <= m
        right = x >= w - m
        top = y <= m
        bottom = y >= h - m

        if top and left:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeFDiagCursor
        elif top and right:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeBDiagCursor
        elif bottom and left:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeBDiagCursor
        elif bottom and right:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeFDiagCursor
        elif left:
            return Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor
        elif right:
            return Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor
        elif top:
            return Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor
        elif bottom:
            return Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor
        return None, None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self.is_locked:
            edge, _ = self._get_resize_edge(event.pos())
            if edge:
                wh = self.windowHandle()
                if wh and hasattr(wh, 'startSystemResize'):
                    wh.startSystemResize(edge)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.is_locked:
            edge, cursor = self._get_resize_edge(event.pos())
            if cursor:
                self.setCursor(cursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        if not self.is_locked and hasattr(event, 'type'):
            et = event.type()
            if et == event.Type.MouseMove and hasattr(event, 'globalPosition'):
                win_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                edge, cursor = self._get_resize_edge(win_pos)
                if cursor:
                    self.setCursor(cursor)
                elif self.cursor().shape() != Qt.CursorShape.ArrowCursor:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            elif et == event.Type.MouseButtonPress and hasattr(event, 'button') and event.button() == Qt.MouseButton.LeftButton:
                if hasattr(event, 'globalPosition'):
                    win_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                    edge, _ = self._get_resize_edge(win_pos)
                    if edge:
                        wh = self.windowHandle()
                        if wh and hasattr(wh, 'startSystemResize'):
                            wh.startSystemResize(edge)
                            return True
        return super().eventFilter(obj, event)

# ==========================================
# JANELA PRINCIPAL COM DESIGN DO USUÁRIO
# ==========================================
class EveOverviewWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("eve-tactical-copilot")
        self.drag_pos = QPoint()
        self.is_collapsed = False
        self.is_locked = False
        self.expanded_height = 560
        self.expanded_width = 580
        self.load_config()
        self.combat_stats = {
            "total_shots": 0,
            "total_hits": 0,
            "total_misses": 0,
            "total_damage": 0.0,
            "quality_counts": {},
            "attackers": {},
            "session_filename": ""
        }

        self.advisor = OllamaAdvisor(host=self.config.get("ollama_host"), model=self.config.get("ollama_model"))
        self.bridge = LogBridge()
        self.bridge.event_received.connect(self.handle_combat_event)

        self.market_bridge = MarketBridge()
        self.market_bridge.quote_ready.connect(self.display_market_quote)
        self.market_bridge.quote_error.connect(self.handle_market_error)

        self.loot_evaluator = LootEvaluator()
        self.loot_bridge = LootBridge()
        self.loot_bridge.loot_ready.connect(self.display_loot_report)
        self.loot_bridge.loot_error.connect(self.handle_loot_error)
        self.current_loot_report = None
        self.current_loot_filter = "ALL"

        self.sound_manager = SoundManager(
            enabled=self.config.get("sound_alerts", True),
            persona=self.config.get("voice_persona", "aura")
        )

        # Registro de janelas modulares destacadas / abas (EVE HUD System)
        self.modules_meta = {
            "overview": {"title": "General", "default_tab_idx": 0},
            "tactics": {"title": "Tactics & Combat", "default_tab_idx": 1},
            "ships": {"title": "Ship Manager", "default_tab_idx": 2},
            "simulator": {"title": "Tactical Simulator", "default_tab_idx": 3},
            "fw": {"title": "FW & D-Scan", "default_tab_idx": 4},
            "training": {"title": "Training & AAR", "default_tab_idx": 5},
            "copilot": {"title": "Copilot", "default_tab_idx": 6},
            "market": {"title": "Market & Fit", "default_tab_idx": 7},
            "loot": {"title": "Loot Triage", "default_tab_idx": 8},
            "hacking": {"title": "Hacking", "default_tab_idx": 9},
            "combat": {"title": "Combat Log", "default_tab_idx": 10},
            "missions": {"title": "Missions", "default_tab_idx": 11},
            "advisor": {"title": "Advisor", "default_tab_idx": 12},
        }
        self.detached_windows = {} # key -> EveDetachedWindow
        self.module_widgets = {}    # key -> widget

        self.init_window_flags()
        self.init_ui()
        self.restore_windows_state()
        self.start_log_watcher()
        self.start_target_scanner()

        # Boas-vindas táticas com voz Sci-Fi
        if self.config.get("sound_alerts", True):
            self.sound_manager.speak(
                "Sistemas táticos integrados. Copiloto de bordo operacional.",
                cache_key="welcome",
                cooldown=10.0
            )

    def cycle_voice_persona(self):
        current = self.config.get("voice_persona", "aura")
        enabled = self.config.get("sound_alerts", True)
        if not enabled:
            self.config["sound_alerts"] = True
            self.config["voice_persona"] = "aura"
            self.sound_manager.enabled = True
            self.sound_manager.set_persona("aura")
            self.header.btn_voice.setText("🎙️ Aura")
            self.header.btn_voice.setStyleSheet("""
                QPushButton {
                    background: rgba(35, 35, 35, 0.60);
                    color: #ffd43b;
                    border: 1px solid rgba(255, 212, 59, 0.25);
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 1px 6px;
                }
                QPushButton:hover {
                    background: rgba(255, 212, 59, 0.15);
                    color: #ffffff;
                    border: 1px solid rgba(255, 212, 59, 0.60);
                }
            """)
            self.sound_manager.speak("Voz de bordo Aura ativada.", cache_key="welcome", cooldown=0.5)
        elif current == "aura":
            self.config["voice_persona"] = "jarvis"
            self.sound_manager.set_persona("jarvis")
            self.header.btn_voice.setText("🎙️ Jarvis")
            self.sound_manager.speak("Protocolo Jarvis ativado. À sua disposição, comandante.", cooldown=0.5)
        else:
            self.config["sound_alerts"] = False
            self.sound_manager.enabled = False
            self.header.btn_voice.setText("🔇 Mudo")
            self.header.btn_voice.setStyleSheet("""
                QPushButton {
                    background: rgba(35, 35, 35, 0.60);
                    color: #888888;
                    border: 1px solid rgba(120, 120, 120, 0.25);
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 1px 6px;
                }
            """)
        self.save_config()

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception:
            self.config = {
                "ollama_host": "http://localhost:11434",
                "ollama_model": "qwen2.5:7b",
                "log_dir": "/home/igor/Games/eve-online/drive_c/users/igor/Documents/EVE/logs/Gamelogs",
                "overlay_opacity": 0.65,
                "is_locked": False,
                "pos_x": 60,
                "pos_y": 60
            }
        self.is_locked = self.config.get("is_locked", False)
        self.font_delta = self.config.get("font_delta", 2)
        self.overlay_opacity = float(self.config.get("overlay_opacity", 0.88))
        self.windows_state = self.config.get("windows_state", {})

    def save_config(self):
        config_path = os.path.join(os.path.dirname(__file__), "config.json")
        try:
            self.config["is_locked"] = self.is_locked
            self.config["pos_x"] = self.x()
            self.config["pos_y"] = self.y()
            self.config["font_delta"] = self.font_delta
            self.config["overlay_opacity"] = self.overlay_opacity
            self._save_windows_state()
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def _save_windows_state(self):
        st = {}
        for key in self.modules_meta.keys():
            if key in self.detached_windows:
                dw = self.detached_windows[key]
                st[key] = {
                    "detached": True,
                    "visible": dw.isVisible(),
                    "x": dw.x(),
                    "y": dw.y(),
                    "w": dw.width(),
                    "h": dw.height(),
                    "locked": getattr(dw, "is_locked", False)
                }
            else:
                # Acoplado na janela principal
                st[key] = {
                    "detached": False,
                    "visible": True
                }
        self.config["windows_state"] = st

    def restore_windows_state(self):
        if not hasattr(self, "windows_state") or not isinstance(self.windows_state, dict):
            return
        for key, s in self.windows_state.items():
            if not isinstance(s, dict):
                continue
            if s.get("detached", False):
                self.detach_window(key)
                if key in self.detached_windows:
                    dw = self.detached_windows[key]
                    x = s.get("x")
                    y = s.get("y")
                    w = s.get("w")
                    h = s.get("h")
                    if x is not None and y is not None:
                        dw.move(x, y)
                    if w is not None and h is not None:
                        dw.resize(w, h)
                    if s.get("locked", False):
                        dw.toggle_lock()
                    if not s.get("visible", True):
                        dw.hide()
                    else:
                        dw.show()

    def populate_windows_menu(self, menu: QMenu):
        act_dock_all = menu.addAction("📥 Acoplar TODAS as Janelas em Abas")
        act_dock_all.triggered.connect(self.dock_all_windows)

        act_detach_all = menu.addAction("⧉ Destacar TODAS as Abas em Janelas")
        act_detach_all.triggered.connect(self.detach_all_windows)

        menu.addSeparator()

        for key, meta in self.modules_meta.items():
            title = meta["title"]
            is_detached = key in self.detached_windows
            if is_detached:
                dw = self.detached_windows[key]
                is_vis = dw.isVisible()
                state_str = f"📥 Acoplar '{title}' (Flutuante)" if is_vis else f"📥 Acoplar '{title}' (Oculta)"
                act = menu.addAction(state_str)
                act.triggered.connect(lambda checked, k=key: self.dock_window(k))
            else:
                is_in_tabs = self._is_tab_in_tabs(key)
                state_str = f"⧉ Destacar '{title}' (Aba)" if is_in_tabs else f"⧉ Destacar '{title}'"
                act = menu.addAction(state_str)
                act.triggered.connect(lambda checked, k=key: self.detach_window(k))

        menu.addSeparator()
        act_save = menu.addAction("💾 Salvar Layout Atual")
        act_save.triggered.connect(self.save_config)

    def _is_tab_in_tabs(self, key):
        w = self.module_widgets.get(key)
        if not w:
            return False
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == w:
                return True
        return False

    def toggle_module_window(self, key):
        if key in self.detached_windows:
            self.dock_window(key)
        else:
            self.detach_window(key)
        self.save_config()

    def detach_active_tab(self):
        curr_idx = self.tabs.currentIndex()
        if curr_idx < 0:
            return
        curr_widget = self.tabs.widget(curr_idx)
        for key, w in self.module_widgets.items():
            if w == curr_widget:
                self.detach_window(key)
                break

    def detach_window(self, key):
        if key in self.detached_windows:
            dw = self.detached_windows[key]
            dw.show()
            dw.raise_()
            dw.activateWindow()
            return

        w = self.module_widgets.get(key)
        if not w:
            return

        meta = self.modules_meta.get(key, {})
        title = meta.get("title", key)

        # Remove do QTabWidget
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == w:
                self.tabs.removeTab(i)
                break

        dw = EveDetachedWindow(key, title, w, self)
        # Posiciona próximo à janela principal
        dw.move(self.x() + self.width() + 15, self.y())
        dw.show()
        self.detached_windows[key] = dw
        self.save_config()

    def detach_all_windows(self):
        keys = list(self.modules_meta.keys())
        for k in keys:
            if k not in self.detached_windows:
                self.detach_window(k)
        self.save_config()

    def dock_window(self, key):
        if key not in self.detached_windows:
            return

        dw = self.detached_windows.pop(key)
        w = self.module_widgets.get(key)
        meta = self.modules_meta.get(key, {})
        title = meta.get("title", key)
        target_idx = meta.get("default_tab_idx", self.tabs.count())

        # 1. Parar timers da janela flutuante
        if hasattr(dw, 'top_timer'):
            try:
                dw.top_timer.stop()
            except Exception:
                pass

        # 2. Desvincular widget do layout e content_area da janela flutuante
        if hasattr(dw, 'content_area') and dw.content_area and dw.content_area.layout():
            try:
                dw.content_area.layout().removeWidget(w)
            except Exception:
                pass

        # 3. Re-anexar no QTabWidget
        if w:
            w.setParent(self.tabs)
            w.setVisible(True)

            already_in_tabs = False
            for i in range(self.tabs.count()):
                if self.tabs.widget(i) == w:
                    already_in_tabs = True
                    break

            if not already_in_tabs:
                insert_pos = self.tabs.count()
                for i in range(self.tabs.count()):
                    tab_w = self.tabs.widget(i)
                    tab_key = None
                    for k, mw in self.module_widgets.items():
                        if mw == tab_w:
                            tab_key = k
                            break
                    if tab_key:
                        tab_target_idx = self.modules_meta.get(tab_key, {}).get("default_tab_idx", 999)
                        if target_idx < tab_target_idx:
                            insert_pos = i
                            break
                self.tabs.insertTab(insert_pos, w, title)

            self.tabs.setCurrentWidget(w)
            w.show()
            self.tabs.show()

        # 4. Destruir janela flutuante
        try:
            dw.hide()
            dw.deleteLater()
        except Exception:
            pass

        # 5. Trazer janela principal para frente
        self.show()
        self.raise_()
        self.activateWindow()

        self.save_config()

    def dock_all_windows(self):
        keys = list(self.detached_windows.keys())
        for k in keys:
            self.dock_window(k)
        if self.tabs.count() > 0:
            self.tabs.setCurrentIndex(0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.save_config()

    def _on_tab_double_clicked(self, idx):
        if idx < 0:
            return
        w = self.tabs.widget(idx)
        for k, mw in self.module_widgets.items():
            if mw == w:
                self.detach_window(k)
                break

    def _on_tabs_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #121212;
                color: #cccccc;
                border: 1px solid rgba(120, 120, 120, 0.35);
                font-family: 'Inter', sans-serif;
                font-size: 11px;
                padding: 4px;
            }
            QMenu::item {
                padding: 5px 22px 5px 18px;
            }
            QMenu::item:selected {
                background-color: rgba(0, 229, 255, 0.20);
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(120, 120, 120, 0.20);
                margin: 4px 0px;
            }
        """)
        if idx >= 0:
            w = self.tabs.widget(idx)
            for k, mw in self.module_widgets.items():
                if mw == w:
                    title = self.modules_meta.get(k, {}).get("title", k)
                    act_detach = menu.addAction(f"⧉ Destacar aba '{title}' em janela flutuante")
                    act_detach.triggered.connect(lambda checked, key=k: self.detach_window(key))
                    break
        act_dock_all = menu.addAction("📥 Acoplar Todas as Janelas Soltas")
        act_dock_all.triggered.connect(self.dock_all_windows)
        menu.exec(self.tabs.mapToGlobal(pos))

    def notify_window_visibility_changed(self, key, visible):
        self.save_config()

    def navigate_to_module(self, key):
        if key in self.detached_windows:
            dw = self.detached_windows[key]
            dw.show()
            dw.raise_()
            dw.activateWindow()
        else:
            w = self.module_widgets.get(key)
            if w and self._is_tab_in_tabs(key):
                self.tabs.setCurrentWidget(w)
            elif w:
                self.dock_window(key)
                self.tabs.setCurrentWidget(w)

    def get_table_row_height(self):
        return max(20, 22 + int(self.font_delta * 1.8))

    def change_font_size(self, step):
        new_delta = self.font_delta + step
        if -2 <= new_delta <= 8:
            self.font_delta = new_delta
            self.update_ui_fonts()
            self.save_config()

    def set_font_size_delta(self, val):
        self.font_delta = max(-2, min(8, val))
        self.update_ui_fonts()
        self.save_config()

    def change_darkness(self, step):
        new_op = round(self.overlay_opacity + step, 2)
        new_op = max(0.40, min(1.00, new_op))
        self.overlay_opacity = new_op
        self.update_ui_fonts()
        self.save_config()

    def cycle_darkness(self):
        presets = [0.70, 0.85, 0.95, 1.00, 0.55]
        for p in presets:
            if p > self.overlay_opacity + 0.02:
                self.overlay_opacity = p
                self.update_ui_fonts()
                self.save_config()
                return
        self.overlay_opacity = presets[0]
        self.update_ui_fonts()
        self.save_config()

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.change_font_size(+1)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Minus:
                self.change_font_size(-1)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_0:
                self.set_font_size_delta(0)
                event.accept()
                return
        elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
            if event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.change_darkness(+0.05)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Minus:
                self.change_darkness(-0.05)
                event.accept()
                return
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            num_degrees = event.angleDelta().y() / 8
            num_steps = num_degrees / 15
            if num_steps > 0:
                self.change_font_size(+1)
            elif num_steps < 0:
                self.change_font_size(-1)
            event.accept()
            return
        elif event.modifiers() & Qt.KeyboardModifier.AltModifier:
            num_degrees = event.angleDelta().y() / 8
            num_steps = num_degrees / 15
            if num_steps > 0:
                self.change_darkness(+0.05)
            elif num_steps < 0:
                self.change_darkness(-0.05)
            event.accept()
            return
        super().wheelEvent(event)

    def update_ui_fonts(self):
        d = self.font_delta
        f_base = max(9, 11 + d)
        f_small = max(8, 10 + d)
        f_title = max(10, 12 + d)
        f_large = max(11, 13 + d)

        # 1. Atualiza stylesheet do container principal
        if hasattr(self, 'overview_container'):
            self.overview_container.setStyleSheet(self._generate_container_stylesheet(f_base, f_small, f_title, f_large))

        # 2. Atualiza elementos específicos
        self._update_cards_stylesheet(f_base, f_small, f_title, f_large)

        # 3. Atualiza altura de linhas das tabelas
        row_h = self.get_table_row_height()
        if hasattr(self, 'table'):
            for r in range(self.table.rowCount()):
                self.table.setRowHeight(r, row_h)
        if hasattr(self, 'market_table'):
            for r in range(self.market_table.rowCount()):
                self.market_table.setRowHeight(r, row_h)

        # 4. Atualiza indicador no header
        if hasattr(self, 'header') and hasattr(self.header, 'lbl_font_size'):
            pct = 100 + (d * 10)
            self.header.lbl_font_size.setText(f"{pct}%")

        # 5. Atualiza indicador de escuridão no header
        if hasattr(self, 'header') and hasattr(self.header, 'lbl_darkness'):
            dark_pct = int(round(self.overlay_opacity * 100))
            self.header.lbl_darkness.setText(f"{dark_pct}%")

        # 6. Atualiza estilo em todas as janelas destacadas ativas
        if hasattr(self, 'detached_windows'):
            for dw in self.detached_windows.values():
                dw.update_style()

    def _generate_container_stylesheet(self, f_base, f_small, f_title, f_large):
        pad_tab = max(3, 4 + int(self.font_delta * 0.5))
        return f"""
            #overviewWindow {{
                background: rgba(14, 14, 14, {self.overlay_opacity:.2f});
                border: 1px solid rgba(120, 120, 120, 0.25);
            }}
            QLabel {{
                color: #cccccc;
                font-family: 'Inter', 'Segoe UI', sans-serif;
                font-size: {f_base}px;
            }}
            /* Abas de Navegação */
            QTabWidget::pane {{
                border: none;
                border-bottom: 1px solid rgba(120, 120, 120, 0.15);
                background: transparent;
            }}
            QTabBar {{
                background: rgba(10, 10, 10, 0.40);
                border-bottom: 1px solid rgba(120, 120, 120, 0.15);
            }}
            QTabBar::tab {{
                padding: {pad_tab}px {pad_tab + 8}px;
                font-size: {f_base}px;
                font-weight: 600;
                background: transparent;
                border: none;
                color: #777777;
                border-bottom: 2px solid transparent;
            }}
            QTabBar::tab:hover {{
                color: #bbbbbb;
                background: rgba(255, 255, 255, 0.02);
            }}
            QTabBar::tab:selected {{
                color: #ffffff;
                border-bottom: 2px solid #ffffff;
                background: rgba(255, 255, 255, 0.05);
            }}
            /* Tabela Estilo Terminal EVE */
            QTableWidget {{
                background: transparent;
                color: #cccccc;
                gridline-color: rgba(120, 120, 120, 0.05);
                border: none;
                font-family: 'Share Tech Mono', 'DejaVu Sans Mono', 'Ubuntu Mono', monospace;
                font-size: {f_base}px;
                selection-background-color: rgba(255, 255, 255, 0.08);
                selection-color: #ffffff;
            }}
            QHeaderView::section {{
                background: rgba(20, 20, 20, 0.60);
                color: #888888;
                padding: 3px 8px;
                font-weight: normal;
                border: none;
                border-bottom: 1px solid rgba(120, 120, 120, 0.15);
                border-right: 1px solid rgba(120, 120, 120, 0.05);
                font-family: 'Share Tech Mono', monospace;
                font-size: {f_base}px;
            }}
            QHeaderView::section:hover {{
                background: rgba(40, 40, 40, 0.60);
                color: #ffffff;
            }}
            QTextEdit, QLineEdit {{
                background-color: rgba(12, 12, 12, 0.85);
                color: #eaeaea;
                border: 1px solid rgba(120, 120, 120, 0.20);
                padding: 5px;
                font-size: {f_base}px;
                font-family: 'Share Tech Mono', monospace;
            }}
            QTextEdit:focus, QLineEdit:focus {{
                border: 1px solid rgba(255, 255, 255, 0.35);
            }}
            QPushButton {{
                background: rgba(25, 25, 25, 0.70);
                color: #cccccc;
                border: 1px solid rgba(120, 120, 120, 0.25);
                font-size: {f_base}px;
                font-family: 'Inter', sans-serif;
                font-weight: 600;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                background: rgba(45, 45, 45, 0.85);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.30);
            }}
            QPushButton:pressed {{
                background: rgba(15, 15, 15, 0.95);
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 5px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(120, 120, 120, 0.20);
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(120, 120, 120, 0.40);
            }}
        """

    def _update_cards_stylesheet(self, f_base, f_small, f_title, f_large):
        if hasattr(self, 'header') and hasattr(self.header, 'title_lbl'):
            self.header.title_lbl.setStyleSheet(f"""
                color: #eaeaea; 
                font-family: 'Inter', 'Segoe UI', sans-serif; 
                font-size: {f_base}px; 
                font-weight: 700; 
                letter-spacing: 0.5px;
            """)

        if hasattr(self, 'lbl_footer_left'):
            self.lbl_footer_left.setStyleSheet(f"font-size: {f_small}px; color: #666666; font-family: 'Inter', sans-serif;")
        if hasattr(self, 'lbl_footer_right'):
            self.lbl_footer_right.setStyleSheet(f"font-size: {f_small}px; color: #666666; font-family: 'Inter', sans-serif;")

        if hasattr(self, 'lbl_target_tag'):
            self.lbl_target_tag.setStyleSheet(f"color: #f03e3e; font-size: {f_large}px; font-weight: bold;")
        if hasattr(self, 'lbl_target_title'):
            self.lbl_target_title.setStyleSheet(f"font-size: {f_title}px; font-weight: 700; color: #ffffff; font-family: 'Share Tech Mono', monospace;")
        if hasattr(self, 'lbl_target_subinfo'):
            self.lbl_target_subinfo.setStyleSheet(f"font-size: {f_small}px; color: #888888;")
        if hasattr(self, 'lbl_ammo_advice'):
            self.lbl_ammo_advice.setStyleSheet(f"font-size: {f_base}px; color: #dddddd; font-family: 'Inter', sans-serif;")
        if hasattr(self, 'lbl_drone_advice'):
            self.lbl_drone_advice.setStyleSheet(f"font-size: {f_base}px; color: #bbbbbb; font-family: 'Inter', sans-serif;")
        if hasattr(self, 'lbl_flight_advice'):
            self.lbl_flight_advice.setStyleSheet(f"font-size: {f_base}px; color: #cccccc; font-family: 'Inter', sans-serif;")
        if hasattr(self, 'lbl_ewar_advice'):
            self.lbl_ewar_advice.setStyleSheet(f"font-size: {f_small}px; color: #ff8787;")

        if hasattr(self, 'lbl_market_fit_name'):
            self.lbl_market_fit_name.setStyleSheet(f"font-size: {f_title}px; font-weight: bold; color: #ffffff; font-family: 'Share Tech Mono', monospace;")
        if hasattr(self, 'lbl_price_radius'):
            self.lbl_price_radius.setStyleSheet(f"font-size: {f_base}px; color: #40c057; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        if hasattr(self, 'lbl_items_found'):
            self.lbl_items_found.setStyleSheet(f"font-size: {f_base}px; color: #ffd43b; font-family: 'Share Tech Mono', monospace;")
        if hasattr(self, 'lbl_market_rec'):
            self.lbl_market_rec.setStyleSheet(f"font-size: {f_small}px; color: #888888;")
        if hasattr(self, 'txt_origin_system'):
            self.txt_origin_system.setStyleSheet(f"padding: 2px 4px; font-size: {f_base}px;")
        if hasattr(self, 'cmb_security'):
            self.cmb_security.setStyleSheet(f"""
                QComboBox {{
                    background: rgba(12, 12, 12, 0.85);
                    color: #eaeaea;
                    border: 1px solid rgba(120, 120, 120, 0.20);
                    font-family: 'Share Tech Mono', monospace;
                    font-size: {f_small}px;
                    padding: 1px 4px;
                }}
                QComboBox QAbstractItemView {{
                    background: #141414;
                    color: #cccccc;
                    selection-background-color: #2b3b4c;
                    border: 1px solid #333333;
                    font-size: {f_base}px;
                }}
            """)


        if hasattr(self, 'txt_combat'):
            self.txt_combat.setStyleSheet(f"background: rgba(12, 12, 12, 0.70); font-family: 'Share Tech Mono', monospace; font-size: {f_base}px;")

        if hasattr(self, 'header'):
            h_op = min(1.0, max(0.40, self.overlay_opacity * 0.95))
            self.header.setStyleSheet(f"""
                background: rgba(20, 20, 20, {h_op:.2f});
                border-bottom: 1px solid rgba(120, 120, 120, 0.15);
            """)

        if hasattr(self, 'footer'):
            f_op = min(1.0, max(0.40, self.overlay_opacity * 0.95))
            self.footer.setStyleSheet(f"""
                background: rgba(10, 10, 10, {f_op:.2f});
                border-top: 1px solid rgba(120, 120, 120, 0.15);
            """)

    BORDER_MARGIN = 6

    def init_window_flags(self):
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.setWindowTitle("EVE Tactical Copilot")
        self.setMinimumSize(360, 180)
        self.resize(self.expanded_width, self.expanded_height)
        
        pos_x = self.config.get("pos_x", 80)
        pos_y = self.config.get("pos_y", 80)
        self.move(pos_x, pos_y)

        # Timer Keep-Above para reforço no compositor Wayland
        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self._keep_above)
        self.top_timer.start(1000)
        self.ensure_game_fullscreen_demoted()

    def _get_resize_edge(self, pos: QPoint):
        x = pos.x()
        y = pos.y()
        w = self.width()
        h = self.height()
        m = self.BORDER_MARGIN

        left = x <= m
        right = x >= w - m
        top = y <= m
        bottom = y >= h - m

        if top and left:
            return Qt.Edge.TopEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeFDiagCursor
        elif top and right:
            return Qt.Edge.TopEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeBDiagCursor
        elif bottom and left:
            return Qt.Edge.BottomEdge | Qt.Edge.LeftEdge, Qt.CursorShape.SizeBDiagCursor
        elif bottom and right:
            return Qt.Edge.BottomEdge | Qt.Edge.RightEdge, Qt.CursorShape.SizeFDiagCursor
        elif left:
            return Qt.Edge.LeftEdge, Qt.CursorShape.SizeHorCursor
        elif right:
            return Qt.Edge.RightEdge, Qt.CursorShape.SizeHorCursor
        elif top:
            return Qt.Edge.TopEdge, Qt.CursorShape.SizeVerCursor
        elif bottom:
            return Qt.Edge.BottomEdge, Qt.CursorShape.SizeVerCursor

        return None, None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and not self.is_locked:
            edge, _ = self._get_resize_edge(event.pos())
            if edge:
                wh = self.windowHandle()
                if wh and hasattr(wh, 'startSystemResize'):
                    wh.startSystemResize(edge)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.is_locked:
            edge, cursor = self._get_resize_edge(event.pos())
            if cursor:
                self.setCursor(cursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def eventFilter(self, obj, event):
        if not self.is_locked and hasattr(event, 'type'):
            et = event.type()
            if et == event.Type.MouseMove and hasattr(event, 'globalPosition'):
                win_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                edge, cursor = self._get_resize_edge(win_pos)
                if cursor:
                    self.setCursor(cursor)
                elif self.cursor().shape() != Qt.CursorShape.ArrowCursor:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
            elif et == event.Type.MouseButtonPress and hasattr(event, 'button') and event.button() == Qt.MouseButton.LeftButton:
                if hasattr(event, 'globalPosition'):
                    win_pos = self.mapFromGlobal(event.globalPosition().toPoint())
                    edge, _ = self._get_resize_edge(win_pos)
                    if edge:
                        wh = self.windowHandle()
                        if wh and hasattr(wh, 'startSystemResize'):
                            wh.startSystemResize(edge)
                            return True
        return super().eventFilter(obj, event)

    def _keep_above(self):
        if self.isVisible() and not self.isMinimized():
            self.raise_()
            self.ensure_game_fullscreen_demoted()

    def ensure_game_fullscreen_demoted(self):
        try:
            subprocess.run(["wmctrl", "-r", "EVE - ", "-b", "remove,fullscreen"], 
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Container Principal com o CSS Monocromático do Usuário
        self.overview_container = QFrame(self)
        self.overview_container.setObjectName("overviewWindow")

        container_layout = QVBoxLayout(self.overview_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # 1. Barra de Título Monocromática com Botão de Trava
        self.header = OverviewHeader(self)
        container_layout.addWidget(self.header)

        # 2. Corpo
        self.body_widget = QWidget()
        body_layout = QVBoxLayout(self.body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # Abas de Navegação (Tabs)
        self.tabs = QTabWidget()
        self.tab_overview = QWidget()
        
        # Módulos Táticos Avançados (Manual do Usuário)
        self.ship_manager = ShipManager()
        self.tab_tactics = TacticalHUDWidget(ship_mgr=self.ship_manager)
        self.tab_ships = ShipManagerWidget(ship_mgr=self.ship_manager)
        self.tab_simulator = TacticalSimulatorWidget()
        self.tab_fw = FWAssistantWidget()
        self.tab_training = TrainingTabWidget()

        # Conectar alteração de fitting ativo com o HUD tático
        self.tab_ships.fit_changed.connect(self.tab_tactics.set_active_fit)
        self.tab_tactics.tactical_guidance_ready.connect(self.handle_tactical_voice_guidance)

        self.tab_copilot = QWidget()
        self.tab_market = QWidget()
        self.tab_loot = QWidget()
        self.tab_hacking = HackingTabWidget(log_dir=self.config.get("log_dir"))
        self.tab_combat = QWidget()
        self.tab_missions = QWidget()
        self.tab_advisor = QWidget()

        self.setup_overview_tab()
        self.setup_copilot_tab()
        self.setup_market_tab()
        self.setup_loot_tab()
        self.setup_combat_tab()
        self.setup_missions_tab()
        self.setup_advisor_tab()

        self.module_widgets = {
            "overview": self.tab_overview,
            "tactics": self.tab_tactics,
            "ships": self.tab_ships,
            "simulator": self.tab_simulator,
            "fw": self.tab_fw,
            "training": self.tab_training,
            "copilot": self.tab_copilot,
            "market": self.tab_market,
            "loot": self.tab_loot,
            "hacking": self.tab_hacking,
            "combat": self.tab_combat,
            "missions": self.tab_missions,
            "advisor": self.tab_advisor
        }

        self.tabs.addTab(self.tab_overview, "General")
        self.tabs.addTab(self.tab_tactics, "Tactics & Combat")
        self.tabs.addTab(self.tab_ships, "Ship Manager")
        self.tabs.addTab(self.tab_simulator, "Simulator")
        self.tabs.addTab(self.tab_fw, "FW & D-Scan")
        self.tabs.addTab(self.tab_training, "Training & AAR")
        self.tabs.addTab(self.tab_copilot, "Copilot")
        self.tabs.addTab(self.tab_market, "Market & Fit")
        self.tabs.addTab(self.tab_loot, "Loot Triage")
        self.tabs.addTab(self.tab_hacking, "Hacking")
        self.tabs.addTab(self.tab_combat, "Combat Log")
        self.tabs.addTab(self.tab_missions, "Missions")
        self.tabs.addTab(self.tab_advisor, "Advisor")
        body_layout.addWidget(self.tabs)

        # Habilita duplo-clique na aba para destacar como janela flutuante
        self.tabs.tabBarDoubleClicked.connect(self._on_tab_double_clicked)
        # Menu de contexto com botão direito na barra de abas
        self.tabs.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.customContextMenuRequested.connect(self._on_tabs_context_menu)

        # 3. Rodapé Monocromático do Usuário
        self.footer = QWidget()
        self.footer.setFixedHeight(22)
        self.footer.setStyleSheet("""
            background: rgba(10, 10, 10, 0.60);
            border-top: 1px solid rgba(120, 120, 120, 0.15);
        """)
        footer_layout = QHBoxLayout(self.footer)
        footer_layout.setContentsMargins(10, 0, 8, 0)
        footer_layout.setSpacing(6)

        self.lbl_footer_left = QLabel("8 objects loaded")
        self.lbl_footer_left.setStyleSheet("font-size: 10px; color: #666666; font-family: 'Inter', sans-serif;")
        
        self.lbl_footer_right = QLabel("Filter: Active Profile • Ctrl+C to Scan")
        self.lbl_footer_right.setStyleSheet("font-size: 10px; color: #666666; font-family: 'Inter', sans-serif;")

        grip = QSizeGrip(self)
        grip.setFixedSize(14, 14)

        footer_layout.addWidget(self.lbl_footer_left)
        footer_layout.addStretch()
        footer_layout.addWidget(self.lbl_footer_right)
        footer_layout.addWidget(grip)

        self.overview_container.setMouseTracking(True)
        self.overview_container.installEventFilter(self)
        self.body_widget.setMouseTracking(True)
        self.body_widget.installEventFilter(self)

        body_layout.addWidget(self.footer)
        container_layout.addWidget(self.body_widget)
        main_layout.addWidget(self.overview_container)

        # Atualiza estado do botão de trava inicial e fontes dinâmicas
        self.update_lock_ui()
        self.update_ui_fonts()

    # ----------------------------------------------------
    # CONTROLE DE TRAVA DA JANELA (LOCK / UNLOCK)
    # ----------------------------------------------------
    def toggle_lock(self):
        self.is_locked = not self.is_locked
        self.update_lock_ui()
        self.save_config()

    def update_lock_ui(self):
        if self.is_locked:
            self.header.btn_lock.setText("🔒")
            self.header.btn_lock.setToolTip("Janela TRAVADA (Clique para destravar e mover)")
            self.header.title_lbl.setText("OVERVIEW [COPILOT - LOCKED]")
            self.header.btn_lock.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #e5e5e5;
                    border: none;
                    font-size: 12px;
                    padding: 0;
                }
            """)
            self.lbl_footer_right.setText("Status: Janela Travada na Posição 🔒")
        else:
            self.header.btn_lock.setText("🔓")
            self.header.btn_lock.setToolTip("Janela DESTRAVADA (Arraste pelo cabeçalho)")
            self.header.title_lbl.setText("OVERVIEW [COPILOT - TACTICAL]")
            self.header.btn_lock.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #666666;
                    border: none;
                    font-size: 12px;
                    padding: 0;
                }
                QPushButton:hover {
                    color: #ffffff;
                }
            """)
            self.lbl_footer_right.setText("Filter: Active Profile • Ctrl+C to Scan")

    # ----------------------------------------------------
    # ABA 1: GENERAL (TABELA DE OVERVIEW DO USUÁRIO)
    # ----------------------------------------------------
    def setup_overview_tab(self):
        layout = QVBoxLayout(self.tab_overview)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Icon", "Distance", "Name", "Type", "Velocity", "Radial Vel"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setStretchLastSection(False)
        header.setHighlightSections(False)
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        self.table.setColumnWidth(0, 36)
        self.table.setColumnWidth(1, 75)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 95)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(5, 90)

        self.table.cellClicked.connect(self.handle_table_click)
        layout.addWidget(self.table)

        btn_bar = QHBoxLayout()
        btn_bar.setContentsMargins(6, 2, 6, 2)
        btn_clear = QPushButton("Limpar Alvos da Tabela")
        btn_clear.setFixedHeight(22)
        btn_clear.clicked.connect(self.clear_overview_table)
        btn_bar.addStretch()
        btn_bar.addWidget(btn_clear)
        layout.addLayout(btn_bar)

        self.populate_overview_rows()

    def clear_overview_table(self):
        self.table.setRowCount(0)
        self.lbl_footer_left.setText("0 objects loaded")

    def populate_overview_rows(self):
        data = [
            ("hostile", "▲", "14 km", "Caldari Navy Griffin", "Fragata (ECM Jammer)", "1,450 m/s", "-60 m/s"),
            ("hostile", "▲", "22 km", "Caldari Navy Scout", "Fragata (Scout)", "1,850 m/s", "80 m/s"),
            ("hostile", "▲", "28 km", "Caldari Navy Soldier", "Fragata (Missiles)", "1,200 m/s", "10 m/s"),
        ]

        self.table.setRowCount(len(data))
        for row, item in enumerate(data):
            tag_type, symbol, dist, name, stype, vel, rvel = item
            
            icon_item = QTableWidgetItem(f" {symbol}")
            if tag_type == "hostile":
                icon_item.setForeground(QColor("#f03e3e"))
            elif tag_type == "fleet":
                icon_item.setForeground(QColor("#a04ef6"))
            elif tag_type == "neutral":
                icon_item.setForeground(QColor("#aaaaaa"))
            elif tag_type == "friendly":
                icon_item.setForeground(QColor("#1c7ed6"))
            elif tag_type == "wreck":
                icon_item.setForeground(QColor("#555555"))

            d_item = QTableWidgetItem(dist)
            d_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            n_item = QTableWidgetItem(name)
            t_item = QTableWidgetItem(stype)

            v_item = QTableWidgetItem(vel)
            v_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            rv_item = QTableWidgetItem(rvel)
            rv_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            self.table.setItem(row, 0, icon_item)
            self.table.setItem(row, 1, d_item)
            self.table.setItem(row, 2, n_item)
            self.table.setItem(row, 3, t_item)
            self.table.setItem(row, 4, v_item)
            self.table.setItem(row, 5, rv_item)
            self.table.setRowHeight(row, self.get_table_row_height())

    def handle_table_click(self, row, col):
        name_item = self.table.item(row, 2)
        if name_item:
            target_name = name_item.text()
            faction_data, ship_size = analyze_target_text(target_name)
            self.update_target_intel(target_name, faction_data, ship_size)
            self.navigate_to_module("copilot")

    # ----------------------------------------------------
    # ABA 2: COPILOT (ANÁLISE E DIRETRIZES DO ALVO)
    # ----------------------------------------------------
    def setup_copilot_tab(self):
        layout = QVBoxLayout(self.tab_copilot)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Cartão de Detalhe do Alvo Monocromático
        card = QFrame()
        card.setStyleSheet("""
            background: rgba(15, 15, 15, 0.40);
            border: 1px solid rgba(120, 120, 120, 0.15);
            padding: 8px;
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(5)

        h_row = QHBoxLayout()
        self.lbl_target_tag = QLabel("▲")
        self.lbl_target_tag.setStyleSheet("color: #f03e3e; font-size: 13px; font-weight: bold;")
        self.lbl_target_title = QLabel("GARMUR [PIRATE FRIGATE]")
        self.lbl_target_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #ffffff; font-family: 'Share Tech Mono', monospace;")
        h_row.addWidget(self.lbl_target_tag)
        h_row.addWidget(self.lbl_target_title)
        h_row.addStretch()
        c_layout.addLayout(h_row)

        self.lbl_target_subinfo = QLabel("Faction: Guristas Pirates • Class: Frigate • Threat: Extreme (Point/Scram 30km+)")
        self.lbl_target_subinfo.setStyleSheet("font-size: 10px; color: #888888;")
        c_layout.addWidget(self.lbl_target_subinfo)

        layout.addWidget(card)

        # Detalhes Táticos em Cards Finos
        t_card = QFrame()
        t_card.setStyleSheet("background: rgba(15, 15, 15, 0.30); border: 1px solid rgba(120, 120, 120, 0.10); padding: 8px;")
        t_layout = QVBoxLayout(t_card)
        t_layout.setSpacing(4)

        lbl_sec1 = QLabel("TACTICAL RECOMMENDATION // WEAKNESS & AMMO")
        lbl_sec1.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        t_layout.addWidget(lbl_sec1)

        self.lbl_ammo_advice = QLabel("Munição: Caldari Navy Scourge / Kinetic • Fraqueza: Kinetic (Secundária: Thermal)")
        self.lbl_ammo_advice.setStyleSheet("font-size: 11px; color: #dddddd; font-family: 'Inter', sans-serif;")
        self.lbl_ammo_advice.setWordWrap(True)
        t_layout.addWidget(self.lbl_ammo_advice)

        self.lbl_drone_advice = QLabel("Drones: Drones Caldari (Hornet / Vespa) - Dano Kinetic de alta velocidade.")
        self.lbl_drone_advice.setStyleSheet("font-size: 11px; color: #bbbbbb; font-family: 'Inter', sans-serif;")
        self.lbl_drone_advice.setWordWrap(True)
        t_layout.addWidget(self.lbl_drone_advice)

        layout.addWidget(t_card)

        # Vetor de Voo & Oficial Tático
        f_card = QFrame()
        f_card.setStyleSheet("background: rgba(15, 15, 15, 0.35); border: 1px solid rgba(0, 229, 255, 0.20); padding: 8px;")
        f_layout = QVBoxLayout(f_card)
        f_layout.setSpacing(4)

        f_header = QHBoxLayout()
        lbl_sec2 = QLabel("FLIGHT VECTOR & TACTICAL ADVISOR")
        lbl_sec2.setStyleSheet("font-size: 10px; color: #00e5ff; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        f_header.addWidget(lbl_sec2)
        f_header.addStretch()
        f_layout.addLayout(f_header)

        # Linha de telemetria balística da arma inimiga detectada
        w_row = QHBoxLayout()
        w_row.setSpacing(8)
        self.lbl_detected_weapon = QLabel("Arma Detectada: [Aguardando impacto...]")
        self.lbl_detected_weapon.setStyleSheet("font-size: 10px; color: #ffd43b; font-family: 'Share Tech Mono', monospace;")
        self.lbl_flight_maneuver = QLabel("Manobra: Transversal Padrão")
        self.lbl_flight_maneuver.setStyleSheet("font-size: 10px; color: #40c057; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        w_row.addWidget(self.lbl_detected_weapon)
        w_row.addStretch()
        w_row.addWidget(self.lbl_flight_maneuver)
        f_layout.addLayout(w_row)

        self.lbl_flight_advice = QLabel("Mantenha Afterburner ativo e órbite transversalmente para quebrar o rastreamento angular das baterias inimigas.")
        self.lbl_flight_advice.setStyleSheet("font-size: 11px; color: #ffffff; font-family: 'Inter', sans-serif; line-height: 140%;")
        self.lbl_flight_advice.setWordWrap(True)
        f_layout.addWidget(self.lbl_flight_advice)

        layout.addWidget(f_card)

        # Alerta E-War
        self.ewar_card = QFrame()
        self.ewar_card.setStyleSheet("background: rgba(40, 15, 15, 0.35); border: 1px solid rgba(240, 62, 62, 0.30); padding: 8px;")
        e_layout = QVBoxLayout(self.ewar_card)
        e_layout.setSpacing(3)

        lbl_sec3 = QLabel("ELECTRONIC WARFARE ALERT")
        lbl_sec3.setStyleSheet("font-size: 10px; color: #f03e3e; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        e_layout.addWidget(lbl_sec3)

        self.lbl_ewar_advice = QLabel("PERIGO: Warp Disruptor de longo alcance (Garmur alcança até 40km de point).")
        self.lbl_ewar_advice.setStyleSheet("font-size: 10px; color: #ff8787;")
        self.lbl_ewar_advice.setWordWrap(True)
        e_layout.addWidget(self.lbl_ewar_advice)

        layout.addWidget(self.ewar_card)
        layout.addStretch()

    # ----------------------------------------------------
    # ABA 3: MARKET & FIT (COTADOR MULTI-HUB DE FITTINGS)
    # ----------------------------------------------------
    def setup_market_tab(self):
        layout = QVBoxLayout(self.tab_market)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Barra de Localização e Raio de Saltos
        loc_bar = QHBoxLayout()
        loc_bar.setSpacing(6)

        lbl_loc = QLabel("📍 Origem:")
        lbl_loc.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        loc_bar.addWidget(lbl_loc)

        # Detecta sistema inicial dos logs
        init_sys = detect_system_from_logs(self.config.get("log_dir", ""))
        self.txt_origin_system = QLineEdit(init_sys)
        self.txt_origin_system.setPlaceholderText("Ex: Ommare, Arnon, Jita...")
        self.txt_origin_system.setFixedWidth(95)
        self.txt_origin_system.setStyleSheet("padding: 2px 4px; font-size: 11px;")
        loc_bar.addWidget(self.txt_origin_system)

        btn_detect = QPushButton("🎯 Auto")
        btn_detect.setFixedHeight(22)
        btn_detect.setToolTip("Detecta o sistema atual a partir dos logs de navegação do jogo")
        btn_detect.clicked.connect(self.handle_detect_system)
        loc_bar.addWidget(btn_detect)

        lbl_sec = QLabel("🛡️ Segurança:")
        lbl_sec.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace; margin-left: 6px;")
        loc_bar.addWidget(lbl_sec)

        self.cmb_security = QComboBox()
        self.cmb_security.addItem("High-Sec (≥ 0.5)", "high")
        self.cmb_security.addItem("High-Sec Seguro (≥ 0.7)", "safe_high")
        self.cmb_security.addItem("Low-Sec Permitido (≥ 0.1)", "low")
        self.cmb_security.addItem("Qualquer (Null/Low/High)", "all")
        self.cmb_security.setFixedHeight(22)
        self.cmb_security.setStyleSheet("""
            QComboBox {
                background: rgba(12, 12, 12, 0.85);
                color: #eaeaea;
                border: 1px solid rgba(120, 120, 120, 0.20);
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                padding: 1px 4px;
            }
            QComboBox QAbstractItemView {
                background: #141414;
                color: #cccccc;
                selection-background-color: #2b3b4c;
                border: 1px solid #333333;
            }
        """)
        saved_sec = self.config.get("market_security_filter", "high")
        idx = self.cmb_security.findData(saved_sec)
        if idx >= 0:
            self.cmb_security.setCurrentIndex(idx)
        self.cmb_security.currentIndexChanged.connect(self.handle_security_filter_changed)
        loc_bar.addWidget(self.cmb_security)

        lbl_sort = QLabel("🎯 Critério:")
        lbl_sort.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace; margin-left: 6px;")
        loc_bar.addWidget(lbl_sort)

        self.cmb_sort_mode = QComboBox()
        self.cmb_sort_mode.addItem("💰 Menor Preço", "cheapest")
        self.cmb_sort_mode.addItem("⚡ Mais Próximo", "nearest")
        self.cmb_sort_mode.addItem("⚖️ Custo-Benefício", "balanced")
        self.cmb_sort_mode.setFixedHeight(22)
        self.cmb_sort_mode.setStyleSheet(self.cmb_security.styleSheet())
        saved_sort = self.config.get("market_sort_mode", "cheapest")
        idx_sort = self.cmb_sort_mode.findData(saved_sort)
        if idx_sort >= 0:
            self.cmb_sort_mode.setCurrentIndex(idx_sort)
        self.cmb_sort_mode.currentIndexChanged.connect(self.handle_market_filter_changed)
        loc_bar.addWidget(self.cmb_sort_mode)

        lbl_max_j = QLabel("🧭 Raio:")
        lbl_max_j.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace; margin-left: 6px;")
        loc_bar.addWidget(lbl_max_j)

        self.cmb_max_jumps = QComboBox()
        self.cmb_max_jumps.addItem("Qualquer Raio", 999)
        self.cmb_max_jumps.addItem("0 Saltos (Local)", 0)
        self.cmb_max_jumps.addItem("Até 1 Salto", 1)
        self.cmb_max_jumps.addItem("Até 2 Saltos", 2)
        self.cmb_max_jumps.addItem("Até 3 Saltos", 3)
        self.cmb_max_jumps.addItem("Até 5 Saltos", 5)
        self.cmb_max_jumps.addItem("Até 10 Saltos", 10)
        self.cmb_max_jumps.setFixedHeight(22)
        self.cmb_max_jumps.setStyleSheet(self.cmb_security.styleSheet())
        saved_j = self.config.get("market_max_jumps", 999)
        idx_j = self.cmb_max_jumps.findData(saved_j)
        if idx_j >= 0:
            self.cmb_max_jumps.setCurrentIndex(idx_j)
        self.cmb_max_jumps.currentIndexChanged.connect(self.handle_market_filter_changed)
        loc_bar.addWidget(self.cmb_max_jumps)

        loc_bar.addStretch()
        layout.addLayout(loc_bar)

        # 2. Barra de Ações e Fit
        action_bar = QHBoxLayout()
        action_bar.setSpacing(6)

        lbl_fit = QLabel("FIT DA NAVE (EFT):")
        lbl_fit.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        action_bar.addWidget(lbl_fit)
        action_bar.addStretch()

        btn_paste_fit = QPushButton("📋 Colar do Clipboard")
        btn_paste_fit.setFixedHeight(22)
        btn_paste_fit.clicked.connect(self.handle_paste_and_quote_fit)

        btn_quote = QPushButton("🛒 Buscar Menor Preço e Jumps")
        btn_quote.setFixedHeight(22)
        btn_quote.setStyleSheet("""
            QPushButton {
                background: rgba(40, 55, 75, 0.90);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.30);
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(55, 75, 105, 0.95);
            }
        """)
        btn_quote.clicked.connect(self.handle_quote_current_fit)

        action_bar.addWidget(btn_paste_fit)
        action_bar.addWidget(btn_quote)
        layout.addLayout(action_bar)

        # Área de texto para o fit
        self.txt_fit_input = QTextEdit()
        self.txt_fit_input.setPlaceholderText("Cole aqui o texto EFT da sua nave (ex: [Vexor, Meu Fit]...)")
        self.txt_fit_input.setMaximumHeight(65)
        layout.addWidget(self.txt_fit_input)

        # 3. Card de Resumo de Cotação
        self.market_summary_card = QFrame()
        self.market_summary_card.setStyleSheet("""
            background: rgba(15, 15, 15, 0.45);
            border: 1px solid rgba(120, 120, 120, 0.15);
            padding: 6px;
        """)
        m_layout = QVBoxLayout(self.market_summary_card)
        m_layout.setSpacing(4)

        self.lbl_market_fit_name = QLabel("NENHUM FIT COTADO")
        self.lbl_market_fit_name.setStyleSheet("font-size: 11px; font-weight: bold; color: #ffffff; font-family: 'Share Tech Mono', monospace;")
        m_layout.addWidget(self.lbl_market_fit_name)

        stats_row = QHBoxLayout()
        self.lbl_price_radius = QLabel("Total Estimado: —")
        self.lbl_price_radius.setStyleSheet("font-size: 10.5px; color: #40c057; font-weight: bold; font-family: 'Share Tech Mono', monospace;")

        self.lbl_items_found = QLabel("Disponibilidade: —")
        self.lbl_items_found.setStyleSheet("font-size: 10.5px; color: #ffd43b; font-family: 'Share Tech Mono', monospace;")

        stats_row.addWidget(self.lbl_price_radius)
        stats_row.addWidget(self.lbl_items_found)
        stats_row.addStretch()
        m_layout.addLayout(stats_row)

        self.lbl_market_rec = QLabel("Digite onde você está (ou use Auto) e clique em 'Buscar Menor Preço e Jumps'.")
        self.lbl_market_rec.setStyleSheet("font-size: 10px; color: #888888;")
        self.lbl_market_rec.setWordWrap(True)
        m_layout.addWidget(self.lbl_market_rec)

        layout.addWidget(self.market_summary_card)

        # 4. Tabela de Itens Cotados no Raio
        self.market_table = QTableWidget()
        self.market_table.setColumnCount(6)
        self.market_table.setHorizontalHeaderLabels(["Qtd", "Módulo / Item", "Distância", "Estação / Sistema", "Preço Unit.", "Total (ISK)"])
        self.market_table.verticalHeader().setVisible(False)
        self.market_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.market_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.market_table.setShowGrid(False)

        m_header = self.market_table.horizontalHeader()
        m_header.setSectionsMovable(True)
        for i in range(6):
            m_header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        
        self.market_table.setColumnWidth(0, 42)
        self.market_table.setColumnWidth(1, 210)
        self.market_table.setColumnWidth(2, 95)
        self.market_table.setColumnWidth(3, 175)
        self.market_table.setColumnWidth(4, 95)
        self.market_table.setColumnWidth(5, 95)

        layout.addWidget(self.market_table)

        # 5. Barra inferior de ações
        bot_bar = QHBoxLayout()
        btn_copy_multibuy = QPushButton("📋 Copiar Lista p/ Multibuy do EVE")
        btn_copy_multibuy.setFixedHeight(22)
        btn_copy_multibuy.clicked.connect(self.handle_copy_multibuy)
        bot_bar.addStretch()
        bot_bar.addWidget(btn_copy_multibuy)
        layout.addLayout(bot_bar)

    def handle_detect_system(self):
        detected = detect_system_from_logs(self.config.get("log_dir", ""))
        self.txt_origin_system.setText(detected)
        self.lbl_market_rec.setText(f"📍 Sistema detectado com sucesso dos logs: <b>{detected}</b>")

    def handle_paste_and_quote_fit(self):
        cb = QApplication.clipboard()
        if cb:
            txt = cb.text().strip()
            if txt:
                self.txt_fit_input.setPlainText(txt)
                self.handle_quote_current_fit()

    def handle_security_filter_changed(self):
        sec_val = self.cmb_security.currentData()
        self.config["market_security_filter"] = sec_val
        self.save_config()
        if self.txt_fit_input.toPlainText().strip():
            self.handle_quote_current_fit()

    def handle_market_filter_changed(self):
        if hasattr(self, "cmb_sort_mode"):
            self.config["market_sort_mode"] = self.cmb_sort_mode.currentData()
        if hasattr(self, "cmb_max_jumps"):
            self.config["market_max_jumps"] = self.cmb_max_jumps.currentData()
        self.save_config()
        if self.txt_fit_input.toPlainText().strip():
            self.handle_quote_current_fit()

    def handle_market_error(self, err_msg):
        self.lbl_market_fit_name.setText("ERRO NA CONSULTA")
        self.lbl_market_rec.setText(f"❌ Erro ao consultar o mercado: {err_msg}")
        self.lbl_price_radius.setText("Total: —")
        self.lbl_items_found.setText("Disponibilidade: —")

    def handle_quote_current_fit(self):
        text = self.txt_fit_input.toPlainText().strip()
        if not text:
            return
        origin = self.txt_origin_system.text().strip() or "Villore"
        sec_filter = self.cmb_security.currentData() or "high"
        sec_label = self.cmb_security.currentText()
        sort_mode = self.cmb_sort_mode.currentData() if hasattr(self, "cmb_sort_mode") else "cheapest"
        max_jumps = self.cmb_max_jumps.currentData() if hasattr(self, "cmb_max_jumps") else 999

        sort_label = self.cmb_sort_mode.currentText() if hasattr(self, "cmb_sort_mode") else "Menor Preço"
        self.lbl_market_rec.setText(f"⏳ Buscando ({sort_label}) a partir de {origin} ({sec_label})...")
        self.lbl_market_fit_name.setText("PESQUISANDO ORDENS...")
        self.lbl_price_radius.setText("Total: Calculando...")
        self.lbl_items_found.setText("Disponibilidade: Consultando...")
        QApplication.processEvents()

        def worker():
            try:
                res = quote_fitting_near(
                    text,
                    origin_system_name=origin,
                    min_security=sec_filter,
                    sort_mode=sort_mode,
                    max_jumps=max_jumps
                )
                self.market_bridge.quote_ready.emit(res)
            except Exception as e:
                self.market_bridge.quote_error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def display_market_quote(self, res):
        if not res or not res.get("items"):
            self.lbl_market_fit_name.setText("FALHA NA COTAÇÃO DO FIT")
            self.lbl_market_rec.setText("Não foi possível resolver os itens deste fit. Verifique o formato EFT.")
            return

        ship = res.get("ship_name", "Nave")
        fit = res.get("fit_name", "Fit")
        origin = res.get("origin_system", "Origem")
        filter_label = res.get("filter_label", "High-Sec")
        total_in_radius = res.get("total_in_radius", 0.0)
        found = res.get("items_in_radius_count", 0)
        total_items = res.get("total_items_count", 0)

        self.lbl_market_fit_name.setText(f"{ship.upper()} [{fit.upper()}] - {total_items} ITENS")
        self.lbl_price_radius.setText(f"Total Estimado: {total_in_radius:,.0f} ISK")
        self.lbl_items_found.setText(f"Disponibilidade: {found}/{total_items} peças cotadas")
        self.lbl_market_rec.setText(res.get("recommendation", ""))

        items = res.get("items", [])
        self.market_table.setRowCount(len(items))
        for row, it in enumerate(items):
            q_item = QTableWidgetItem(f"{it['qty']}x")
            q_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            raw_name = it.get("raw_name", it["name"])
            n_item = QTableWidgetItem(it["name"])
            n_item.setData(Qt.ItemDataRole.UserRole, raw_name)

            badge = it.get("badge", "")
            if "Menor Preço" in badge:
                n_item.setForeground(QColor("#51cf66"))
            elif "Mesmo Sistema" in badge:
                n_item.setForeground(QColor("#00e5ff"))

            stock = it.get("stock_avail", 0)
            if stock > 0:
                n_item.setToolTip(f"{raw_name}\n📦 Estoque no mercado: {stock:,.0f} un.")
                q_item.setToolTip(f"Quantidade: {it['qty']}x\n📦 Estoque nesta estação: {stock:,.0f} un.")

            j_val = it.get("jumps", -1)
            sec_info = it.get("sec_details", {})
            sec_lbl = sec_info.get("label", "0.0")
            sec_tier = sec_info.get("tier", "")
            sec_color = sec_info.get("color", "#888888")

            if it.get("in_radius"):
                dist_str = f"✅ {j_val}j [{sec_lbl} {sec_tier}]" if j_val > 0 else f"✅ 0j [{sec_lbl} {sec_tier}]"
                d_item = QTableWidgetItem(dist_str)
                d_item.setForeground(QColor("#40c057"))
            elif j_val >= 0:
                dist_str = f"⚠️ {j_val}j [{sec_lbl} {sec_tier}]"
                d_item = QTableWidgetItem(dist_str)
                d_item.setForeground(QColor(sec_color))
            else:
                d_item = QTableWidgetItem("❌ Sem estoque")
                d_item.setForeground(QColor("#f03e3e"))

            s_name = it.get("station_name", "—")
            sys_name = it.get("system_name", "")
            loc_str = f"{s_name}" if not sys_name or sys_name in s_name else f"{s_name} [{sys_name}]"
            loc_item = QTableWidgetItem(loc_str)
            loc_item.setToolTip(f"{loc_str}\nNível de Segurança: {sec_lbl} ({sec_tier}-Sec)\n📦 Estoque disponível: {stock:,.0f} un.")

            p_item = QTableWidgetItem(f"{it['price']:,.0f} ISK")
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if "Menor Preço" in badge:
                p_item.setForeground(QColor("#51cf66"))

            t_item = QTableWidgetItem(f"{it['total']:,.0f} ISK")
            t_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            t_item.setForeground(QColor("#ffffff"))

            self.market_table.setItem(row, 0, q_item)
            self.market_table.setItem(row, 1, n_item)
            self.market_table.setItem(row, 2, d_item)
            self.market_table.setItem(row, 3, loc_item)
            self.market_table.setItem(row, 4, p_item)
            self.market_table.setItem(row, 5, t_item)
            self.market_table.setRowHeight(row, self.get_table_row_height())

    def handle_copy_multibuy(self):
        lines = []
        for r in range(self.market_table.rowCount()):
            qty_text = self.market_table.item(r, 0).text().replace("x", "").strip()
            item_obj = self.market_table.item(r, 1)
            raw_name = item_obj.data(Qt.ItemDataRole.UserRole)
            if not raw_name:
                raw_name = item_obj.text().strip()
            lines.append(f"{raw_name} {qty_text}")
        if lines:
            cb = QApplication.clipboard()
            if cb:
                cb.setText("\n".join(lines))
                self.lbl_market_rec.setText("✅ Lista copiada! Abra o 'Multibuy' no EVE e dê Ctrl+V para comprar tudo de uma vez!")

    # ----------------------------------------------------
    # ABA: TRIAGEM DE CARGA & AVALIADOR DE LOOT (EVE COPILOT)
    # ----------------------------------------------------
    def setup_loot_tab(self):
        layout = QVBoxLayout(self.tab_loot)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Card Superior com Resumo Executivo e KPIs
        self.loot_summary_card = QFrame()
        self.loot_summary_card.setStyleSheet("""
            background: rgba(14, 16, 20, 0.65);
            border: 1px solid rgba(120, 120, 120, 0.20);
            padding: 8px;
        """)
        s_layout = QVBoxLayout(self.loot_summary_card)
        s_layout.setContentsMargins(6, 6, 6, 6)
        s_layout.setSpacing(6)

        # Título e Total ISK
        top_row = QHBoxLayout()
        self.lbl_loot_title = QLabel("📦 TRIAGEM DE CARGA & AVALIADOR DE LOOT")
        self.lbl_loot_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #00e5ff; font-family: 'Share Tech Mono', monospace;")

        self.lbl_loot_total_isk = QLabel("💰 Total Estimado: 0 ISK")
        self.lbl_loot_total_isk.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffd43b; font-family: 'Share Tech Mono', monospace;")

        top_row.addWidget(self.lbl_loot_title)
        top_row.addStretch()
        top_row.addWidget(self.lbl_loot_total_isk)
        s_layout.addLayout(top_row)

        # Linha de Métricas Rápidas (Badges)
        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)

        self.lbl_kpi_volume = QLabel("📦 Vol: 0.00 m³")
        self.lbl_kpi_volume.setStyleSheet("font-size: 10px; color: #888888; font-family: 'Share Tech Mono', monospace;")

        self.lbl_kpi_use = QLabel("🟢 Usar: 0")
        self.lbl_kpi_use.setStyleSheet("font-size: 11px; font-weight: bold; color: #00e5ff; font-family: 'Share Tech Mono', monospace;")

        self.lbl_kpi_sell = QLabel("💰 Vender: 0")
        self.lbl_kpi_sell.setStyleSheet("font-size: 11px; font-weight: bold; color: #ffd43b; font-family: 'Share Tech Mono', monospace;")

        self.lbl_kpi_hoard = QLabel("📦 Guardar: 0")
        self.lbl_kpi_hoard.setStyleSheet("font-size: 11px; font-weight: bold; color: #74c0fc; font-family: 'Share Tech Mono', monospace;")

        self.lbl_kpi_trash = QLabel("⚪ Reprocessar: 0")
        self.lbl_kpi_trash.setStyleSheet("font-size: 11px; font-weight: bold; color: #868e96; font-family: 'Share Tech Mono', monospace;")

        metrics_row.addWidget(self.lbl_kpi_volume)
        metrics_row.addSpacing(10)
        metrics_row.addWidget(self.lbl_kpi_use)
        metrics_row.addWidget(self.lbl_kpi_sell)
        metrics_row.addWidget(self.lbl_kpi_hoard)
        metrics_row.addWidget(self.lbl_kpi_trash)
        metrics_row.addStretch()
        s_layout.addLayout(metrics_row)

        # Frase explicativa / status
        self.lbl_loot_status = QLabel("📋 Selecione itens no Cargo, Hangar ou Destroço no EVE e aperte Ctrl+C, ou clique em 'Escanear Clipboard'.")
        self.lbl_loot_status.setStyleSheet("font-size: 10px; color: #888888; font-family: 'Inter', sans-serif;")
        s_layout.addWidget(self.lbl_loot_status)

        layout.addWidget(self.loot_summary_card)

        # 2. Barra de Filtros e Ações Rápidas
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(6)

        self.btn_filter_all = QPushButton("Todos (0)")
        self.btn_filter_use = QPushButton("🟢 Usar (0)")
        self.btn_filter_sell = QPushButton("💰 Vender (0)")
        self.btn_filter_hoard = QPushButton("📦 Guardar (0)")
        self.btn_filter_trash = QPushButton("⚪ Reprocessar (0)")

        for btn in [self.btn_filter_all, self.btn_filter_use, self.btn_filter_sell, self.btn_filter_hoard, self.btn_filter_trash]:
            btn.setFixedHeight(22)
            btn.setStyleSheet("""
                QPushButton {
                    background: rgba(35, 35, 35, 0.60);
                    color: #aaaaaa;
                    border: 1px solid rgba(120, 120, 120, 0.25);
                    font-family: 'Share Tech Mono', monospace;
                    font-size: 10px;
                    padding: 1px 6px;
                }
                QPushButton:hover {
                    background: rgba(60, 60, 60, 0.85);
                    color: #ffffff;
                    border: 1px solid rgba(255, 255, 255, 0.40);
                }
            """)

        self.btn_filter_all.clicked.connect(lambda: self.filter_loot_table("ALL"))
        self.btn_filter_use.clicked.connect(lambda: self.filter_loot_table("USE_SHIP"))
        self.btn_filter_sell.clicked.connect(lambda: self.filter_loot_table("SELL_JITA"))
        self.btn_filter_hoard.clicked.connect(lambda: self.filter_loot_table("HOARD_HANGAR"))
        self.btn_filter_trash.clicked.connect(lambda: self.filter_loot_table("REPROCESS_TRASH"))

        actions_bar.addWidget(self.btn_filter_all)
        actions_bar.addWidget(self.btn_filter_use)
        actions_bar.addWidget(self.btn_filter_sell)
        actions_bar.addWidget(self.btn_filter_hoard)
        actions_bar.addWidget(self.btn_filter_trash)
        actions_bar.addStretch()

        # Botão Escanear / Colar
        btn_paste_loot = QPushButton("📋 Escanear Clipboard")
        btn_paste_loot.setFixedHeight(22)
        btn_paste_loot.setToolTip("Analisa o inventário copiado atualmente na área de transferência (Ctrl+C no jogo)")
        btn_paste_loot.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.15);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.40);
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.30);
                color: #ffffff;
            }
        """)
        btn_paste_loot.clicked.connect(self.handle_paste_and_evaluate_loot)

        # Botão Voz
        btn_speak_loot = QPushButton("🎙️ Ouvir")
        btn_speak_loot.setFixedHeight(22)
        btn_speak_loot.setToolTip("Aura / Jarvis fala em áudio o diagnóstico do loot")
        btn_speak_loot.setStyleSheet("""
            QPushButton {
                background: rgba(255, 212, 59, 0.15);
                color: #ffd43b;
                border: 1px solid rgba(255, 212, 59, 0.40);
                font-family: 'Share Tech Mono', monospace;
                font-size: 10px;
                font-weight: bold;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background: rgba(255, 212, 59, 0.30);
                color: #ffffff;
            }
        """)
        btn_speak_loot.clicked.connect(self.handle_speak_loot_summary)

        # Botão Limpar
        btn_clear_loot = QPushButton("🗑️")
        btn_clear_loot.setFixedSize(22, 22)
        btn_clear_loot.setToolTip("Limpar análise atual")
        btn_clear_loot.clicked.connect(self.clear_loot_table)

        actions_bar.addWidget(btn_paste_loot)
        actions_bar.addWidget(btn_speak_loot)
        actions_bar.addWidget(btn_clear_loot)
        layout.addLayout(actions_bar)

        # 3. Tabela de Triagem de Loot
        self.loot_table = QTableWidget()
        self.loot_table.setColumnCount(6)
        self.loot_table.setHorizontalHeaderLabels([
            "Recomendação", "Qtd", "Item / Módulo", "Preço Est.", "Total (ISK)", "Justificativa Tática"
        ])
        self.loot_table.verticalHeader().setVisible(False)
        self.loot_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.loot_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.loot_table.setShowGrid(False)

        l_header = self.loot_table.horizontalHeader()
        l_header.setSectionsMovable(True)
        for i in range(6):
            l_header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

        self.loot_table.setColumnWidth(0, 160)  # Recomendação
        self.loot_table.setColumnWidth(1, 48)   # Qtd
        self.loot_table.setColumnWidth(2, 175)  # Nome
        self.loot_table.setColumnWidth(3, 85)   # Preço Unit
        self.loot_table.setColumnWidth(4, 95)   # Total ISK
        self.loot_table.setColumnWidth(5, 230)  # Justificativa

        layout.addWidget(self.loot_table)

    def handle_paste_and_evaluate_loot(self):
        cb = QApplication.clipboard()
        if cb:
            txt = cb.text().strip()
            if txt:
                self.process_loot_text(txt)

    def process_loot_text(self, text: str):
        if not text:
            return
        self.lbl_loot_status.setText("⏳ Analisando itens e consultando base de mercado da ESI...")
        QApplication.processEvents()

        def worker():
            try:
                report = self.loot_evaluator.evaluate_text(text)
                self.loot_bridge.loot_ready.emit(report)
            except Exception as e:
                self.loot_bridge.loot_error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()

    def handle_loot_error(self, err_msg: str):
        self.lbl_loot_status.setText(f"❌ Erro na avaliação de loot: {err_msg}")

    def display_loot_report(self, report):
        self.current_loot_report = report
        self.current_loot_filter = "ALL"

        if not report or not report.items:
            self.lbl_loot_status.setText("Nenhum item válido identificado no texto copiado.")
            self.lbl_loot_total_isk.setText("💰 Total: 0 ISK")
            self.lbl_kpi_volume.setText("📦 Vol: 0.00 m³")
            self.loot_table.setRowCount(0)
            return

        # Atualiza KPIs
        total_m = report.total_isk / 1000000
        if total_m >= 1000:
            val_str = f"{total_m/1000:.2f}B ISK"
        elif total_m >= 1:
            val_str = f"{total_m:.1f}M ISK"
        else:
            val_str = f"{report.total_isk:,.0f} ISK"

        self.lbl_loot_total_isk.setText(f"💰 Total Estimado: {val_str}")
        self.lbl_kpi_volume.setText(f"📦 Vol: {report.total_volume_m3:,.2f} m³")
        self.lbl_kpi_use.setText(f"🟢 Usar: {report.use_count}")
        self.lbl_kpi_sell.setText(f"💰 Vender: {report.sell_count}")
        self.lbl_kpi_hoard.setText(f"📦 Guardar: {report.hoard_count}")
        self.lbl_kpi_trash.setText(f"⚪ Reprocessar: {report.reprocess_count}")

        # Atualiza botões de filtro
        self.btn_filter_all.setText(f"Todos ({len(report.items)})")
        self.btn_filter_use.setText(f"🟢 Usar ({report.use_count})")
        self.btn_filter_sell.setText(f"💰 Vender ({report.sell_count})")
        self.btn_filter_hoard.setText(f"📦 Guardar ({report.hoard_count})")
        self.btn_filter_trash.setText(f"⚪ Reprocessar ({report.reprocess_count})")

        self.lbl_loot_status.setText(f"✅ {len(report.items)} tipos de itens triados com sucesso. Filtragem ativa: Todos.")

        # Renderiza tabela completa
        self.render_loot_rows(report.items)

        # Fala por voz se configurado
        if self.config.get("sound_alerts", True) and report.summary_speech:
            self.sound_manager.speak(report.summary_speech, cooldown=5.0)

    def filter_loot_table(self, action_filter):
        self.current_loot_filter = action_filter
        if not self.current_loot_report:
            return

        items = self.current_loot_report.items
        if action_filter != "ALL":
            filtered = [it for it in items if it.action == action_filter]
        else:
            filtered = items

        self.render_loot_rows(filtered)
        labels_map = {
            "ALL": "Todos",
            "USE_SHIP": "🟢 Usar na Nave",
            "SELL_JITA": "💰 Vender (Jita/Hub)",
            "HOARD_HANGAR": "📦 Guardar no Hangar",
            "REPROCESS_TRASH": "⚪ Reprocessar / Descartar"
        }
        self.lbl_loot_status.setText(f"Exibindo {len(filtered)} itens ({labels_map.get(action_filter, action_filter)}).")

    def render_loot_rows(self, items):
        self.loot_table.setRowCount(len(items))
        for row, it in enumerate(items):
            # 0. Ação recomendada (Badge)
            act_item = QTableWidgetItem(it.action_label)
            act_item.setForeground(QColor(it.badge_color))
            font = act_item.font()
            font.setBold(True)
            act_item.setFont(font)

            # 1. Quantidade
            q_item = QTableWidgetItem(f"{it.quantity:,}x")
            q_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # 2. Nome
            n_item = QTableWidgetItem(it.name)
            if it.is_valuable:
                n_item.setForeground(QColor("#ffd43b"))

            # 3. Preço Unitário
            p_unit = QTableWidgetItem(f"{it.unit_price:,.0f} ISK" if it.unit_price > 0 else "—")
            p_unit.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            # 4. Total ISK
            p_tot = QTableWidgetItem(f"{it.total_price:,.0f} ISK" if it.total_price > 0 else "—")
            p_tot.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            p_tot.setForeground(QColor("#ffffff"))

            # 5. Justificativa
            r_item = QTableWidgetItem(it.reason)
            r_item.setToolTip(f"{it.name} ({it.group})\n{it.reason}")

            self.loot_table.setItem(row, 0, act_item)
            self.loot_table.setItem(row, 1, q_item)
            self.loot_table.setItem(row, 2, n_item)
            self.loot_table.setItem(row, 3, p_unit)
            self.loot_table.setItem(row, 4, p_tot)
            self.loot_table.setItem(row, 5, r_item)
            self.loot_table.setRowHeight(row, self.get_table_row_height())

    def handle_speak_loot_summary(self):
        if self.current_loot_report and self.current_loot_report.summary_speech:
            self.sound_manager.speak(self.current_loot_report.summary_speech, cooldown=0.0)

    def clear_loot_table(self):
        self.current_loot_report = None
        self.loot_table.setRowCount(0)
        self.lbl_loot_total_isk.setText("💰 Total: 0 ISK")
        self.lbl_kpi_volume.setText("📦 Vol: 0.00 m³")
        self.lbl_kpi_use.setText("🟢 Usar: 0")
        self.lbl_kpi_sell.setText("💰 Vender: 0")
        self.lbl_kpi_hoard.setText("📦 Guardar: 0")
        self.lbl_kpi_trash.setText("⚪ Reprocessar: 0")
        self.btn_filter_all.setText("Todos (0)")
        self.btn_filter_use.setText("🟢 Usar (0)")
        self.btn_filter_sell.setText("💰 Vender (0)")
        self.btn_filter_hoard.setText("📦 Guardar (0)")
        self.btn_filter_trash.setText("⚪ Reprocessar (0)")
        self.lbl_loot_status.setText("Lista limpa. Pronto para nova análise.")

    # ----------------------------------------------------
    # ABA 4: COMBAT LOG (TELEMETRIA AO VIVO & CONTADOR DE TIROS)
    # ----------------------------------------------------
    def setup_combat_tab(self):
        layout = QVBoxLayout(self.tab_combat)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 1. Painel Superior de Telemetria de Evasão e Disparos
        self.combat_telemetry_card = QFrame()
        self.combat_telemetry_card.setStyleSheet("""
            background: rgba(14, 16, 20, 0.65);
            border: 1px solid rgba(120, 120, 120, 0.20);
            padding: 6px;
        """)
        c_layout = QVBoxLayout(self.combat_telemetry_card)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(5)

        lbl_top = QLabel("TELEMETRIA DE DISPAROS & EVASÃO TRANSVERSAL:")
        lbl_top.setStyleSheet("font-size: 10px; color: #888888; font-weight: bold; font-family: 'Share Tech Mono', monospace;")
        c_layout.addWidget(lbl_top)

        # Indicadores principais em linha
        stats_row = QHBoxLayout()
        stats_row.setSpacing(10)

        self.lbl_stat_shots = QLabel("🎯 Disparos: 0")
        self.lbl_stat_shots.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffffff; font-family: 'Share Tech Mono', monospace;")

        self.lbl_stat_misses = QLabel("🛡️ Erros: 0 (0.0% Evasão)")
        self.lbl_stat_misses.setStyleSheet("font-size: 12px; font-weight: bold; color: #40c057; font-family: 'Share Tech Mono', monospace;")

        self.lbl_stat_hits = QLabel("💥 Acertos: 0 (0.0%)")
        self.lbl_stat_hits.setStyleSheet("font-size: 12px; font-weight: bold; color: #f03e3e; font-family: 'Share Tech Mono', monospace;")

        self.lbl_stat_dmg = QLabel("🩸 Dano: 0 HP")
        self.lbl_stat_dmg.setStyleSheet("font-size: 12px; font-weight: bold; color: #ffd43b; font-family: 'Share Tech Mono', monospace;")

        stats_row.addWidget(self.lbl_stat_shots)
        stats_row.addWidget(self.lbl_stat_misses)
        stats_row.addWidget(self.lbl_stat_hits)
        stats_row.addWidget(self.lbl_stat_dmg)
        stats_row.addStretch()
        c_layout.addLayout(stats_row)

        # Barra de Evasão Visual (Proporção Misses vs Hits)
        self.progress_evasion = QProgressBar()
        self.progress_evasion.setFixedHeight(8)
        self.progress_evasion.setRange(0, 100)
        self.progress_evasion.setValue(0)
        self.progress_evasion.setTextVisible(False)
        self.progress_evasion.setStyleSheet("""
            QProgressBar {
                background: rgba(180, 40, 40, 0.70);
                border: 1px solid rgba(120, 120, 120, 0.25);
            }
            QProgressBar::chunk {
                background: #40c057;
            }
        """)
        c_layout.addWidget(self.progress_evasion)

        # Linha de Qualidade dos Impactos
        self.lbl_hit_qualities = QLabel("Impactos: Grazes: 0 | Glances: 0 | Hits: 0 | Penetrates: 0 | Smashes: 0 | Wrecks: 0")
        self.lbl_hit_qualities.setStyleSheet("font-size: 9.5px; color: #999999; font-family: 'Share Tech Mono', monospace;")
        c_layout.addWidget(self.lbl_hit_qualities)

        # Linha de Botões do Painel
        btn_panel_row = QHBoxLayout()
        btn_panel_row.setSpacing(6)

        btn_copy_report = QPushButton("📋 Copiar Relatório para IA")
        btn_copy_report.setFixedHeight(22)
        btn_copy_report.setToolTip("Copia um relatório completo formatado em Markdown com métricas de evasão e atacantes para colar no ChatGPT/Claude/Ollama")
        btn_copy_report.setStyleSheet("""
            QPushButton {
                background: rgba(40, 55, 75, 0.90);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.30);
                font-weight: bold;
                font-size: 10.5px;
            }
            QPushButton:hover {
                background: rgba(55, 75, 105, 0.95);
            }
        """)
        btn_copy_report.clicked.connect(self.handle_copy_combat_report_to_ai)

        btn_reset_stats = QPushButton("🔄 Zerar")
        btn_reset_stats.setFixedHeight(22)
        btn_reset_stats.setToolTip("Zera os contadores para iniciar a medição da próxima missão/pocket")
        btn_reset_stats.setStyleSheet("font-size: 10px;")
        btn_reset_stats.clicked.connect(self.handle_reset_combat_stats)

        btn_reload_stats = QPushButton("📜 Recarregar da Sessão")
        btn_reload_stats.setFixedHeight(22)
        btn_reload_stats.setToolTip("Recalcula as estatísticas completas lendo todo o log da sessão atual")
        btn_reload_stats.setStyleSheet("font-size: 10px;")
        btn_reload_stats.clicked.connect(self.handle_reload_combat_stats)

        self.lbl_report_status = QLabel("")
        self.lbl_report_status.setStyleSheet("font-size: 10px; color: #40c057;")

        btn_panel_row.addWidget(btn_copy_report)
        btn_panel_row.addWidget(btn_reset_stats)
        btn_panel_row.addWidget(btn_reload_stats)
        btn_panel_row.addWidget(self.lbl_report_status)
        btn_panel_row.addStretch()
        c_layout.addLayout(btn_panel_row)

        layout.addWidget(self.combat_telemetry_card)

        # 2. Stream de Log em Tempo Real
        lbl_stream = QLabel("LOG DE COMBATE AO VIVO:")
        lbl_stream.setStyleSheet("font-size: 10px; color: #888888; font-family: 'Share Tech Mono', monospace;")
        layout.addWidget(lbl_stream)

        self.txt_combat = QTextEdit()
        self.txt_combat.setReadOnly(True)
        self.txt_combat.setStyleSheet("background: rgba(12, 12, 12, 0.70); font-family: 'Share Tech Mono', monospace; font-size: 10px;")
        layout.addWidget(self.txt_combat)

        btn_row = QHBoxLayout()
        btn_clear = QPushButton("Limpar Texto")
        btn_clear.clicked.connect(lambda: self.txt_combat.clear())
        btn_row.addStretch()
        btn_row.addWidget(btn_clear)
        layout.addLayout(btn_row)

    def update_combat_telemetry_ui(self):
        shots = self.combat_stats.get("total_shots", 0)
        hits = self.combat_stats.get("total_hits", 0)
        misses = self.combat_stats.get("total_misses", 0)
        dmg = self.combat_stats.get("total_damage", 0.0)
        evasion_pct = (misses / shots * 100.0) if shots > 0 else 0.0
        hit_pct = (hits / shots * 100.0) if shots > 0 else 0.0

        if hasattr(self, 'lbl_stat_shots'):
            self.lbl_stat_shots.setText(f"🎯 Disparos: {shots:,}")
        if hasattr(self, 'lbl_stat_misses'):
            self.lbl_stat_misses.setText(f"🛡️ Erros: {misses:,} ({evasion_pct:.1f}% Evasão)")
        if hasattr(self, 'lbl_stat_hits'):
            self.lbl_stat_hits.setText(f"💥 Acertos: {hits:,} ({hit_pct:.1f}%)")
        if hasattr(self, 'lbl_stat_dmg'):
            self.lbl_stat_dmg.setText(f"🩸 Dano: {dmg:,.0f} HP")
        if hasattr(self, 'progress_evasion'):
            self.progress_evasion.setValue(int(round(evasion_pct)))

        qc = self.combat_stats.get("quality_counts", {})
        q_str = f"Grazes: {qc.get('Grazes', 0):,} | Glances: {qc.get('Glances Off', 0):,} | Hits: {qc.get('Hits', 0):,} | Penetrates: {qc.get('Penetrates', 0):,} | Smashes: {qc.get('Smashes', 0):,} | Wrecks: {qc.get('Wrecks', 0):,}"
        if hasattr(self, 'lbl_hit_qualities'):
            self.lbl_hit_qualities.setText(f"Impactos: {q_str}")

        if hasattr(self, 'lbl_footer_left') and shots > 0:
            self.lbl_footer_left.setText(f"🎯 Tiros: {shots:,} | 🛡️ Evasão: {evasion_pct:.1f}% ({misses:,} err / {hits:,} ac)")

    def handle_reset_combat_stats(self):
        self.combat_stats = {
            "total_shots": 0,
            "total_hits": 0,
            "total_misses": 0,
            "total_damage": 0.0,
            "quality_counts": {},
            "attackers": {},
            "session_filename": self.combat_stats.get("session_filename", "")
        }
        self.update_combat_telemetry_ui()
        if hasattr(self, 'lbl_report_status'):
            self.lbl_report_status.setText("Contadores zerados.")

    def handle_reload_combat_stats(self):
        if hasattr(self, 'watcher'):
            latest = self.watcher.find_latest_log()
            if latest:
                stats = parse_log_session_stats(latest)
                if stats:
                    self.combat_stats["total_shots"] = stats["total_shots"]
                    self.combat_stats["total_hits"] = stats["total_hits"]
                    self.combat_stats["total_misses"] = stats["total_misses"]
                    self.combat_stats["total_damage"] = stats["total_damage"]
                    self.combat_stats["quality_counts"] = stats["quality_counts"]
                    self.combat_stats["attackers"] = dict(stats["top_attackers"])
                    self.combat_stats["session_filename"] = os.path.basename(latest)
                    self.update_combat_telemetry_ui()
                    if hasattr(self, 'lbl_report_status'):
                        self.lbl_report_status.setText(f"Sessão recarregada: {stats['total_shots']:,} tiros processados.")

    def handle_copy_combat_report_to_ai(self):
        shots = self.combat_stats.get("total_shots", 0)
        hits = self.combat_stats.get("total_hits", 0)
        misses = self.combat_stats.get("total_misses", 0)
        dmg = self.combat_stats.get("total_damage", 0.0)
        evasion_pct = (misses / shots * 100.0) if shots > 0 else 0.0
        hit_pct = (hits / shots * 100.0) if shots > 0 else 0.0
        avg_dmg = (dmg / hits) if hits > 0 else 0.0
        fname = self.combat_stats.get("session_filename", "Gamelog EVE")
        qc = self.combat_stats.get("quality_counts", {})
        att = self.combat_stats.get("attackers", {})

        top_att_lines = []
        if isinstance(att, dict):
            sorted_att = sorted(att.items(), key=lambda x: x[1], reverse=True)[:8]
            for name, count in sorted_att:
                top_att_lines.append(f"- **{name}:** {count:,} disparos")
        elif isinstance(att, list):
            for name, count in att[:8]:
                top_att_lines.append(f"- **{name}:** {count:,} disparos")

        att_block = "\n".join(top_att_lines) if top_att_lines else "- Nenhum atacante isolado identificado."

        report = f"""# 📊 Relatório de Telemetria de Combate & Evasão (EVE Online)
**Arquivo de Sessão:** `{fname}`
**Amostra:** {shots:,} disparos monitorados

## 1. Métricas de Defesa e Velocidade Transversal:
- **Total de Tiros Disparados Contra Mim:** {shots:,}
- **Tiros que Erraram (Misses / Evasão):** {misses:,} ({evasion_pct:.1f}% Taxa de Evasão)
- **Tiros que Acertaram (Hits):** {hits:,} ({hit_pct:.1f}%)
- **Dano Total Absorvido:** {dmg:,.1f} HP
- **Dano Médio por Acerto:** {avg_dmg:.1f} HP

## 2. Qualidade dos Impactos Recebidos (Tracking Enemy):
- **Grazes (De Raspão / 50% dano base):** {qc.get('Grazes', 0):,}
- **Glances Off (Arranhão / 67% dano base):** {qc.get('Glances Off', 0):,}
- **Hits (Acerto Padrão / 100% dano base):** {qc.get('Hits', 0):,}
- **Penetrates (Penetração / 125% dano base):** {qc.get('Penetrates', 0):,}
- **Smashes (Impacto Pesado / 149% dano base):** {qc.get('Smashes', 0):,}
- **Wrecks (Acerto Crítico / 300% dano base):** {qc.get('Wrecks', 0):,}

## 3. Principais Atacantes:
{att_block}

---
### 🧠 Avaliação para IA:
Avalie a minha evasão angular e velocidade transversal nesta sessão de combate. Com base na taxa de evasão de {evasion_pct:.1f}% e na distribuição dos impactos recebidos, o que posso aprimorar na minha pilotagem, órbita e vetor de voo para mitigar ainda mais os danos sofridos?
"""
        cb = QApplication.clipboard()
        if cb:
            cb.setText(report)
        if hasattr(self, 'lbl_report_status'):
            self.lbl_report_status.setText("✅ Relatório copiado para o clipboard!")

    # ----------------------------------------------------
    # ABA 4: MISSIONS (TRADUTOR ESTRATÉGICO VIA OLLAMA)
    # ----------------------------------------------------
    def setup_missions_tab(self):
        layout = QVBoxLayout(self.tab_missions)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        lbl_desc = QLabel("Briefing em inglês da missão (cole o texto do EVE):")
        lbl_desc.setStyleSheet("font-size: 10px; color: #888888;")
        layout.addWidget(lbl_desc)

        self.txt_mission_in = QTextEdit()
        self.txt_mission_in.setPlaceholderText("Cole o briefing aqui (ex: Pirate Invasion, Recon, Blockade)...")
        self.txt_mission_in.setMaximumHeight(80)
        layout.addWidget(self.txt_mission_in)

        btn_analyze = QPushButton("🧠 ANALISAR MISSÃO // OLLAMA")
        btn_analyze.clicked.connect(self.handle_mission_ai)
        layout.addWidget(btn_analyze)

        self.txt_mission_out = QTextEdit()
        self.txt_mission_out.setReadOnly(True)
        self.txt_mission_out.setPlaceholderText("A tradução tática em português com fraquezas de dano e gatilhos aparecerá aqui...")
        layout.addWidget(self.txt_mission_out)

    # ----------------------------------------------------
    # ABA 5: ADVISOR (COPILOTO CONVERSACIONAL)
    # ----------------------------------------------------
    def setup_advisor_tab(self):
        layout = QVBoxLayout(self.tab_advisor)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.txt_advisor_out = QTextEdit()
        self.txt_advisor_out.setReadOnly(True)
        self.txt_advisor_out.setText(
            "[SYSTEM READY] Copiloto tático conectado ao modelo local.\n"
            "Pergunte sobre táticas de PvP/PvE, manobras de kite/orbit ou ajustes de nave.\n"
        )
        layout.addWidget(self.txt_advisor_out)

        in_layout = QHBoxLayout()
        in_layout.setSpacing(4)
        self.txt_advisor_in = QLineEdit()
        self.txt_advisor_in.setPlaceholderText("Instrução ao copiloto...")
        self.txt_advisor_in.returnPressed.connect(self.handle_ask_copilot)

        btn_send = QPushButton("Enviar")
        btn_send.clicked.connect(self.handle_ask_copilot)

        in_layout.addWidget(self.txt_advisor_in)
        in_layout.addWidget(btn_send)
        layout.addLayout(in_layout)

    # ----------------------------------------------------
    # INTEGRAÇÃO COM LOGS E ÁREA DE TRANSFERÊNCIA
    # ----------------------------------------------------
    def start_log_watcher(self):
        log_dir = self.config.get("log_dir")
        if os.path.exists(log_dir):
            self.watcher = EveLogWatcher(log_dir, on_event_callback=lambda evt: self.bridge.event_received.emit(evt))
            self.watcher.start()

    def start_target_scanner(self):
        self.scanner = TargetScanner()
        self.scanner.target_detected.connect(self.handle_target_detected)

    def manual_clipboard_scan(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            text = clipboard.text().strip()
            if text:
                faction_data, ship_size = analyze_target_text(text)
                self.update_target_intel(text, faction_data, ship_size)
                self.navigate_to_module("copilot")

    def add_or_update_overview_row(self, tag_type, dist, name, stype, vel, rvel):
        if not name or name in ["Inimigo", "Alvo", "Your"]:
            return
        # Procura se o alvo já existe na tabela para atualizar
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 2)
            if item and item.text().strip().lower() == name.strip().lower():
                if dist and dist != "—":
                    self.table.item(r, 1).setText(dist)
                if stype and stype != "—" and stype != "Hostile":
                    self.table.item(r, 3).setText(stype)
                if vel and vel != "—":
                    self.table.item(r, 4).setText(vel)
                if rvel and rvel != "—":
                    self.table.item(r, 5).setText(rvel)
                return

        # Insere novo objeto detectado no início da tabela do usuário
        self.table.insertRow(0)
        self.table.setRowHeight(0, self.get_table_row_height())

        type_lbl = QLabel(f"● {tag_type.upper()}")
        if tag_type == "hostile":
            type_lbl.setStyleSheet("color: #f03e3e; font-weight: bold; padding-left: 5px;")
        elif tag_type == "gate":
            type_lbl.setStyleSheet("color: #ffd43b; font-weight: bold; padding-left: 5px;")
        elif tag_type == "station":
            type_lbl.setStyleSheet("color: #40c057; font-weight: bold; padding-left: 5px;")
        else:
            type_lbl.setStyleSheet("color: #4dabf7; font-weight: bold; padding-left: 5px;")

        self.table.setCellWidget(0, 0, type_lbl)
        self.table.setItem(0, 1, QTableWidgetItem(str(dist)))
        self.table.setItem(0, 2, QTableWidgetItem(str(name)))
        self.table.setItem(0, 3, QTableWidgetItem(str(stype)))
        self.table.setItem(0, 4, QTableWidgetItem(str(vel)))
        self.table.setItem(0, 5, QTableWidgetItem(str(rvel)))

        # Alinhamento estético do terminal EVE
        for col in [1, 4, 5]:
            it = self.table.item(0, col)
            if it:
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        count = self.table.rowCount()
        self.lbl_footer_left.setText(f"{count} objects loaded")

    def handle_target_detected(self, data):
        # Trata triagem de carga / inventário / loot copiado via Ctrl+C no jogo
        if data.get("type") == "loot_triage":
            loot_text = data.get("loot_text", "")
            if loot_text:
                self.process_loot_text(loot_text)
                self.navigate_to_module("loot")
                self.txt_combat.append("<span style='color: #ffd43b;'>[LOOT]</span> Relatório de triagem de carga gerado.")
            return

        # Trata caso especial de Ship Fitting importado via Ctrl+C no jogo
        if data.get("type") == "pilot_fit" or data.get("is_fitting"):
            ship = data.get("ship_name") or data.get("ship", "Sua Nave")
            fit = data.get("fit_name", "Fitting")
            fit_text = data.get("fit_text", "")
            self.lbl_target_tag.setText("PILOT SHIP LOADOUT")
            self.lbl_target_tag.setStyleSheet("color: #40c057; font-size: 13px; font-weight: bold;")
            self.lbl_target_title.setText(ship.upper())
            self.lbl_target_subinfo.setText(f"Fit Ativo: {fit} • Casco: {ship}")
            self.lbl_ammo_advice.setText("Configuração Tática da Sua Nave carregada com sucesso.")
            self.lbl_drone_advice.setText("Drones: Bônus de dano massivo para Drones Gallente (Hobgoblin para Térmico, Hornet para Cinético).")
            self.lbl_flight_advice.setText("Diretriz de Voo: Mantenha Afterburner ativo e órbite a 20-30km enquanto seus Drones destroem o alvo.")
            self.lbl_ewar_advice.setText("Defesa Ativa: Medium Armor Repairer com Capacitor Control Circuit. Monitore seu capacitor se tomar neut!")
            self.lbl_footer_left.setText(f"Nave Ativa: {ship}")
            # Alimenta o Ship Manager e o HUD Tático automaticamente
            if fit_text and hasattr(self, 'ship_manager') and hasattr(self, 'tab_tactics'):
                try:
                    parsed, prof = self.ship_manager.import_eft(fit_text)
                    if prof:
                        self.tab_tactics.set_active_fit(prof)
                        if hasattr(self, 'tab_ships'):
                            self.tab_ships.current_profile = prof
                            self.tab_ships.refresh_fits_combo()
                            self.tab_ships.display_profile(prof, parsed)
                        self.txt_combat.append(f"<span style='color: #40c057;'>🛠️ [SHIP MANAGER]</span> Fitting <b>{fit}</b> ({ship}) importado e validado automaticamente!")
                except Exception:
                    pass

            # Alimenta a aba de Mercado e cota automaticamente
            if fit_text:
                self.txt_fit_input.setPlainText(fit_text)
                self.handle_quote_current_fit()
                self.navigate_to_module("ships") # Direciona para o Ship Manager
            else:
                self.navigate_to_module("copilot")
            return

        raw = data.get("raw_text")
        dist = data.get("distance", "—")
        stype = data.get("ship_type", "Ship")
        vel = data.get("velocity", "—")
        radial = data.get("radial", "—")
        faction = data.get("faction")
        ship_size = data.get("ship_size")

        self.add_or_update_overview_row("hostile", dist, raw, ship_size or stype, vel, radial)
        self.update_target_intel(raw, faction, ship_size or stype)
        self.txt_combat.append(f"<span style='color: #888888;'>[SCANNER]</span> Alvo importado: <b>{raw}</b> ({ship_size or stype})")
        self.navigate_to_module("copilot")

    def update_target_intel(self, raw_name, faction, ship_size):
        self.lbl_target_title.setText(raw_name.upper())
        if faction:
            fname = faction.get("name", "Unknown Faction")
            weakness = faction.get("weakness", "Geral")
            self.lbl_target_subinfo.setText(f"Faction: {fname} • Class: {ship_size or 'Hostile'} • Threat: {faction.get('danger_level', 'Normal')}")
            self.lbl_ammo_advice.setText(f"Munição: {faction.get('ammo_to_use', 'Padrão')} • Fraqueza: {weakness}")
            self.lbl_drone_advice.setText(f"Drones recomendados: {faction.get('drones_to_use', 'Drones velozes')}")
            self.lbl_flight_advice.setText(faction.get("optimal_distance", "Mantenha órbita e transversal alta."))
            self.lbl_ewar_advice.setText(f"Prioridade: {faction.get('priority', 'Eliminar fragatas primeiro.')}")
            self.lbl_footer_left.setText(f"Target: {fname}")
            # Fala tática de bordo quando o alvo é detectado
            self.sound_manager.speak(
                f"Alvo {raw_name}. Fraqueza identificada: dano {weakness}.",
                cooldown=6.0
            )
        else:
            self.lbl_target_subinfo.setText(f"Target: {raw_name} • Class: {ship_size or 'Hostile'}")
            self.lbl_ammo_advice.setText("Munição: Utilize munição com maior DPS da sua nave (bônus de casco).")
            self.lbl_drone_advice.setText("Drones: Drones de alta velocidade de voo.")
            self.lbl_flight_advice.setText("Mantenha velocidade transversal contra as baterias inimigas.")
            self.lbl_ewar_advice.setText("Nenhuma anomalia eletrônica detectada.")
            self.lbl_footer_left.setText(f"Target: {raw_name}")

        # Sincroniza o HUD tático avançado com o alvo selecionado/copiado
        if hasattr(self, 'tab_tactics'):
            idx = self.tab_tactics.combo_enemy.findText(raw_name)
            if idx >= 0:
                self.tab_tactics.combo_enemy.setCurrentIndex(idx)
            else:
                self.tab_tactics.on_enemy_changed(raw_name)

        hack_words = ["relic", "debris", "monument", "remains", "ruin", "databank", "comms", "mainframe", "survey", "array", "vault", "enclave"]
        if any(w in raw_name.lower() for w in hack_words) and hasattr(self, 'tab_hacking'):
            self.tab_hacking.auto_configure(target_name=raw_name)

    def handle_tactical_voice_guidance(self, data: dict):
        """
        Narrador Tático / Treinador de Combate em Tempo Real (Voz Sci-Fi Aura/Jarvis).
        Informa ativamente comandos práticos:
        - "Engajar Kestrel. Mantenha Keep at Range em 5000 metros."
        - "Carregar lente Multifrequency. Prioridade: Controle de distância."
        - "Atenção: Órbita a 2000 metros para quebrar tracking."
        """
        target = data.get("target", "Alvo")
        movement = data.get("movement", "").strip()
        distance = data.get("distance", "").strip()
        ammo = data.get("ammo", "").strip()
        scenario = data.get("scenario", "")

        phrases = []
        if movement:
            if "KEEP AT RANGE" in movement.upper():
                dist_str = f" a {distance}" if distance and distance != "—" else ""
                phrases.append(f"Mantenha Keep at Range{dist_str}")
            elif "ORBIT" in movement.upper():
                dist_str = f" em {distance}" if distance and distance != "—" else ""
                phrases.append(f"Execute Órbita{dist_str}")
            elif "PILOTAGEM MANUAL" in movement.upper():
                phrases.append("Adote pilotagem manual e movimento lateral")
            elif "RETIRADA" in movement.upper():
                phrases.append("Atenção piloto: Superioridade inimiga. Prepare retirada imediata")
            else:
                phrases.append(f"Comando de voo: {movement}")

        if ammo and ammo not in ["—", "None", "None"]:
            phrases.append(f"Carregar {ammo}")

        if phrases:
            text = f"Alvo {target}. " + ". ".join(phrases) + "."
            self.sound_manager.speak(
                text,
                cache_key=f"guide_{target}_{movement}",
                priority=True if "RETIRADA" in movement.upper() else False,
                cooldown=8.0
            )

    def handle_combat_event(self, event):
        etype = event.get("type")
        if etype == "session_stats_loaded":
            stats = event.get("stats", {})
            self.combat_stats["total_shots"] = stats.get("total_shots", 0)
            self.combat_stats["total_hits"] = stats.get("total_hits", 0)
            self.combat_stats["total_misses"] = stats.get("total_misses", 0)
            self.combat_stats["total_damage"] = stats.get("total_damage", 0.0)
            self.combat_stats["quality_counts"] = stats.get("quality_counts", {})
            self.combat_stats["attackers"] = dict(stats.get("top_attackers", []))
            self.combat_stats["session_filename"] = event.get("filename", "")
            self.update_combat_telemetry_ui()
            return

        elif etype == "shot_missed":
            attacker = event.get("attacker", "Inimigo")
            emit_stats = event.get("emit_stats", True)
            if emit_stats:
                self.combat_stats["total_misses"] += 1
                self.combat_stats["total_shots"] += 1
                if isinstance(self.combat_stats["attackers"], dict):
                    self.combat_stats["attackers"][attacker] = self.combat_stats["attackers"].get(attacker, 0) + 1
                self.update_combat_telemetry_ui()

            self.txt_combat.append(f"<span style='color: #40c057;'>🛡️ [ERROU]</span> <b>{attacker}</b> errou o tiro contra você.")
            faction, ship_size = analyze_target_text(attacker)
            self.add_or_update_overview_row("hostile", "Combat", attacker, ship_size or "Hostile", "—", "—")

        elif etype == "drone_under_attack":
            dmg = event.get("damage", 0)
            attacker = event.get("attacker", "Inimigo")
            drone = event.get("drone", "Drone")
            weapon = event.get("weapon", "")
            verb = event.get("verb", "Hits")

            # Fala inteligente de bordo (Aura/Jarvis)
            self.sound_manager.speak(
                f"Atenção piloto. Seu {drone} está sob ataque. Pressione Shift R para recolhê-lo.",
                cache_key="drone_under_attack",
                priority=True,
                cooldown=3.0
            )

            w_str = f" ({weapon})" if weapon else ""
            self.txt_combat.append(
                f"<div style='background: rgba(220, 38, 38, 0.20); border-left: 3px solid #ff3b30; padding: 4px 6px; margin: 3px 0;'>"
                f"<b style='color: #ff4d4d;'>🚨 [ALERTA: DRONE SOB ATAQUE!]</b> "
                f"Seu <b>{drone}</b> tomou <b>-{dmg:.1f} HP</b> [{verb}] de <b>{attacker}</b>{w_str}!<br>"
                f"<span style='color: #ffd43b; font-weight: bold;'>⚠️ RECOLHA IMEDIATAMENTE: [SHIFT + R]</span>"
                f"</div>"
            )

            # Atualiza recomendação de drones no HUD em vermelho chamativo
            self.lbl_drone_advice.setText(f"🚨 ALERTA: {drone.upper()} SOB ATAQUE DE {attacker.upper()}! Pressione [SHIFT + R] para recolher!")
            self.lbl_drone_advice.setStyleSheet("font-size: 11px; color: #ff6b6b; font-weight: bold; font-family: 'Inter', sans-serif;")

            faction, ship_size = analyze_target_text(attacker)
            self.add_or_update_overview_row("hostile", "DroneAggro", attacker, ship_size or "Hostile", "—", "—")

        elif etype == "drone_idle":
            note = event.get("note", "Alvo destruído. Seus drones estão ociosos no espaço.")
            self.sound_manager.speak(
                "Alvo destruído. Seus drones estão ociosos no espaço. Recolha antes de saltar.",
                cache_key="drone_idle",
                priority=False,
                cooldown=12.0
            )
            self.txt_combat.append(
                f"<div style='background: rgba(255, 193, 7, 0.15); border-left: 3px solid #ffc107; padding: 3px 6px; margin: 2px 0;'>"
                f"<b style='color: #ffd43b;'>🛸 [COPILOTO - DRONES OCIOSOS]</b> "
                f"{note}"
                f"</div>"
            )

        elif etype == "drone_left_behind":
            dest = event.get("destination", "espaço")
            self.sound_manager.speak(
                "Alerta de navegação: seus drones foram deixados para trás no espaço.",
                cache_key="drone_left_behind",
                priority=True,
                cooldown=8.0
            )
            self.txt_combat.append(
                f"<div style='background: rgba(220, 38, 38, 0.25); border-left: 3px solid #ff3b30; padding: 4px 6px; margin: 3px 0;'>"
                f"<b style='color: #ff4d4d;'>🚨 [ALERTA: DRONES ESQUECIDOS]</b> "
                f"Você iniciou dobra/salto com drones ativos! Retorne ao setor para recuperá-los."
                f"</div>"
            )

        elif etype == "drone_not_present":
            self.sound_manager.speak(
                "Aviso: drone não localizado no grid de combate.",
                cooldown=10.0
            )

        elif etype == "damage_received":
            dmg = event.get("damage", 0)
            attacker = event.get("attacker", "Inimigo")
            weapon = event.get("weapon", "")
            verb = event.get("verb", "Hits")
            emit_stats = event.get("emit_stats", True)
            if emit_stats:
                self.combat_stats["total_hits"] += 1
                self.combat_stats["total_shots"] += 1
                self.combat_stats["total_damage"] += dmg
                qc = self.combat_stats.setdefault("quality_counts", {})
                qc[verb] = qc.get(verb, 0) + 1
                if isinstance(self.combat_stats["attackers"], dict):
                    self.combat_stats["attackers"][attacker] = self.combat_stats["attackers"].get(attacker, 0) + 1
                self.update_combat_telemetry_ui()

            # Análise Tática Balística e de Vetor de Voo (Tactical Flight Advisor)
            w_tactic = analyze_incoming_weapon(weapon, attacker)
            if w_tactic:
                w_cat = w_tactic.get("category", weapon or "Arma Hostil")
                maneuver = w_tactic.get("recommended_maneuver", "Transversal")
                flight_txt = w_tactic.get("flight_advice", "")
                v_speech = w_tactic.get("voice_advice", "")
                c_key = w_tactic.get("cache_key", "weapon_generic")

                if hasattr(self, 'lbl_detected_weapon'):
                    self.lbl_detected_weapon.setText(f"Arma Detectada: {w_cat}")
                if hasattr(self, 'lbl_flight_maneuver'):
                    self.lbl_flight_maneuver.setText(f"Manobra: {maneuver}")
                if hasattr(self, 'lbl_flight_advice') and flight_txt:
                    self.lbl_flight_advice.setText(flight_txt)

                # Instrução Falada pelo Copiloto (Aura / Jarvis)
                if v_speech:
                    self.sound_manager.speak(
                        v_speech,
                        cache_key=c_key,
                        priority=True if verb in ["Wrecks", "Smashes"] else False,
                        cooldown=15.0
                    )
            elif verb in ["Wrecks", "Smashes"] or dmg > 150:
                self.sound_manager.speak(
                    "Aviso de integridade: dano pesado recebido na blindagem.",
                    cache_key="heavy_damage",
                    priority=False,
                    cooldown=7.0
                )

            w_str = f" ({weapon})" if weapon else ""
            v_color = "#f03e3e" if verb in ["Wrecks", "Smashes"] else "#ff8787" if verb == "Penetrates" else "#ffd43b"
            self.txt_combat.append(f"<span style='color: {v_color};'>▼ -{dmg:.1f} HP [{verb}]</span> de <b>{attacker}</b>{w_str}")
            faction, ship_size = analyze_target_text(attacker)
            self.add_or_update_overview_row("hostile", "Combat", attacker, ship_size or "Hostile", "—", "—")
            self.update_target_intel(attacker, faction, ship_size)

        elif etype == "damage_dealt":
            dmg = event.get("damage", 0)
            target = event.get("target", "Alvo")
            weapon = event.get("weapon", "")
            w_str = f" ({weapon})" if weapon else ""
            self.txt_combat.append(f"<span style='color: #00e5ff;'>▲ +{dmg:.1f} HP</span> em <b>{target}</b>{w_str}")
            faction, ship_size = analyze_target_text(target)
            self.add_or_update_overview_row("hostile", "Combat", target, ship_size or "Hostile", "—", "—")

            # Atualização automática das armas detectadas da sua nave no Ship Manager / HUD
            if weapon and weapon not in ["Sua Arma", "Combat"] and hasattr(self, 'ship_manager') and hasattr(self, 'tab_tactics'):
                active_prof = self.tab_tactics.current_my_fit or {}
                if not active_prof.get("weapon_type") or active_prof.get("weapon_type") == "Desconhecido":
                    active_prof["weapon_type"] = weapon
                    if "pulse" in weapon.lower() or "beam" in weapon.lower() or "laser" in weapon.lower():
                        active_prof.setdefault("weapon_stats", {})["family"] = "pulse_laser"
                    self.tab_tactics.set_active_fit(active_prof)

        elif etype == "target_spotted":
            target = event.get("target", "Alvo")
            note = event.get("note", "")
            self.txt_combat.append(f"<span style='color: #888888;'>[RADAR]</span> <b>{target}</b> - {note}")
            faction, ship_size = analyze_target_text(target)
            self.add_or_update_overview_row("hostile", "Radar", target, ship_size or "Hostile", "—", "—")

        elif etype == "ewar_alert":
            effect = event.get("effect", "")
            player_ship = event.get("player_ship")
            
            # Detecção automática do casco da sua nave revelado pelo log de combate
            if player_ship and hasattr(self, 'ship_manager') and hasattr(self, 'tab_tactics'):
                cur_ship = self.tab_tactics.current_my_fit.get("ship")
                if cur_ship != player_ship:
                    prof = self.ship_manager.get(player_ship)
                    if not prof:
                        prof = self.ship_manager.add(player_ship)
                    self.tab_tactics.set_active_fit(prof)
                    if hasattr(self, 'tab_ships'):
                        self.tab_ships.current_profile = prof
                        self.tab_ships.refresh_fits_combo()
                        self.tab_ships.display_profile(prof)
                    self.txt_combat.append(f"<span style='color: #40c057;'>🛸 [AUTO-DETECÇÃO]</span> Sua nave foi identificada nos logs: <b>{player_ship}</b>")

            eff_upper = effect.upper()
            if "SCRAMBLE" in eff_upper or "DISRUPT" in eff_upper:
                self.sound_manager.speak(
                    "Alerta crítico: motor de dobra bloqueado por inibidor inimigo.",
                    cache_key="scram_alert",
                    priority=True,
                    cooldown=5.0
                )
            elif "WEB" in eff_upper:
                self.sound_manager.speak(
                    "Aviso tático: rede de estase ativa. Velocidade reduzida.",
                    cache_key="web_alert",
                    priority=True,
                    cooldown=5.0
                )
            elif "NEUTRAL" in eff_upper or "DRAIN" in eff_upper:
                self.sound_manager.speak(
                    "Aviso: drenagem de capacitor detectada.",
                    cache_key="neut_alert",
                    priority=True,
                    cooldown=5.0
                )
            elif "ECM" in eff_upper or "JAMM" in eff_upper:
                self.sound_manager.speak(
                    "Alerta: interferência nos sistemas de mira.",
                    cache_key="ecm_alert",
                    priority=True,
                    cooldown=5.0
                )
            else:
                self.sound_manager.speak(
                    f"Alerta tático: {effect} ativo na sua nave.",
                    priority=True,
                    cooldown=5.0
                )
            self.txt_combat.append(f"<b style='color: #f03e3e;'>🚨 [E-WAR CRÍTICO]</b> {effect} ativo contra sua nave!")
            self.lbl_ewar_advice.setText(f"🚨 ALERTA CRÍTICO: {effect.upper()} ATIVO NA SUA NAVE!")
            self.navigate_to_module("copilot")

        elif etype == "stargate_jump":
            dest = event.get("destination", "")
            drones_out = event.get("drones_were_out", False)
            if drones_out:
                self.sound_manager.speak(
                    "Alerta de navegação: seus drones foram deixados para trás no espaço.",
                    cache_key="drone_left_behind",
                    priority=True,
                    cooldown=8.0
                )
            self.lbl_footer_left.setText(f"System: {dest}")

        elif etype == "own_shot_missed":
            target = event.get("target", "Alvo")
            self.txt_combat.append(f"<span style='color: #d29922;'>⚠️ [SEU TIRO ERROU]</span> Seu disparo contra <b>{target}</b> errou devido ao tracking/distância!")
            if hasattr(self, 'tab_tactics'):
                self.tab_tactics.trigger_tactical_alert(f"TRACKING INEFICIENTE: Tiro errou {target}. Aumente a distância ou reduza a velocidade angular.")
            self.sound_manager.speak(
                "Aviso tático: disparo ineficaz por velocidade angular. Ajuste a rota.",
                cache_key="tracking_miss",
                priority=False,
                cooldown=12.0
            )

        elif etype == "undocked":
            solarsystem = event.get("system", "")
            self.lbl_footer_left.setText(f"System: {solarsystem}")
            self.sound_manager.speak(
                f"Desacoplagem concluída no sistema {solarsystem}.",
                cooldown=10.0
            )

    def handle_mission_ai(self):
        txt = self.txt_mission_in.toPlainText().strip()
        if not txt:
            return
        self.txt_mission_out.setText("⏳ Analisando inteligência com o Ollama...")
        QApplication.processEvents()
        res = self.advisor.analyze_mission(txt)
        self.txt_mission_out.setText(res)

    def handle_ask_copilot(self):
        q = self.txt_advisor_in.text().strip()
        if not q:
            return
        self.txt_advisor_out.append(f"\nPiloto: {q}")
        self.txt_advisor_in.clear()
        self.txt_advisor_out.append("<i>Calculando vetor tático...</i>")
        QApplication.processEvents()
        ans = self.advisor.ask_tactical_advice(q)
        self.txt_advisor_out.append(f"Copiloto: {ans}")

    def toggle_collapse(self):
        if not self.is_collapsed:
            self.body_widget.hide()
            self.resize(self.width(), 26)
            self.header.btn_roll.setText("◻")
            self.is_collapsed = True
        else:
            self.body_widget.show()
            self.resize(self.expanded_width, self.expanded_height)
            self.header.btn_roll.setText("◽")
            self.is_collapsed = False

    def closeEvent(self, event):
        self.save_config()
        if hasattr(self, 'detached_windows'):
            for dw in list(self.detached_windows.values()):
                try:
                    dw.close()
                except Exception:
                    pass
        super().closeEvent(event)

def main():
    os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
    app = QApplication(sys.argv)
    app.setApplicationName("eve-tactical-copilot")
    app.setDesktopFileName("eve-tactical-copilot")
    
    window = EveOverviewWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
