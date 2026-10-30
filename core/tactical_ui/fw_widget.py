"""
core/tactical_ui/fw_widget.py - Assistente Faction Warfare e D-Scan.
Atende às Seções 12, 13 e 18 do Manual:
- Tabela de complexos de FW (Novice, Small, Medium, Large, Open) com restrições e regras.
- Parser e visualizador tático de D-Scan colado pelo piloto.
- Classificação de ameaças imediatas e naves que não entram no complexo atual.
- Recomendador de naves baseado em orçamento, Alpha/Omega e estilo.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from core.tactical.fw import COMPLEX_TYPES, check_entry, parse_dscan, explain_complex
from core.tactical.recommend import recommend

class FWAssistantWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: D-Scan Parser e Complexos FW
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        # Seletor de Complexo FW
        complex_group = QGroupBox("Complexo Atual (Faction Warfare)")
        c_layout = QVBoxLayout(complex_group)
        
        c_sel_layout = QHBoxLayout()
        c_sel_layout.addWidget(QLabel("Complexo:"))
        self.combo_complex = QComboBox()
        for c_key in COMPLEX_TYPES.keys():
            self.combo_complex.addItem(c_key, c_key)
        self.combo_complex.currentIndexChanged.connect(self.on_complex_changed)
        c_sel_layout.addWidget(self.combo_complex, 1)
        c_layout.addLayout(c_sel_layout)

        self.lbl_complex_rules = QLabel()
        self.lbl_complex_rules.setWordWrap(True)
        self.lbl_complex_rules.setStyleSheet("color: #8b949e; font-size: 11px; padding-top: 4px;")
        c_layout.addWidget(self.lbl_complex_rules)
        left_layout.addWidget(complex_group)

        # D-Scan Parser
        dscan_group = QGroupBox("D-Scan Tático (Cole o resultado do Directional Scanner)")
        dscan_layout = QVBoxLayout(dscan_group)

        self.txt_dscan = QTextEdit()
        self.txt_dscan.setPlaceholderText("Cole o D-Scan aqui (Ctrl+A e Ctrl+C dentro do EVE):\nKestrel   1,234 km   -\nTristan   5.2 AU   -")
        dscan_layout.addWidget(self.txt_dscan, 1)

        btn_dscan = QPushButton("📡 Analisar D-Scan")
        btn_dscan.setStyleSheet("background-color: #1f6feb; color: white; font-weight: bold; padding: 6px;")
        btn_dscan.clicked.connect(self.parse_dscan_ui)
        dscan_layout.addWidget(btn_dscan)

        # Tabela de Contatos Detectados
        self.table_dscan = QTableWidget(0, 3)
        self.table_dscan.setHorizontalHeaderLabels(["Nave", "Distância", "Status no Complexo"])
        self.table_dscan.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_dscan.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_dscan.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_dscan.verticalHeader().setVisible(False)
        dscan_layout.addWidget(self.table_dscan, 1)

        left_layout.addWidget(dscan_group, 1)
        splitter.addWidget(left_widget)

        # Painel Direito: Recomendador de Naves (Seção 18)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        rec_group = QGroupBox("Recomendador de Naves & Doutrina (Seção 18 do Manual)")
        rec_layout = QVBoxLayout(rec_group)

        rec_desc = QLabel(
            "<i>Princípio do Manual: O Copilot nunca deve privilegiar naves caras. "
            "Recomenda opções baratas e eficientes para curva de aprendizado de acordo com o clone e milícia.</i>"
        )
        rec_desc.setWordWrap(True)
        rec_desc.setStyleSheet("color: #8b949e; font-size: 11px;")
        rec_layout.addWidget(rec_desc)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Estilo:"))
        self.combo_style = QComboBox()
        self.combo_style.addItems(["Todos", "Brawler", "Kiter", "Scram Kiter", "Fleet Support"])
        self.combo_style.currentIndexChanged.connect(self.update_recommendations)
        filter_layout.addWidget(self.combo_style)

        filter_layout.addWidget(QLabel("Complexo:"))
        self.combo_rec_complex = QComboBox()
        self.combo_rec_complex.addItems(["Todos", "Novice", "Small", "Medium"])
        self.combo_rec_complex.currentIndexChanged.connect(self.update_recommendations)
        filter_layout.addWidget(self.combo_rec_complex)

        rec_layout.addLayout(filter_layout)

        self.table_rec = QTableWidget(0, 4)
        self.table_rec.setHorizontalHeaderLabels(["Nave", "Função / Estilo", "Custo Est.", "Motivo da Recomendação"])
        self.table_rec.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_rec.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table_rec.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_rec.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_rec.verticalHeader().setVisible(False)
        rec_layout.addWidget(self.table_rec, 1)

        right_layout.addWidget(rec_group, 1)
        splitter.addWidget(right_widget)

        splitter.setSizes([400, 450])
        layout.addWidget(splitter, 1)

        self.on_complex_changed(0)
        self.update_recommendations()

    def on_complex_changed(self, index):
        c_key = self.combo_complex.currentText()
        exp = explain_complex(c_key)
        self.lbl_complex_rules.setText(f"<b>Regras do Complexo:</b> {exp}")
        self.recheck_dscan_entries()

    def parse_dscan_ui(self):
        text = self.txt_dscan.toPlainText().strip()
        if not text:
            return
        res = parse_dscan(text)
        entries = res.get("entries", [])
        self.table_dscan.setRowCount(len(entries))
        current_complex = self.combo_complex.currentText()

        for row, entry in enumerate(entries):
            ship_name = entry.get("ship_name", "Desconhecido")
            dist = entry.get("distance_raw", "N/A")
            s_class = entry.get("class", "Frigate")
            check = check_entry(current_complex, s_class)
            verdict = check.get("verdict", "DESCONHECIDO")

            it_ship = QTableWidgetItem(f"{ship_name} ({s_class})")
            it_dist = QTableWidgetItem(dist)
            
            if "PERMITIDO" in verdict:
                status_text = "Entra no Complexo"
                color = "#f85149" # perigo
            elif "RESTRITO" in verdict:
                status_text = "NÃO entra (Pesada)"
                color = "#7ee787" # seguro
            else:
                status_text = "Neutro / Não verificado"
                color = "#8b949e"

            it_status = QTableWidgetItem(status_text)
            it_status.setForeground(QColor(color))

            self.table_dscan.setItem(row, 0, it_ship)
            self.table_dscan.setItem(row, 1, it_dist)
            self.table_dscan.setItem(row, 2, it_status)

    def recheck_dscan_entries(self):
        if self.table_dscan.rowCount() > 0:
            self.parse_dscan_ui()

    def update_recommendations(self):
        style = self.combo_style.currentText()
        if style == "Todos": style = None
        complex_type = self.combo_rec_complex.currentText()
        if complex_type == "Todos": complex_type = None

        prefs = {
            "budget_isk": 50_000_000,
            "clone_status": "Alpha",
            "preferred_complex": complex_type,
            "playstyle": style
        }
        recs = recommend(prefs, top_n=6)

        self.table_rec.setRowCount(len(recs))
        for row, r in enumerate(recs):
            it_name = QTableWidgetItem(r.get("ship", ""))
            it_name.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            it_style = QTableWidgetItem(r.get("role", ""))
            it_cost = QTableWidgetItem(f"{r.get('hull_cost_isk', 0) / 1_000_000:.1f}M ISK")
            it_reason = QTableWidgetItem(r.get("why", ""))

            self.table_rec.setItem(row, 0, it_name)
            self.table_rec.setItem(row, 1, it_style)
            self.table_rec.setItem(row, 2, it_cost)
            self.table_rec.setItem(row, 3, it_reason)
