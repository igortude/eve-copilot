# -*- coding: utf-8 -*-
"""
EVE Online Tactical Loot & Cargo Evaluator (Triagem Inteligente de Loot)
Classifica inventário e cargas coletadas em 4 categorias de decisão rápida:
1. 🟢 USAR NA NAVE: Munições compatíveis, drones e módulos táticos de combate
2. 💰 VENDER (JITA/HUB): Faction drops, Deadspace, Officer, Bounties, Overseer Tags e T2 valioso
3. 📦 GUARDAR NO HANGAR: Materiais de Salvage, Minerais, Blueprints, Datacores e Indústria
4. ⚪ REPROCESSAR / DESCARTAR: Metal Scraps, módulos civis e itens de baixo valor comercial

Integrado com a ESI da CCP Games para estimativa de valor em ISK e síntese de voz (Aura/Jarvis).
"""

import os
import re
import time
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

import requests
from core.market_checker import resolve_type_ids, _clean_item_line, session

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PRICES_CACHE_FILE = os.path.join(DATA_DIR, "global_prices.json")

# ---------------------------------------------------------------------------
# BASE DE REGRAS HEURÍSTICAS DE TRIAGEM DE EVE ONLINE
# ---------------------------------------------------------------------------

# MUNIÇÕES E CARGAS ÚTEIS DE COMBATE
AMMO_PATTERNS = [
    # Mísseis & Torpedos
    r"\b(missile|rocket|torpedo)\b",
    r"\b(scourge|inferno|mjolnir|nova)\b",
    r"\b(auto-targeting|light missile|heavy missile|cruise missile)\b",
    # Cargas Híbridas (Blasters / Railguns)
    r"\b(antimatter|plutonium|uranium|thorium|lead|iridium|iron|tungsten)\b",
    r"\b(void|null|javelin|spike)\b",
    # Projéteis (Autocannons / Artilharia)
    r"\b(emp|fusion|phased plasma|proton|nuclear|titanium sabot|depleted uranium|carbonized lead)\b",
    r"\b(barrage|hail|tremor|quake)\b",
    # Cristais e Lentes de Laser
    r"\b(multifrequency|standard|radio|microwave|infrared|gamma|xray|ultraviolet)\b",
    r"\b(scorch|conflagration|aurora|gleam)\b",
    # Triglavian
    r"\b(exotic plasma|meson|tetryon|baryon|occult|mystic)\b",
    # Consumíveis de capacitor e reparo
    r"\bcap booster (150|200|400|800|3200)\b",
    r"\bnanite repair paste\b",
    r"\bliquid ozone\b",
    r"\bstrontium clathrates\b",
]

# DRONES DE COMBATE E SUPORTE
DRONE_NAMES = [
    "hobgoblin", "hammerhead", "ogre",
    "hornet", "vespa", "wasp",
    "acolyte", "infiltrator", "praetor",
    "warrior", "valkyrie", "berserker",
    "salvage drone", "salvaging drone",
    "armor maintenance bot", "shield maintenance bot",
    "infiltrator", "curator", "garde", "warden", "bouncer"
]

# MÓDULOS DE COMBATE ESSENCIAIS (USAR NA NAVE)
COMBAT_MODULE_PATTERNS = [
    r"\b(afterburner|microwarpdrive)\b",
    r"\b(damage control)\b",
    r"\b(shield booster|shield extender)\b",
    r"\b(armor repairer|armor plate|reinforced bulkheads)\b",
    r"\b(multispectrum shield hardener|armor hardener)\b",
    r"\b(capacitor booster|cap battery)\b",
    r"\b(stasis webifier|warp scrambler|warp disruptor)\b",
    r"\b(ballistic control system|gyrostabilizer|magnetic field stabilizer|heat sink)\b",
    r"\b(drone damage amplifier|omnidirectional tracking)\b",
    r"\b(tracking computer|target painter)\b",
    r"\b(expanded probe launcher|core probe launcher)\b",
    r"\b(data analyzer|relic analyzer)\b",
]

# FACTION & DEADSPACE / OFFICER (VENDER IMEDIATAMENTE POR BOM ISK)
FACTION_OFFICER_PATTERNS = [
    r"\b(caldari navy|federation navy|republic fleet|imperial navy)\b",
    r"\b(dread guristas|shadow serpentis|true sansha|dark blood|domination)\b",
    r"\b(pith|gist|core|corpii|centus|centum)\b",
    r"\b(a-type|b-type|c-type|x-type)\b",
    r"\b(sisters of eve|syndicate|ore|thukker)\b",
    r"\b(overseer's personal effects)\b",
    r"\b(insignia|dogtag|sleeper components|encrypted data)\b",
    r"\b(blue loot)\b",
]

# MATERIAIS DE SALVAGE & EXPLORAÇÃO & INDÚSTRIA (GUARDAR NO HANGAR)
SALVAGE_INDUSTRY_PATTERNS = [
    # Salvage components
    r"\b(armor plates|logic circuits|power circuits|burned logic circuit)\b",
    r"\b(alloyed tritanium bar|charred micro circuit|contaminated lore)\b",
    r"\b(fried interface circuit|malfunctioning drone transceiver)\b",
    r"\b(smashed trigger unit|damaged artificial neural network)\b",
    r"\b(warded drone net|tripped power circuit|tangled power conduit)\b",
    r"\b(nanite internal circuitry|defective current pump)\b",
    # Blueprints
    r"\b(blueprint|bpc|bpo)\b",
    # Datacores & Decryptors
    r"\b(datacore|decryptor)\b",
    # Minerais
    r"\b(tritanium|pyerite|mexallon|isogen|nocxium|zydrine|megacyte|morphite)\b",
    # Gas / PI
    r"\b(condensate|fullerite|bacteria|proteins|coolant)\b",
]

# LIXO / REPROCESSAR
TRASH_PATTERNS = [
    r"\b(metal scraps|scrap metal)\b",
    r"\bcivilian\b",
    r"\b(carbon|garbage|rubbish)\b",
]


@dataclass
class LootItem:
    name: str
    quantity: int = 1
    group: str = "Geral"
    volume_m3: float = 0.0
    action: str = "SELL_JITA"  # USE_SHIP, SELL_JITA, HOARD_HANGAR, REPROCESS_TRASH
    action_label: str = "💰 VENDER (JITA)"
    badge_color: str = "#ffd43b"
    reason: str = "Valor comercial de mercado."
    unit_price: float = 0.0
    total_price: float = 0.0
    is_valuable: bool = False

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "group": self.group,
            "volume_m3": round(self.volume_m3, 2),
            "action": self.action,
            "action_label": self.action_label,
            "badge_color": self.badge_color,
            "reason": self.reason,
            "unit_price": self.unit_price,
            "total_price": self.total_price,
            "is_valuable": self.is_valuable,
        }


@dataclass
class LootTriageReport:
    items: List[LootItem] = field(default_factory=list)
    total_isk: float = 0.0
    total_volume_m3: float = 0.0
    use_count: int = 0
    sell_count: int = 0
    hoard_count: int = 0
    reprocess_count: int = 0
    summary_speech: str = ""

    def to_dict(self) -> Dict:
        return {
            "items": [item.to_dict() for item in self.items],
            "total_isk": round(self.total_isk, 2),
            "total_volume_m3": round(self.total_volume_m3, 2),
            "use_count": self.use_count,
            "sell_count": self.sell_count,
            "hoard_count": self.hoard_count,
            "reprocess_count": self.reprocess_count,
            "summary_speech": self.summary_speech,
        }


class LootEvaluator:
    """Gerenciador inteligente de análise e precificação de loot/inventário."""

    def __init__(self):
        self._price_cache: Dict[int, float] = {}
        self._price_cache_timestamp: float = 0.0
        self._load_cached_prices()

    def _load_cached_prices(self):
        """Carrega preços globais em cache de disco se válidos (< 2 horas)."""
        if os.path.exists(PRICES_CACHE_FILE):
            try:
                mtime = os.path.getmtime(PRICES_CACHE_FILE)
                if time.time() - mtime < 7200:  # 2 horas de validade
                    with open(PRICES_CACHE_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        self._price_cache = {int(k): float(v) for k, v in data.items()}
                        self._price_cache_timestamp = mtime
            except Exception as e:
                print(f"[Aviso] Falha ao carregar cache de preços de loot: {e}")

    def _save_cached_prices(self):
        """Persiste cache de preços no disco."""
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PRICES_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._price_cache, f)
        except Exception as e:
            print(f"[Aviso] Falha ao salvar cache de preços de loot: {e}")

    def refresh_global_prices(self):
        """Busca a tabela de preços de mercado de todos os itens do EVE na ESI."""
        if time.time() - self._price_cache_timestamp < 3600 and self._price_cache:
            return  # Cache recente

        url = "https://esi.evetech.net/latest/markets/prices/"
        try:
            r = session.get(url, timeout=6.0)
            if r.status_code == 200:
                data = r.json()
                new_cache = {}
                for entry in data:
                    t_id = entry.get("type_id")
                    avg_p = entry.get("average_price") or entry.get("adjusted_price") or 0.0
                    if t_id and avg_p > 0:
                        new_cache[int(t_id)] = float(avg_p)
                if new_cache:
                    self._price_cache = new_cache
                    self._price_cache_timestamp = time.time()
                    self._save_cached_prices()
        except Exception as e:
            print(f"[Aviso] Falha ao atualizar preços globais da ESI: {e}")

    def classify_item(self, name: str, quantity: int, group: str = "", unit_price: float = 0.0) -> Tuple[str, str, str, str]:
        """
        Retorna (action, action_label, badge_color, reason).
        Actions:
        - USE_SHIP
        - SELL_JITA
        - HOARD_HANGAR
        - REPROCESS_TRASH
        """
        n_lower = name.lower().strip()
        g_lower = group.lower().strip()

        # 1. Checa Lixo evidente
        for pat in TRASH_PATTERNS:
            if re.search(pat, n_lower) or re.search(pat, g_lower):
                return (
                    "REPROCESS_TRASH",
                    "⚪ REPROCESSAR / DESCARTAR",
                    "#868e96",
                    "Lixo de destroço ou item civil sem valor. Reprocesse para obter minérios ou jogue fora."
                )

        # 2. Checa Faction / Deadspace / Overseer / Blue Loot (SEMPRE VENDER)
        for pat in FACTION_OFFICER_PATTERNS:
            if re.search(pat, n_lower) or re.search(pat, g_lower):
                return (
                    "SELL_JITA",
                    "💰 VENDER (JITA/HUB)",
                    "#ffd43b",
                    "Item Raro / Facção / Deadspace de alto valor em ISK. Venda no mercado para lucro máximo."
                )

        # 3. Checa Munição de Combate & Consumíveis (USAR NA NAVE)
        for pat in AMMO_PATTERNS:
            if re.search(pat, n_lower) or "charge" in g_lower or "missile" in g_lower:
                return (
                    "USE_SHIP",
                    "🟢 USAR NA NAVE",
                    "#00e5ff",
                    "Munição tática ou consumível de bordo para reabastecer sua nave em combate."
                )

        # 4. Checa Drones de Combate e Suporte (USAR NA NAVE)
        for d in DRONE_NAMES:
            if d in n_lower or "drone" in g_lower:
                return (
                    "USE_SHIP",
                    "🟢 USAR NA NAVE",
                    "#00e5ff",
                    "Drone de combate / suporte. Guarde no Drone Bay da sua nave para uso operacional."
                )

        # 5. Checa Materiais de Salvage, Minerais e Blueprints (GUARDAR NO HANGAR)
        for pat in SALVAGE_INDUSTRY_PATTERNS:
            if re.search(pat, n_lower) or "salvaged" in g_lower or "mineral" in g_lower or "blueprint" in g_lower:
                return (
                    "HOARD_HANGAR",
                    "📦 GUARDAR NO HANGAR",
                    "#74c0fc",
                    "Material nobre de fabricação de Rigs, minério ou projeto industrial. Guarde no seu Hangar."
                )

        # 6. Módulos de Combate Essenciais (USAR NA NAVE se for módulo tático)
        for pat in COMBAT_MODULE_PATTERNS:
            if re.search(pat, n_lower):
                # Se for módulo meta caro (> 3M), pode ser interessante vender se já tiver
                if unit_price > 5000000:
                    return (
                        "SELL_JITA",
                        "💰 VENDER (JITA/HUB)",
                        "#ffd43b",
                        "Módulo de alto valor comercial. Se não precisar equipar agora, venda no mercado."
                    )
                return (
                    "USE_SHIP",
                    "🟢 USAR NA NAVE",
                    "#00e5ff",
                    "Módulo essencial de tanque, propulsão ou combate tático para equipar na sua nave."
                )

        # 7. Regra por Valor Comercial
        total_val = unit_price * quantity
        if total_val >= 500000 or unit_price >= 200000:
            return (
                "SELL_JITA",
                "💰 VENDER (JITA/HUB)",
                "#ffd43b",
                "Bom valor comercial no mercado. Leve para Jita ou Trade Hub para conversão rápida em ISK."
            )
        elif total_val < 30000 and quantity <= 5:
            return (
                "REPROCESS_TRASH",
                "⚪ REPROCESSAR / DESCARTAR",
                "#868e96",
                "Item de baixo valor e pouca liquidez. Reprocesse na estação para recuperar minerais."
            )

        # Padrão: Venda
        return (
            "SELL_JITA",
            "💰 VENDER (JITA/HUB)",
            "#ffd43b",
            "Loot comercial padrão para venda em estação de mercado."
        )

    def parse_inventory_clipboard(self, raw_text: str) -> List[Tuple[str, int, str, float]]:
        """
        Interpreta linhas copiadas do inventário do EVE (Ctrl+C em Cargo/Hangar/Wreck)
        Formatos suportados:
        - Tabulado: 'Scourge Heavy Missile\t1,500\tHeavy Missile\t1.88 m3\t...'
        - Multiplicadores: '10x Nanite Repair Paste', 'Armor Plates x8'
        - Simples: 'Damage Control II'
        """
        items = []
        for line in raw_text.splitlines():
            clean = line.strip()
            if not clean or clean.startswith("["):
                continue

            # Caso 1: Tabela tabulada do EVE Online (a mais rica e comum!)
            if "\t" in clean:
                cols = [c.strip() for c in clean.split("\t") if c.strip()]
                name = cols[0]
                qty = 1
                group = "Item"
                vol = 0.0

                # Quantidade normalmente na coluna 1 ou 2
                for c in cols[1:]:
                    val_str = c.replace(".", "").replace(",", "").strip()
                    if val_str.isdigit() and int(val_str) > 0 and qty == 1:
                        qty = int(val_str)
                    elif "m3" in c.lower() or "m³" in c.lower():
                        try:
                            v_clean = re.sub(r"[^\d.]", "", c.replace(",", "."))
                            vol = float(v_clean)
                        except Exception:
                            pass
                    elif len(c) > 2 and not c.replace(".", "").replace(",", "").isdigit() and group == "Item":
                        group = c

                if name and not name.lower().startswith(("slot", "subsystem")):
                    items.append((name, qty, group, vol))
                continue

            # Caso 2: Linha única com 'clean_item_line'
            name, qty = _clean_item_line(clean)
            if name:
                items.append((name, qty, "Geral", 0.0))

        return items

    def evaluate_text(self, text: str) -> LootTriageReport:
        """Processa o texto completo de loot/inventário e devolve o relatório de triagem."""
        parsed = self.parse_inventory_clipboard(text)
        if not parsed:
            return LootTriageReport()

        # Atualiza preços da ESI se necessário
        self.refresh_global_prices()

        # Resolve nomes para type_ids
        names = list(set([item[0] for item in parsed]))
        name_to_tid = resolve_type_ids(names)

        evaluated_items = []
        total_isk = 0.0
        total_vol = 0.0
        counts = {"USE_SHIP": 0, "SELL_JITA": 0, "HOARD_HANGAR": 0, "REPROCESS_TRASH": 0}

        for name, qty, group, vol in parsed:
            tid = name_to_tid.get(name)
            unit_price = self._price_cache.get(tid, 0.0) if tid else 0.0
            total_price = unit_price * qty
            total_isk += total_price
            total_vol += vol

            action, label, color, reason = self.classify_item(name, qty, group, unit_price)
            counts[action] = counts.get(action, 0) + 1

            is_valuable = (total_price >= 5000000 or "facção" in reason.lower() or "deadspace" in reason.lower())

            evaluated_items.append(LootItem(
                name=name,
                quantity=qty,
                group=group,
                volume_m3=vol,
                action=action,
                action_label=label,
                badge_color=color,
                reason=reason,
                unit_price=unit_price,
                total_price=total_price,
                is_valuable=is_valuable,
            ))

        # Ordena: Primeiro os de alto valor e itens de usar na nave
        evaluated_items.sort(key=lambda x: (
            0 if x.action == "USE_SHIP" else (1 if x.action == "SELL_JITA" else (2 if x.action == "HOARD_HANGAR" else 3)),
            -x.total_price
        ))

        # Monta resumo falado (TTS)
        speech_parts = []
        if counts["USE_SHIP"] > 0:
            speech_parts.append(f"{counts['USE_SHIP']} itens recomendados para usar na nave")
        if counts["SELL_JITA"] > 0:
            val_millions = round(total_isk / 1000000, 1)
            speech_parts.append(f"{counts['SELL_JITA']} itens para vender em Jita, totalizando {val_millions} milhões de ISK")
        if counts["HOARD_HANGAR"] > 0:
            speech_parts.append(f"{counts['HOARD_HANGAR']} materiais para guardar no hangar")

        if speech_parts:
            summary_speech = "Triagem de carga concluída: " + ", ".join(speech_parts) + "."
        else:
            summary_speech = "Nenhum item identificado para triagem."

        return LootTriageReport(
            items=evaluated_items,
            total_isk=total_isk,
            total_volume_m3=total_vol,
            use_count=counts["USE_SHIP"],
            sell_count=counts["SELL_JITA"],
            hoard_count=counts["HOARD_HANGAR"],
            reprocess_count=counts["REPROCESS_TRASH"],
            summary_speech=summary_speech,
        )
