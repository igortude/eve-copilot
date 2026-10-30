# -*- coding: utf-8 -*-
"""
EVE Online Instant Target Scanner (Clipboard / Overview Listener)
Captura cliques copiados da Overview do EVE Online e dispara análise instantânea.
Suporta polling contínuo (essencial para compositores Wayland), detecção de fittings EFT do piloto
e parsing de colunas tabuladas da Overview.
"""

import re
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QGuiApplication
from core.database import analyze_target_text

class TargetScanner(QObject):
    target_detected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.last_text = ""
        self.clipboard = QGuiApplication.clipboard()
        if self.clipboard:
            self.clipboard.dataChanged.connect(self._check_clipboard)

        # Polling periódico essencial no Wayland para quando a janela está sem foco
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_clipboard)
        self.timer.start(400)

    def _check_clipboard(self):
        if not self.clipboard:
            return
        try:
            text = self.clipboard.text().strip()
        except Exception:
            return

        if not text or text == self.last_text or len(text) > 4000:
            return

        self.last_text = text

        # 1. Verifica se é um Fitting de nave do jogador (formato EFT: [NomeDaNave, NomeDoFit])
        if text.startswith("[") and "]" in text and "\n" in text:
            first_line = text.splitlines()[0].strip("[]")
            ship_name = first_line.split(",")[0].strip() if "," in first_line else first_line
            fit_name = first_line.split(",")[1].strip() if "," in first_line else "Fit Ativo"
            self.target_detected.emit({
                "raw_text": f"{ship_name} [{fit_name}]",
                "is_fitting": True,
                "ship_name": ship_name,
                "fit_name": fit_name,
                "fit_text": text,
                "distance": "—",
                "ship_type": "Nave do Piloto",
                "velocity": "—",
                "radial": "—",
                "faction": None,
                "ship_size": ship_name
            })
            return

        # 1b. Verifica se é cópia de inventário / carga / loot do EVE (múltiplas linhas com tabulação ou quantidades)
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if len(lines) >= 2:
            is_inv = False
            first_parts = lines[0].split('\t')
            if len(first_parts) >= 2:
                col0 = first_parts[0].lower()
                if not (col0.endswith("km") or col0.endswith(" m") or col0.endswith("au") or col0 == "—"):
                    is_inv = True
            elif any(re.search(r'^\d+\s*x\s+|\s+x\s*\d+$', l, re.I) for l in lines[:3]):
                is_inv = True

            if is_inv:
                self.target_detected.emit({
                    "type": "loot_triage",
                    "loot_text": text,
                })
                return

        # 2. Verifica se o texto é uma linha tabulada da Overview do EVE:
        # Ex: "12 km\tCaldari Navy Griffin\tFrigate\t1,200 m/s\t140 m/s"
        lines = text.splitlines()
        for line in lines:
            parts = [p.strip() for p in line.split('\t') if p.strip()]
            if len(parts) >= 3:
                dist = parts[0] if ("km" in parts[0] or "m" in parts[0]) else "—"
                name = parts[1] if len(parts) > 1 else parts[0]
                stype = parts[2] if len(parts) > 2 else "Ship"
                vel = parts[3] if len(parts) > 3 else "0 m/s"
                radial = parts[4] if len(parts) > 4 else "0 m/s"
                
                faction_data, ship_size = analyze_target_text(f"{name} {stype}")
                self.target_detected.emit({
                    "raw_text": name,
                    "distance": dist,
                    "ship_type": stype,
                    "velocity": vel,
                    "radial": radial,
                    "faction": faction_data,
                    "ship_size": ship_size or stype
                })
                return

        # 3. Texto simples de alvo copiado do jogo
        faction_data, ship_size = analyze_target_text(text)
        self.target_detected.emit({
            "raw_text": text,
            "distance": "—",
            "ship_type": ship_size or "Hostile",
            "velocity": "—",
            "radial": "—",
            "faction": faction_data,
            "ship_size": ship_size
        })
