"""
core/tactical_ui/training_widget.py - Modo de Treino, AAR e Histórico do Piloto.
Atende às Seções 15, 16 e 17 do Manual:
- Treinamento offline com 10 exercícios práticos e quiz conceitual explicativo.
- AAR (After Action Review) baseado estritamente em fatos (danos reais, logs, killmail).
- Histórico do piloto com detecção de padrões de derrotas (ex: morte para tracking, falta de capacitor).
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTabWidget, QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from core.tactical.training import (
    EXERCISES, CONCEPTS, PilotHistory, after_action_review, answer_concept
)

class TrainingTabWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.history = PilotHistory()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        tabs = QTabWidget()
        tabs.addTab(self.create_quiz_tab(), "🎓 Perguntas Conceituais")
        tabs.addTab(self.create_exercises_tab(), "🎯 10 Exercícios Práticos")
        tabs.addTab(self.create_aar_tab(), "📋 After Action Review (AAR)")
        tabs.addTab(self.create_history_tab(), "📊 Histórico & Padrões de Morte")
        
        main_layout.addWidget(tabs)

    # 1. QUIZ CONCEITUAL
    def create_quiz_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("<b>Base Conceitual Offline (Seções 17 e 23 do Manual)</b>"))
        self.lbl_quiz_title = QLabel("Carregando pergunta...")
        self.lbl_quiz_title.setWordWrap(True)
        self.lbl_quiz_title.setStyleSheet("font-size: 13px; font-weight: bold; padding: 10px; background: #161b22; border-radius: 4px; color: #58a6ff;")
        layout.addWidget(self.lbl_quiz_title)

        self.txt_concept_answer = QTextEdit()
        self.txt_concept_answer.setReadOnly(True)
        self.txt_concept_answer.setStyleSheet("font-size: 12px; line-height: 1.4;")
        layout.addWidget(self.txt_concept_answer, 1)

        btn_box = QHBoxLayout()
        self.btn_prev_quiz = QPushButton("⬅️ Pergunta Anterior")
        self.btn_prev_quiz.setStyleSheet("background-color: #30363d; color: white; padding: 6px 14px;")
        self.btn_prev_quiz.clicked.connect(self.load_prev_concept)
        btn_box.addWidget(self.btn_prev_quiz)

        self.btn_next_quiz = QPushButton("Próxima Pergunta ➡️")
        self.btn_next_quiz.setStyleSheet("background-color: #1f6feb; color: white; padding: 6px 14px; font-weight: bold;")
        self.btn_next_quiz.clicked.connect(self.load_next_concept)
        btn_box.addWidget(self.btn_next_quiz)
        btn_box.addStretch()
        layout.addLayout(btn_box)

        self.current_concept_idx = 0
        self.load_concept(0)
        return w

    def load_concept(self, idx):
        if not CONCEPTS:
            return
        self.current_concept_idx = idx % len(CONCEPTS)
        c = CONCEPTS[self.current_concept_idx]
        self.lbl_quiz_title.setText(f"Conceito {self.current_concept_idx + 1} de {len(CONCEPTS)}: {c['title']}")
        self.txt_concept_answer.setHtml(f"<p>{c['answer']}</p>")

    def load_prev_concept(self):
        self.load_concept(self.current_concept_idx - 1)

    def load_next_concept(self):
        self.load_concept(self.current_concept_idx + 1)

    # 2. EXERCÍCIOS PRÁTICOS
    def create_exercises_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("<b>Catálogo de 10 Exercícios Práticos em Espaço Real (Seção 17 do Manual)</b>"))

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table_ex = QTableWidget(0, 3)
        self.table_ex.setHorizontalHeaderLabels(["Nº", "Título do Exercício", "Nível"])
        self.table_ex.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_ex.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_ex.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_ex.verticalHeader().setVisible(False)
        self.table_ex.currentCellChanged.connect(self.on_exercise_selected)
        splitter.addWidget(self.table_ex)

        # Painel de Detalhes
        det_widget = QWidget()
        det_layout = QVBoxLayout(det_widget)
        self.lbl_ex_title = QLabel("Selecione um exercício ao lado")
        self.lbl_ex_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        det_layout.addWidget(self.lbl_ex_title)

        self.txt_ex_desc = QTextEdit()
        self.txt_ex_desc.setReadOnly(True)
        det_layout.addWidget(self.txt_ex_desc)
        splitter.addWidget(det_widget)

        splitter.setSizes([350, 450])
        layout.addWidget(splitter)

        self.populate_exercises()
        return w

    def populate_exercises(self):
        self.table_ex.setRowCount(len(EXERCISES))
        for row, ex in enumerate(EXERCISES):
            self.table_ex.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.table_ex.setItem(row, 1, QTableWidgetItem(ex.get("title", "")))
            
            diff = ex.get("level", "Iniciante")
            it_diff = QTableWidgetItem(diff)
            if diff == "Iniciante": it_diff.setForeground(QColor("#7ee787"))
            elif diff == "Intermediário": it_diff.setForeground(QColor("#e3b341"))
            else: it_diff.setForeground(QColor("#f85149"))
            self.table_ex.setItem(row, 2, it_diff)

    def on_exercise_selected(self, currentRow, currentColumn, previousRow, previousColumn):
        if currentRow < 0 or currentRow >= len(EXERCISES):
            return
        ex = EXERCISES[currentRow]
        self.lbl_ex_title.setText(f"Exercício {currentRow + 1}: {ex.get('title')} ({ex.get('level')})")
        
        steps_html = "<ol>"
        for s in ex.get("steps", []):
            steps_html += f"<li>{s}</li>"
        steps_html += "</ol>"

        body = (
            f"<b>OBJETIVO:</b><br>{ex.get('objective')}<br><br>"
            f"<b>POR QUE FAZER:</b><br>{ex.get('why')}<br><br>"
            f"<b>PASSO A PASSO / PROCEDIMENTO:</b><br>{steps_html}"
            f"<b>CRITÉRIO DE SUCESSO:</b><br>{ex.get('success')}"
        )
        self.txt_ex_desc.setHtml(body)

    # 3. AAR (AFTER ACTION REVIEW)
    def create_aar_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        top_info = QLabel(
            "<b>After Action Review Baseado em Fatos (Seção 18 do Manual)</b><br>"
            "<i>Regra do Manual: O Copilot analisa estritamente o dano real recebido e infligido, tipo de arma e módulos. Não inventa desculpas nem atribui azar.</i>"
        )
        top_info.setWordWrap(True)
        layout.addWidget(top_info)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Entrada de Dados
        in_widget = QWidget()
        in_layout = QVBoxLayout(in_widget)
        in_layout.addWidget(QLabel("Nave Pilotada:"))
        self.combo_aar_myship = QComboBox()
        self.combo_aar_myship.addItems(["Tormentor", "Executioner", "Punisher", "Crucifier", "Coercer", "Kestrel", "Tristan", "Rifter", "Incursus", "Breacher"])
        in_layout.addWidget(self.combo_aar_myship)

        in_layout.addWidget(QLabel("Nave Inimiga:"))
        self.combo_aar_enemy = QComboBox()
        self.combo_aar_enemy.addItems(["Kestrel", "Tristan", "Breacher", "Incursus", "Rifter", "Executioner", "Tormentor", "Hookbill", "Comet", "Firetail", "Slicer"])
        in_layout.addWidget(self.combo_aar_enemy)

        in_layout.addWidget(QLabel("Resultado:"))
        self.combo_aar_res = QComboBox()
        self.combo_aar_res.addItems(["loss", "kill"])
        in_layout.addWidget(self.combo_aar_res)

        in_layout.addWidget(QLabel("Cole os logs do combate ou texto da Killmail:"))
        self.txt_aar_logs = QTextEdit()
        self.txt_aar_logs.setPlaceholderText("Cole linhas do log de combate ou texto do zKillboard:\n02:14:05 Scourge Rocket hits you for 142 damage\n02:14:09 Warp Scrambler II applied\n...")
        in_layout.addWidget(self.txt_aar_logs, 1)

        btn_run_aar = QPushButton("🔍 Gerar Análise de AAR")
        btn_run_aar.setStyleSheet("background-color: #1f6feb; color: white; font-weight: bold; padding: 8px;")
        btn_run_aar.clicked.connect(self.generate_aar)
        in_layout.addWidget(btn_run_aar)
        splitter.addWidget(in_widget)

        # Saída do AAR
        out_widget = QWidget()
        out_layout = QVBoxLayout(out_widget)
        out_layout.addWidget(QLabel("<b>Relatório Pós-Combate (AAR):</b>"))
        self.txt_aar_report = QTextEdit()
        self.txt_aar_report.setReadOnly(True)
        out_layout.addWidget(self.txt_aar_report, 1)
        splitter.addWidget(out_widget)

        splitter.setSizes([350, 450])
        layout.addWidget(splitter)
        return w

    def generate_aar(self):
        my_ship = self.combo_aar_myship.currentText()
        enemy_ship = self.combo_aar_enemy.currentText()
        res = self.combo_aar_res.currentText()
        logs = self.txt_aar_logs.toPlainText().splitlines()

        data = {
            "my_ship": my_ship,
            "enemy_ship": enemy_ship,
            "outcome": res,
            "notes": " ".join(logs)
        }

        report = after_action_review(data)
        self.history.add(report)

        evid = report.get("evidencias", {})
        interp = report.get("interpretacao", [])
        
        html = f"""
        <h3 style="color: {'#f85149' if res == 'loss' else '#7ee787'};">Resultado: {res.upper()} ({my_ship} vs {enemy_ship})</h3>
        <p><b>Resumo:</b> {report.get('resumo', '')}</p>
        <hr>
        <h4>Evidências Físicas Registradas:</h4>
        <ul>
        """
        for k, v in evid.items():
            html += f"<li><b>{k}:</b> {v}</li>"
        html += "</ul><h4>Interpretação e Fatores Críticos:</h4><ul>"
        for i in interp:
            html += f"<li>{i}</li>"
        html += "</ul>"

        ex_sug = report.get("exercicio_sugerido")
        if ex_sug:
            html += f"<div style='background: #161b22; padding: 10px; border-radius: 4px; border-left: 4px solid #58a6ff;'>"
            html += f"<b>EXERCÍCIO RECOMENDADO:</b> {ex_sug.get('title')} - <i>{ex_sug.get('why')}</i></div>"

        self.txt_aar_report.setHtml(html)
        self.update_history_tab_view()

    # 4. HISTÓRICO E PADRÕES
    def create_history_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        layout.addWidget(QLabel("<b>Detecção de Padrões de Morte do Piloto (Seção 19 do Manual)</b>"))
        self.lbl_history_summary = QLabel("Nenhum histórico registrado nesta sessão.")
        self.lbl_history_summary.setWordWrap(True)
        self.lbl_history_summary.setStyleSheet("background: #161b22; padding: 10px; border-radius: 4px;")
        layout.addWidget(self.lbl_history_summary)

        self.table_history = QTableWidget(0, 4)
        self.table_history.setHorizontalHeaderLabels(["Data / Hora", "Minha Nave", "Inimigo", "Resultado"])
        self.table_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_history.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table_history.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table_history.verticalHeader().setVisible(False)
        layout.addWidget(self.table_history, 1)

        self.update_history_tab_view()
        return w

    def update_history_tab_view(self):
        if not hasattr(self, 'table_history'):
            return
        records = self.history.records
        self.table_history.setRowCount(len(records))

        for row, r in enumerate(reversed(records)):
            self.table_history.setItem(row, 0, QTableWidgetItem(r.get("timestamp", "")))
            self.table_history.setItem(row, 1, QTableWidgetItem(r.get("my_ship", "")))
            self.table_history.setItem(row, 2, QTableWidgetItem(r.get("enemy_ship", "")))
            
            res = r.get("outcome", "")
            it_res = QTableWidgetItem(res.upper())
            it_res.setForeground(QColor("#f85149" if res == "loss" else "#7ee787"))
            self.table_history.setItem(row, 3, it_res)

        patterns = self.history.patterns()
        if patterns:
            txt = "<b>Padrões Identificados nas Derrotas:</b><br>" + "<br>".join([f"• {p.get('tag')}: {p.get('diagnostico', '')}" for p in patterns])
            self.lbl_history_summary.setText(txt)
            self.lbl_history_summary.setStyleSheet("background: #2b1111; color: #f85149; padding: 10px; border-radius: 4px; border: 1px solid #da3633;")
        else:
            self.lbl_history_summary.setText("Nenhum padrão crítico de repetição de erros detectado até o momento.")
            self.lbl_history_summary.setStyleSheet("background: #161b22; color: #8b949e; padding: 10px; border-radius: 4px;")
