"""
core/tactical_ui/ships_widget.py - Gerenciador de Naves do Piloto.
Atende rigorosamente às Seções 2 e 3 do Manual:
- Importação de EFT sem inventar dados.
- Validação explícita de atributos e slots (CPU/PG pendentes sem SDE/ESI).
- Recálculo dinâmico de alcance ótimo e falloff com base em munição/tackle.
- Suporte a salvar/selecionar nave ativa.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTextEdit, QComboBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from core.tactical.ships import (
    ShipManager, parse_eft, validate_fitting, template_for, recommended_range_m
)
from core.tactical import UNKNOWN, PENDING

class ShipManagerWidget(QWidget):
    fit_changed = pyqtSignal(dict)

    def __init__(self, ship_mgr: ShipManager = None, parent=None):
        super().__init__(parent)
        self.ship_mgr = ship_mgr or ShipManager()
        names = self.ship_mgr.names()
        initial_name = names[0] if names else "Tormentor"
        self.current_profile = self.ship_mgr.get(initial_name) or template_for(initial_name)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header / Seletor de Fitting
        top_bar = QHBoxLayout()
        lbl_sel = QLabel("NAVE / FITTING ATIVO:")
        lbl_sel.setStyleSheet("font-weight: bold; color: #58a6ff;")
        top_bar.addWidget(lbl_sel)

        self.combo_fits = QComboBox()
        self.combo_fits.currentIndexChanged.connect(self.on_fit_selected)
        top_bar.addWidget(self.combo_fits, 1)

        self.btn_set_active = QPushButton("Definir como Principal")
        self.btn_set_active.setStyleSheet("background-color: #238636; color: white; font-weight: bold; padding: 5px 12px; border-radius: 4px;")
        self.btn_set_active.clicked.connect(self.set_active_fit)
        top_bar.addWidget(self.btn_set_active)

        self.btn_delete_fit = QPushButton("Excluir")
        self.btn_delete_fit.setStyleSheet("background-color: #da3633; color: white; padding: 5px 12px; border-radius: 4px;")
        self.btn_delete_fit.clicked.connect(self.delete_current_fit)
        top_bar.addWidget(self.btn_delete_fit)

        layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Painel Esquerdo: EFT Import & Status de Validação
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        left_layout.addWidget(QLabel("<b>Importador EFT (Cole aqui o fitting do Pyfa ou EVE):</b>"))
        self.txt_eft = QTextEdit()
        self.txt_eft.setPlaceholderText("[Tormentor, Tormentor FW Solo]\nSmall Armor Repairer II\nDamage Control II\n...\nSmall Focused Pulse Laser II, Scorch S")
        left_layout.addWidget(self.txt_eft, 1)

        btn_parse = QPushButton("📥 Importar e Validar Fitting EFT")
        btn_parse.setStyleSheet("background-color: #1f6feb; color: white; font-weight: bold; padding: 6px;")
        btn_parse.clicked.connect(self.parse_and_save_eft)
        left_layout.addWidget(btn_parse)

        # Box de Validação e Pendências
        self.box_validation = QGroupBox("Status de Validação & Integridade (Regra CCP)")
        val_layout = QVBoxLayout(self.box_validation)
        self.lbl_validation_status = QLabel("Nenhum fitting carregado.")
        self.lbl_validation_status.setWordWrap(True)
        val_layout.addWidget(self.lbl_validation_status)
        left_layout.addWidget(self.box_validation)

        splitter.addWidget(left_widget)

        # Painel Direito: Atributos Calculados e Slots
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        # Resumo de Atributos
        attr_group = QGroupBox("Atributos Táticos da Nave")
        attr_layout = QVBoxLayout(attr_group)

        self.table_attr = QTableWidget(7, 2)
        self.table_attr.setHorizontalHeaderLabels(["Parâmetro", "Valor Atual"])
        self.table_attr.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_attr.verticalHeader().setVisible(False)
        self.table_attr.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        attr_layout.addWidget(self.table_attr)
        right_layout.addWidget(attr_group)

        # Módulos Equipados
        mod_group = QGroupBox("Módulos Equipados por Slot")
        mod_layout = QVBoxLayout(mod_group)
        self.table_mods = QTableWidget(0, 2)
        self.table_mods.setHorizontalHeaderLabels(["Slot", "Módulo / Carga"])
        self.table_mods.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_mods.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_mods.verticalHeader().setVisible(False)
        mod_layout.addWidget(self.table_mods)
        right_layout.addWidget(mod_group)

        splitter.addWidget(right_widget)
        splitter.setSizes([350, 450])
        layout.addWidget(splitter, 1)

        self.refresh_fits_combo()
        self.display_profile(self.current_profile)

    def refresh_fits_combo(self):
        self.combo_fits.blockSignals(True)
        self.combo_fits.clear()
        names = self.ship_mgr.names()
        cur_ship_name = self.current_profile.get("ship", "")

        idx_to_select = 0
        for i, name in enumerate(names):
            label = name
            if name == cur_ship_name:
                idx_to_select = i
            self.combo_fits.addItem(label, name)

        if names:
            self.combo_fits.setCurrentIndex(idx_to_select)
        self.combo_fits.blockSignals(False)

    def on_fit_selected(self, index):
        if index < 0:
            return
        ship_name = self.combo_fits.itemData(index)
        prof = self.ship_mgr.get(ship_name)
        if prof:
            self.current_profile = prof
            self.display_profile(prof)

    def set_active_fit(self):
        if not self.current_profile:
            return
        self.fit_changed.emit(self.current_profile)
        name = self.current_profile.get("ship", "Nave")
        QMessageBox.information(self, "Fitting Ativo", f"'{name}' foi definido como o fitting principal de combate!")

    def delete_current_fit(self):
        if not self.current_profile:
            return
        name = self.current_profile.get("ship", "")
        if not name:
            return
        confirm = QMessageBox.question(
            self, "Confirmar Exclusão",
            f"Deseja excluir a nave '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.ship_mgr.remove(name)
            self.refresh_fits_combo()
            names = self.ship_mgr.names()
            first = names[0] if names else "Tormentor"
            self.current_profile = self.ship_mgr.get(first) or template_for(first)
            self.display_profile(self.current_profile)

    def parse_and_save_eft(self):
        text = self.txt_eft.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Aviso", "Por favor cole o bloco de texto no formato EFT.")
            return

        parsed, prof = self.ship_mgr.import_eft(text)
        if not parsed.get("ok"):
            errs = "<br>".join(parsed.get("errors", ["Erro desconhecido"]))
            QMessageBox.critical(self, "Erro de Importação", f"Falha ao interpretar EFT:<br>{errs}")
            return

        self.current_profile = prof
        self.refresh_fits_combo()
        self.display_profile(prof, parsed)
        self.fit_changed.emit(prof)
        QMessageBox.information(self, "Importação Concluída", f"Fitting '{prof.get('ship')}' importado e validado!")

    def display_profile(self, prof: dict, parsed: dict | None = None):
        if not prof:
            return

        ship_name = prof.get("ship", "Desconhecido")
        ws = prof.get("weapon_stats", {})
        optimal = ws.get("optimal_m")
        falloff = ws.get("falloff_m")
        tracking = ws.get("tracking_rad_s")
        speed = prof.get("speed_profile", {}).get("max_speed_ms")
        ammo = prof.get("loaded_ammo") or (prof.get("ammo_choices", [""])[0] if prof.get("ammo_choices") else None)

        rec_range = recommended_range_m(prof)
        range_val = rec_range.get("value")
        range_str = f"{range_val} m ({rec_range.get('source')})" if range_val else PENDING

        attr_data = [
            ("Casco / Tipo", ship_name),
            ("Velocidade Máx.", f"{speed} m/s" if speed else PENDING),
            ("Armamento", prof.get("weapon_type") or UNKNOWN),
            ("Munição Carregada", ammo or UNKNOWN),
            ("Alcance Ótimo (Optimal)", f"{optimal} m" if optimal else PENDING),
            ("Falloff", f"{falloff} m" if falloff else PENDING),
            ("Tracking Speed", f"{tracking} rad/s" if tracking else PENDING),
        ]

        for row, (k, v) in enumerate(attr_data):
            it_k = QTableWidgetItem(k)
            it_k.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            it_v = QTableWidgetItem(str(v))
            if str(v) in (PENDING, UNKNOWN):
                it_v.setForeground(QColor("#d29922"))
            else:
                it_v.setForeground(QColor("#58a6ff"))
            self.table_attr.setItem(row, 0, it_k)
            self.table_attr.setItem(row, 1, it_v)

        # Módulos
        mods = []
        if parsed and "slots" in parsed:
            for s in ("high", "mid", "low", "rig"):
                for m in parsed["slots"].get(s, []):
                    mods.append((s.capitalize(), m.get("name", "")))
            for d in parsed.get("drones", []):
                mods.append(("Drone", f"{d.get('name')} x{d.get('qty', 1)}"))
        else:
            slots_cfg = prof.get("slots", {})
            for s in ("high", "mid", "low", "rigs"):
                qty = slots_cfg.get(s, 0)
                mods.append((s.capitalize(), f"{qty} slots configurados"))

        self.table_mods.setRowCount(len(mods))
        for row, (slot, name) in enumerate(mods):
            it_slot = QTableWidgetItem(slot)
            if slot == "High": it_slot.setForeground(QColor("#f85149"))
            elif slot == "Mid": it_slot.setForeground(QColor("#58a6ff"))
            elif slot == "Low": it_slot.setForeground(QColor("#e3b341"))
            elif slot == "Rig" or slot == "Rigs": it_slot.setForeground(QColor("#a371f7"))
            else: it_slot.setForeground(QColor("#7ee787"))

            self.table_mods.setItem(row, 0, it_slot)
            self.table_mods.setItem(row, 1, QTableWidgetItem(name))

        # Status de Validação
        if parsed and "validation" in parsed:
            v_info = parsed["validation"]
            val_text = f"<b>Status:</b> {'⚠️ CONTÉM PENDÊNCIAS' if v_info.get('pending') else '✅ COMPLETO'}<br>"
            if v_info.get("pending"):
                val_text += "<br>".join([f"• {p}" for p in v_info["pending"]])
            if v_info.get("warnings"):
                val_text += "<br>" + "<br>".join([f"• {w}" for w in v_info["warnings"]])
            self.lbl_validation_status.setText(val_text)
            self.box_validation.setStyleSheet("QGroupBox { border: 1px solid #d29922; color: #d29922; }")
        else:
            self.lbl_validation_status.setText(
                "Nave carregada do perfil de combate.<br>"
                "• CPU/PG e calibração mantidos como PENDENTE conforme regra do manual."
            )
            self.box_validation.setStyleSheet("QGroupBox { border: 1px solid #58a6ff; color: #58a6ff; }")
