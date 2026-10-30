# -*- coding: utf-8 -*-
"""
Ship Manager (manual, seções 3 e 4): múltiplas naves, importador EFT, validador de fitting
e perfil de combate editável.

Regra de ouro: NÃO inventar atributos. CPU, Powergrid, calibração e requisitos de habilidades
exigem dados do jogo (SDE/ESI) — enquanto não houver, a validação é marcada como PENDENTE.
"""
import copy
import re

from . import load_json, save_json, PENDING

SHIPS_FILE = "ships.json"

# --------------------------------------------------------------------------- #
# Classificação por palavras-chave (heurística transparente, editável aqui)
# --------------------------------------------------------------------------- #
_DRONE_RE = re.compile(
    r"\b(hobgoblin|hammerhead|ogre|praetor|acolyte|infiltrator|warrior|hornet|vespa|wasp|valkyrie|"
    r"berserker|curator|bouncer|garde|warden|gecko|light scout|medium scout|heavy attack|"
    r"scout drone|combat drone|sentry|augmented \w+|drone)\b", re.I)
_RIG_RE = re.compile(
    r"(locus coordinator|nano pump|reinforcer|anti-\w+ pump|auxiliary|trimark|semiconductor|"
    r"ionic field|egress|polycarbon|hybrid collision|burst aerator|core defense|"
    r"signal amplifier|\brig\b|processor overclocking|capacitor control circuit|"
    r"energy discharge elutriation|energy burst aerator|energy collision accelerator|"
    r"low friction nozzle|gravity capacitor|ancillary current router|warp core|"
    r"small \w+ (booster|reinforcer|pump|coordinator)|medium \w+ (booster|reinforcer|pump|coordinator))", re.I)
_CHARGE_RE = re.compile(
    r"(crystal|multifrequency|standard s|standard m|standard l|radio [sml]\b|microwave|infrared|ultraviolet|"
    r"gamma [sml]\b|xray|x-ray|scorch|conflagration|aurora|gleam|\bcharge\b|nanite repair paste|"
    r"capacitor booster \d|cap booster|missile|rocket|torpedo|antimatter|iridium|thorium|tungsten|lead\b|"
    r"plutonium|uranium|void|null [sml]\b|depleted|carbonized|proton|fusion|emp [sml]\b|phased plasma|"
    r"hail|barrage|tremor|quake|titanium sabot|scout drone|script|scan resolution)", re.I)

# (regex, papel, ativo?)  — ativo True/False; None = indefinido
_MODULE_RULES = [
    (r"warp scrambler", "tackle:scrambler", True),
    (r"warp disrupt", "tackle:disruptor", True),
    (r"stasis webifier|stasis web\b", "tackle:webifier", True),
    (r"afterburner", "propulsion:afterburner", True),
    (r"microwarpdrive|\bmwd\b", "propulsion:mwd", True),
    (r"ancillary armor repairer", "tank:ancillary_armor_repairer", True),
    (r"armor repairer|armor repair", "tank:armor_repairer", True),
    (r"shield booster", "tank:shield_booster", True),
    (r"ancillary shield booster", "tank:ancillary_shield_booster", True),
    (r"damage control", "tank:damage_control", True),
    (r"energy neutralizer|neutralizer", "ewar:neutralizer", True),
    (r"nosferatu|energy nosferatu", "ewar:nosferatu", True),
    (r"target painter|sensor damp|tracking disrupt|ecm|remote sensor|weapon disrupt", "ewar:other", True),
    (r"capacitor booster|cap booster", "cap:booster", True),
    (r"capacitor recharger|cap recharger", "cap:recharger", False),
    (r"(pulse|beam|laser).*(energy|laser)|energy (beam|pulse)|pulse laser|beam laser", "weapon:laser", True),
    (r"blaster|neutron|ion blaster|electron blaster", "weapon:blaster", True),
    (r"railgun|rail", "weapon:railgun", True),
    (r"autocannon", "weapon:autocannon", True),
    (r"artillery", "weapon:artillery", True),
    (r"launcher|missile bay", "weapon:missile", True),
    (r"heat sink|gyrostabilizer|magnetic field|ballistic control|tracking enhancer|tracking computer", "damage_mod", False),
    (r"armor hardener|hardener", "tank:hardener", True),
    (r"coating|plating|plate|membrane|energized|reinforced", "tank:armor_passive", False),
    (r"overdrive|nanofiber|inertial stabil", "speed_mod", False),
    (r"co-?processor|power diagnostic|reactor control|capacitor flux|cap power relay", "fitting_mod", False),
]

_SLOT_ORDER = ["low", "mid", "high", "rig", "subsystem"]

_EMPTY_SLOT_RE = re.compile(r"^\[empty (low|med|mid|high|rig|subsystem)[^\]]*\]$", re.I)

PENDING_VALIDATIONS = [
    "CPU", "Powergrid", "Calibração dos rigs", "Requisitos de habilidades",
]


def _classify_module(name: str):
    lname = name.lower()
    for pat, role, active in _MODULE_RULES:
        if re.search(pat, lname):
            return role, active
    return "unknown", None


def _split_charge(line: str):
    """'Módulo, Carga' -> (módulo, carga). Remove sufixo /OFFLINE."""
    offline = False
    if line.upper().endswith("/OFFLINE"):
        offline = True
        line = line[: -len("/OFFLINE")].strip()
    if "," in line:
        mod, charge = [p.strip() for p in line.split(",", 1)]
        return mod, charge, offline
    return line.strip(), None, offline


def _split_qty(line: str):
    m = re.match(r"^(.*?)\s+x\s*(\d+)$", line.strip(), re.I)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return line.strip(), 1


def parse_eft(text: str) -> dict:
    """
    Importa um fitting no formato EFT.
    Retorna dict com: ok, hull, name, slots{low,mid,high,rig,subsystem}, drones, cargo, charges,
    warnings, errors, derived (arma/tanque/propulsão/tackle) e validation.
    """
    result = {
        "ok": False, "hull": None, "name": None,
        "slots": {s: [] for s in _SLOT_ORDER},
        "drones": [], "cargo": [], "charges": [],
        "warnings": [], "errors": [], "derived": {}, "validation": {},
    }
    lines = [l.rstrip() for l in (text or "").replace("\r", "").split("\n")]
    # remove linhas vazias iniciais
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        result["errors"].append("Fitting vazio.")
        return result

    header = re.match(r"^\[\s*([^,\]]+?)\s*,\s*(.+?)\s*\]$", lines[0].strip())
    if not header:
        result["errors"].append("Cabeçalho EFT inválido. Esperado: [Nave, Nome do fitting].")
        return result
    result["hull"], result["name"] = header.group(1).strip(), header.group(2).strip()

    # blocos separados por linha em branco
    blocks, cur = [], []
    for raw in lines[1:]:
        if raw.strip():
            cur.append(raw.strip())
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)

    module_block_idx = 0
    for block in blocks:
        first_name, _ = _split_qty(block[0])
        first_mod, _, _ = _split_charge(first_name)
        is_drone_block = all(_DRONE_RE.search(_split_qty(l)[0]) and not _MODULE_RULES_MATCH(l) for l in block)
        is_cargo_block = all(
            (re.search(r"\sx\s*\d+$", l, re.I) is not None) or _CHARGE_RE.search(l) for l in block
        ) and not is_drone_block and not any(_EMPTY_SLOT_RE.match(l) for l in block)

        if is_drone_block:
            for l in block:
                n, q = _split_qty(l)
                result["drones"].append({"name": n, "qty": q})
            continue
        if is_cargo_block:
            for l in block:
                n, q = _split_qty(l)
                result["cargo"].append({"name": n, "qty": q})
                if _CHARGE_RE.search(n):
                    result["charges"].append({"name": n, "qty": q})
            continue

        slot = _SLOT_ORDER[module_block_idx] if module_block_idx < len(_SLOT_ORDER) else None
        module_block_idx += 1
        if slot is None:
            result["warnings"].append(f"Bloco de módulos extra ignorado na classificação de slot: {block[0]}")
            slot = "subsystem"
        for l in block:
            if _EMPTY_SLOT_RE.match(l):
                result["slots"][slot].append({"name": None, "empty": True})
                continue
            mod, charge, offline = _split_charge(l)
            role, active = _classify_module(mod)
            if slot == "rig":
                active = False
                role = "rig"
            entry = {"name": mod, "charge": charge, "role": role, "active": active,
                     "offline": offline, "empty": False}
            result["slots"][slot].append(entry)
            if charge:
                result["charges"].append({"name": charge, "qty": 1})

    result["derived"] = derive_profile_hints(result)
    result["validation"] = validate_fitting(result)
    result["ok"] = not result["errors"]
    return result


def _MODULE_RULES_MATCH(line: str) -> bool:
    mod, _, _ = _split_charge(_split_qty(line)[0])
    role, _ = _classify_module(mod)
    return role != "unknown"


def derive_profile_hints(parsed: dict) -> dict:
    """Deriva dicas de perfil SOMENTE a partir do que está literalmente no fitting."""
    roles = []
    for slot in ("low", "mid", "high"):
        for m in parsed["slots"][slot]:
            if not m.get("empty"):
                roles.append(m["role"])
    out = {"weapon_type": None, "tank_type": None, "propulsion": None, "tackle": [], "drones": bool(parsed["drones"])}
    weapon_map = {"weapon:laser": "Energy Turrets", "weapon:blaster": "Hybrid Turrets (Blasters)",
                  "weapon:railgun": "Hybrid Turrets (Railguns)", "weapon:autocannon": "Projectile (Autocannons)",
                  "weapon:artillery": "Projectile (Artillery)", "weapon:missile": "Missile Launchers"}
    for r in roles:
        if r in weapon_map and not out["weapon_type"]:
            out["weapon_type"] = weapon_map[r]
    if any(r == "tank:ancillary_armor_repairer" for r in roles):
        out["tank_type"] = "Active Armor (Ancillary)"
    elif any(r == "tank:armor_repairer" for r in roles):
        out["tank_type"] = "Active Armor"
    elif any(r in ("tank:shield_booster", "tank:ancillary_shield_booster") for r in roles):
        out["tank_type"] = "Active Shield"
    if "propulsion:mwd" in roles:
        out["propulsion"] = "Microwarpdrive"
    elif "propulsion:afterburner" in roles:
        out["propulsion"] = "Afterburner"
    names = {"tackle:scrambler": "Warp Scrambler", "tackle:disruptor": "Warp Disruptor",
             "tackle:webifier": "Stasis Webifier"}
    out["tackle"] = [names[r] for r in names if r in roles]
    return out


def validate_fitting(parsed: dict, known_slots: dict | None = None) -> dict:
    """
    Valida a ESTRUTURA do fitting. Itens que dependem de dados do jogo ficam PENDENTES.
    known_slots: {'low':n,'mid':n,'high':n,'rig':n} fornecido pelo piloto (opcional).
    """
    issues, notes = [], []
    if not parsed.get("hull"):
        issues.append("Nave não identificada.")
    for s in ("low", "mid", "high", "rig"):
        count = len(parsed["slots"][s])
        if known_slots and known_slots.get(s) is not None and count > known_slots[s]:
            issues.append(f"{s.upper()}: {count} módulos excedem os {known_slots[s]} slots informados.")
        if count == 0 and s != "rig":
            notes.append(f"Nenhum módulo identificado nos slots {s.upper()}.")
    empties = sum(1 for s in _SLOT_ORDER for m in parsed["slots"][s] if m.get("empty"))
    if empties:
        notes.append(f"{empties} slot(s) vazio(s) no fitting.")
    unknown = [m["name"] for s in ("low", "mid", "high") for m in parsed["slots"][s]
               if not m.get("empty") and m["role"] == "unknown"]
    if unknown:
        notes.append("Módulos sem classificação ativo/passivo (papel desconhecido): " + ", ".join(sorted(set(unknown))))
    has_weapon = any(m["role"].startswith("weapon:") for m in parsed["slots"]["high"])
    if parsed["slots"]["high"] and not has_weapon:
        notes.append("Nenhuma arma reconhecida nos slots altos.")
    return {
        "structure": "INCONSISTENTE" if issues else "OK",
        "issues": issues,
        "notes": notes,
        "pending": [f"{p}: {PENDING} (requer dados do jogo / ESI)" for p in PENDING_VALIDATIONS],
    }


# --------------------------------------------------------------------------- #
# Perfil de combate da nave (manual, seção 4)
# --------------------------------------------------------------------------- #
PROFILE_FIELDS_NUM = ["optimal_m", "falloff_m", "tracking_rad_s", "sig_res_m", "nominal_dps",
                      "speed_ms", "signature_m", "scram_range_m", "cap_gj", "cap_recharge_s"]


def blank_ship_profile(ship: str = "Nova nave") -> dict:
    return {
        "ship": ship,
        "role": None,
        "weapon_type": None,
        "tank_type": None,
        "propulsion": None,
        "tackle": [],
        "drones": None,
        "preferred_engagement_range_m": None,
        "class_hint": "Frigate",
        "reference_range_window_m": None,
        "strengths": [],
        "weaknesses": [],
        # Dados opcionais informados pelo piloto (nunca presumidos)
        "slots": {"low": None, "mid": None, "high": None, "rig": None},
        "weapon_stats": {k: None for k in PROFILE_FIELDS_NUM},
        "ammo": None,
        "fitting_eft": None,
        "notes": "",
    }


# Modelos iniciais editáveis. Só o Tormentor traz valores do manual ("exemplo inicial").
SHIP_TEMPLATES = {
    "Tormentor": {
        "role": "Scram Kiting", "weapon_type": "Small Energy Turrets", "tank_type": "Active Armor",
        "propulsion": "Afterburner", "tackle": ["Warp Scrambler", "Stasis Webifier"], "drones": True,
        "preferred_engagement_range_m": 4000,
        "reference_range_window_m": [4000, 7000],  # janela do manual (cenário A) — confirmar alcance real
        "strengths": ["Range Control", "Drone Damage", "Flexible Laser Crystals"],
        "weaknesses": ["Capacitor Pressure", "Limited Speed", "Energy Neutralizers"],
    },
    "Punisher": {"role": None, "weapon_type": "Energy Turrets", "tank_type": "Active Armor",
                 "propulsion": "Afterburner", "tackle": [], "drones": None},
    "Executioner": {"role": None, "weapon_type": "Energy Turrets", "tank_type": None,
                    "propulsion": None, "tackle": [], "drones": None},
    "Imperial Navy Slicer": {"role": None, "weapon_type": "Energy Turrets", "tank_type": None,
                             "propulsion": None, "tackle": [], "drones": None},
    "Coercer": {"class_hint": "Destroyer", "role": None, "weapon_type": "Energy Turrets", "tank_type": None,
                "propulsion": None, "tackle": [], "drones": None},
}


def template_for(ship: str) -> dict:
    p = blank_ship_profile(ship)
    for k, v in SHIP_TEMPLATES.get(ship, {}).items():
        p[k] = copy.deepcopy(v)
    return p


def recommended_range_m(profile: dict) -> dict:
    """
    Recalcula o alcance recomendado quando armas/munição/módulos mudam (seção 4).
    Usa apenas dados informados: optimal/falloff da arma e alcance do scrambler.
    Retorna {value, source, note}.
    """
    ws = profile.get("weapon_stats") or {}
    opt, fall, scram = ws.get("optimal_m"), ws.get("falloff_m"), ws.get("scram_range_m")
    has_scram = any("scrambler" in t.lower() or "disruptor" in t.lower() for t in profile.get("tackle", []))
    cands = []
    if opt:
        cands.append(float(opt))
    if has_scram and scram:
        cands.append(float(scram) * 0.9)
    if cands:
        val = min(cands)
        val = int(round(val / 100.0) * 100)
        parts = []
        if opt:
            parts.append("optimal da arma")
        if has_scram and scram:
            parts.append("alcance do scrambler (com folga de 10%)")
        note = "Calculado a partir de: " + " e ".join(parts) + "."
        if fall:
            note += " Falloff informado permite aplicar dano reduzido além disso."
        return {"value": val, "source": "calculado", "note": note}
    manual = profile.get("preferred_engagement_range_m")
    if manual:
        return {"value": manual, "source": "manual",
                "note": "Valor definido manualmente; informe optimal/falloff/alcance de tackle para recalcular."}
    return {"value": None, "source": PENDING,
            "note": "Sem dados de alcance. Informe optimal da arma e alcance do scrambler."}


class ShipManager:
    """CRUD de naves persistido em data/ships.json."""

    def __init__(self):
        self.ships: dict = load_json(SHIPS_FILE, {})
        if not self.ships:
            self.ships = {"Tormentor": template_for("Tormentor")}
            self.save()

    def save(self) -> bool:
        return save_json(SHIPS_FILE, self.ships)

    def names(self):
        return sorted(self.ships.keys())

    def get(self, name: str):
        return self.ships.get(name)

    def add(self, name: str, profile: dict | None = None) -> dict:
        prof = profile or template_for(name)
        prof["ship"] = name
        self.ships[name] = prof
        self.save()
        return prof

    def update(self, name: str, profile: dict):
        self.ships[name] = profile
        self.save()

    def remove(self, name: str):
        self.ships.pop(name, None)
        self.save()

    def import_eft(self, text: str) -> tuple[dict, dict | None]:
        """Importa EFT e cria/atualiza a nave. Retorna (parsed, profile)."""
        parsed = parse_eft(text)
        if not parsed["ok"]:
            return parsed, None
        hull = parsed["hull"]
        prof = copy.deepcopy(self.ships.get(hull) or template_for(hull))
        d = parsed["derived"]
        for key in ("weapon_type", "tank_type", "propulsion"):
            if d.get(key):
                prof[key] = d[key]
        if d.get("tackle"):
            prof["tackle"] = d["tackle"]
        prof["drones"] = d["drones"] if parsed["drones"] else prof.get("drones")
        prof["fitting_eft"] = text
        ammo = [c["name"] for c in parsed["charges"] if "paste" not in c["name"].lower()]
        prof["ammo"] = ammo or prof.get("ammo")
        prof["ship"] = hull
        parsed["validation"] = validate_fitting(parsed, prof.get("slots"))
        self.ships[hull] = prof
        self.save()
        return parsed, prof
