# -*- coding: utf-8 -*-
"""
EVE Online Market & Radius Quoter (Ultra-Fast Concurrent Edition - v2.1)
Analisa fittings no formato EFT, listas de módulos simples e cópias de inventário.
Cota ordens de venda ao vivo a partir do sistema solar onde o jogador está,
dentro de um raio configurável de 'X' jumps via EVE Swagger Interface (ESI).
Execução multi-threaded concorrente com pooling de conexões TCP/TLS, busca multi-regional
(região local + hub mais próximo + Jita universal) e cache persistente em disco.
"""

import os
import glob
import json
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_FILE = os.path.join(DATA_DIR, "market_cache.json")

# Sessão HTTP reutilizável com pooling de conexões TCP/TLS
session = requests.Session()
session.headers.update({
    'User-Agent': 'EVECopilot/2.1 (Linux; Tactical Overlay)',
    'Accept': 'application/json'
})

# Estruturas de Cache em Memória
CACHE_SYSTEM_INFO = {}
CACHE_ROUTES = {}
CACHE_NAMES = {}
CACHE_TYPES = {}
CACHE_SYSTEM_SECURITY = {}

def load_disk_cache():
    global CACHE_SYSTEM_INFO, CACHE_ROUTES, CACHE_NAMES, CACHE_TYPES, CACHE_SYSTEM_SECURITY
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                CACHE_SYSTEM_INFO.update(data.get("systems_info", {}))
                CACHE_NAMES.update({int(k): v for k, v in data.get("names", {}).items()})
                CACHE_TYPES.update({k.lower(): v for k, v in data.get("types", {}).items()})
                CACHE_SYSTEM_SECURITY.update({int(k): v for k, v in data.get("security", {}).items()})
                for k, v in data.get("routes", {}).items():
                    parts = k.split(":")
                    if len(parts) == 3:
                        CACHE_ROUTES[(int(parts[0]), int(parts[1]), parts[2])] = v
        except Exception as e:
            print(f"Aviso ao carregar cache de disco: {e}")

def save_disk_cache():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        routes_serialized = {f"{k[0]}:{k[1]}:{k[2]}": v for k, v in CACHE_ROUTES.items()}
        data = {
            "systems_info": CACHE_SYSTEM_INFO,
            "names": CACHE_NAMES,
            "types": CACHE_TYPES,
            "security": CACHE_SYSTEM_SECURITY,
            "routes": routes_serialized
        }
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        print(f"Aviso ao salvar cache de disco: {e}")

# Carrega o cache inicial do disco
load_disk_cache()

# Trade Hubs de referência (IDs verificados)
REFERENCE_HUBS = {
    "Jita 4-4": {"station_id": 60003760, "system_id": 30000142, "region_id": 10000002},
    "Dodixie IX": {"station_id": 60011866, "system_id": 30002659, "region_id": 10000032},
    "Amarr VIII": {"station_id": 60008494, "system_id": 30002187, "region_id": 10000043},
    "Rens VI": {"station_id": 60004588, "system_id": 30002510, "region_id": 10000030},
    "Hek VIII": {"station_id": 60005686, "system_id": 30002053, "region_id": 10000042}
}

def detect_system_from_logs(log_dir):
    """
    Varre os logs mais recentes de combate/jogo para detectar em qual sistema solar o piloto está.
    """
    if not os.path.exists(log_dir):
        return "Villore"
    files = glob.glob(os.path.join(log_dir, "*.txt"))
    if not files:
        return "Villore"
    latest = max(files, key=os.path.getmtime)

    # Expressões regulares para transições de sistema
    undock_re = re.compile(r'Undocking from .*? to ([A-Za-z0-9\-\']+) solar system', re.IGNORECASE)
    jump_re = re.compile(r'(?:jumping (?:from .*? )?to|warping to)\s+([A-Za-z0-9\-\']+)', re.IGNORECASE)
    blacklist = ['target', 'stargate', 'station', 'gate', 'cargo', 'wreck', 'asteroid', 'beacon', 'sun', 'perimeter', 'belt', 'site']

    try:
        with open(latest, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # 1. Procura primeiro por undock explícito (mais confiável)
            for l in reversed(lines[-250:]):
                clean = re.sub(r'<[^>]+>', '', l).strip()
                m = undock_re.search(clean)
                if m:
                    cand = m.group(1).strip()
                    if cand.lower() not in blacklist and len(cand) > 2:
                        return cand

            # 2. Procura por jumps/warps
            for l in reversed(lines[-250:]):
                clean = re.sub(r'<[^>]+>', '', l).strip()
                m = jump_re.search(clean)
                if m:
                    cand = m.group(1).strip()
                    if cand.lower() not in blacklist and len(cand) > 2:
                        return cand
    except Exception:
        pass

    return "Villore"

def _clean_item_line(line):
    """
    Interpreta uma linha de texto em múltiplos formatos:
    - '1x Data Analyzer I'
    - 'Data Analyzer I x2'
    - '1 Data Analyzer I'
    - 'Data Analyzer I\t1\tModule' (cópia tabulada do EVE)
    - '- Hobgoblin I'
    """
    line = line.strip().strip('-*• \t')
    if not line or line.startswith('['):
        return None, 1

    # Formato separado por TAB (ex: tabela do inventário/hangar do EVE)
    if '\t' in line:
        parts = [p.strip() for p in line.split('\t') if p.strip()]
        if parts:
            name = parts[0]
            qty = 1
            if len(parts) > 1 and parts[1].replace('.', '').replace(',', '').isdigit():
                qty = int(parts[1].replace('.', '').replace(',', ''))
            return name, qty

    # '1x Item' ou '1 x Item'
    m1 = re.match(r'^([0-9]+)\s*x\s+(.+)$', line, re.IGNORECASE)
    if m1:
        return m1.group(2).strip(), int(m1.group(1))

    # 'Item x 2' ou 'Item x2'
    m2 = re.match(r'^(.+?)\s+x\s*([0-9]+)$', line, re.IGNORECASE)
    if m2:
        return m2.group(1).strip(), int(m2.group(2))

    # '1 Item' (primeiro token é número e resto é letras)
    m3 = re.match(r'^([0-9]+)\s+([A-Za-z].+)$', line)
    if m3 and not m3.group(2).isdigit():
        return m3.group(2).strip(), int(m3.group(1))

    # 'Item 1' (se terminar com número sem ser numeral romano)
    m4 = re.match(r'^(.+?)\s+([0-9]+)$', line)
    if m4 and not m4.group(1).endswith((' I', ' II', ' III', ' IV', ' V', ' VI', ' VII', ' VIII', ' IX', ' X')):
        return m4.group(1).strip(), int(m4.group(2))

    return line, 1

def parse_eft_fitting(eft_text):
    """
    Interpreta tanto fittings EFT completos ([Ship, FitName]...) quanto listas avulsas de itens.
    """
    lines = [line.strip() for line in eft_text.strip().splitlines() if line.strip()]
    if not lines:
        return None, None, {}

    ship_name = "Nave"
    fit_name = "Fit"

    first_line = lines[0]
    if first_line.startswith("[") and "]" in first_line:
        header = first_line.strip("[]")
        parts = header.split(",")
        ship_name = parts[0].strip()
        fit_name = parts[1].strip() if len(parts) > 1 else "Custom Fit"
        content_lines = lines[1:]
    else:
        content_lines = lines

    item_counts = Counter()
    if ship_name and ship_name != "Nave":
        item_counts[ship_name] += 1

    for raw_line in content_lines:
        if not raw_line or raw_line.startswith("["):
            continue
        if raw_line.lower() in ["[empty low slot]", "[empty med slot]", "[empty high slot]", "[empty rig slot]"]:
            continue

        # Submódulos separados por vírgula em EFT (ex: '125mm Railgun I, Antimatter Charge S')
        if "," in raw_line:
            for subpart in raw_line.split(","):
                name, qty = _clean_item_line(subpart)
                if name:
                    item_counts[name] += qty
        else:
            name, qty = _clean_item_line(raw_line)
            if name:
                item_counts[name] += qty

    return ship_name, fit_name, dict(item_counts)

def get_system_security(system_id):
    if system_id in CACHE_SYSTEM_SECURITY:
        return CACHE_SYSTEM_SECURITY[system_id]
    try:
        url = f"https://esi.evetech.net/latest/universe/systems/{system_id}/"
        r = session.get(url, timeout=3.5)
        if r.status_code == 200:
            sec = float(r.json().get("security_status", 0.0))
            CACHE_SYSTEM_SECURITY[system_id] = sec
            return sec
    except Exception as e:
        print(f"Erro ao obter security do sistema {system_id}: {e}")
    return 0.5

def get_security_details(sec_val):
    sec_round = round(sec_val, 1)
    if sec_round == -0.0:
        sec_round = 0.0
    if sec_val >= 0.45:
        tier = "High"
        color = "#40c057"
    elif sec_val >= 0.05:
        tier = "Low"
        color = "#fd7e14"
    else:
        tier = "Null"
        color = "#f03e3e"
    return {
        "value": sec_val,
        "label": f"{sec_round:.1f}",
        "tier": tier,
        "color": color
    }

def resolve_system_name(system_name):
    sys_clean = system_name.strip()
    if not sys_clean:
        sys_clean = "Villore"

    if sys_clean.lower() in CACHE_SYSTEM_INFO:
        return CACHE_SYSTEM_INFO[sys_clean.lower()]

    try:
        url = "https://esi.evetech.net/latest/universe/ids/"
        r = session.post(url, json=[sys_clean], timeout=4)
        if r.status_code == 200:
            data = r.json()
            systems = data.get("systems", [])
            if not systems:
                return 30004975, 10000064, sys_clean # Villore default
            sys_id = systems[0]["id"]
            clean_name = systems[0]["name"]

            r_sys = session.get(f"https://esi.evetech.net/latest/universe/systems/{sys_id}/", timeout=4)
            sys_data = r_sys.json()
            const_id = sys_data["constellation_id"]
            sec_status = float(sys_data.get("security_status", 0.0))
            CACHE_SYSTEM_SECURITY[sys_id] = sec_status

            r_const = session.get(f"https://esi.evetech.net/latest/universe/constellations/{const_id}/", timeout=4)
            region_id = r_const.json()["region_id"]

            res = (sys_id, region_id, clean_name)
            CACHE_SYSTEM_INFO[sys_clean.lower()] = res
            return res
    except Exception as e:
        print(f"Erro ao resolver sistema {system_name}: {e}")

    return 30004975, 10000064, sys_clean

def resolve_type_ids(item_names):
    """
    Resolução de IDs de inventário 100% case-insensitive com cache em memória e disco.
    """
    needed = []
    res = {}
    for name in item_names:
        clean = name.strip()
        if clean.lower() in CACHE_TYPES:
            res[clean] = CACHE_TYPES[clean.lower()]
        else:
            needed.append(clean)

    if needed:
        url = "https://esi.evetech.net/latest/universe/ids/"
        try:
            r = session.post(url, json=needed[:400], timeout=5)
            if r.status_code == 200:
                data = r.json()
                for entry in data.get("inventory_types", []):
                    c_name = entry["name"]
                    t_id = entry["id"]
                    CACHE_TYPES[c_name.lower()] = t_id
                    CACHE_NAMES[t_id] = c_name
                    for orig in needed:
                        if orig.lower() == c_name.lower():
                            res[orig] = t_id
        except Exception as e:
            print(f"Erro ao resolver type_ids: {e}")

    for name in item_names:
        clean = name.strip()
        if clean not in res and clean.lower() in CACHE_TYPES:
            res[clean] = CACHE_TYPES[clean.lower()]

    return res

def resolve_names_bulk(id_list):
    needed = [x for x in id_list if x not in CACHE_NAMES]
    if not needed:
        return CACHE_NAMES

    url = "https://esi.evetech.net/latest/universe/names/"
    # Divide em chunks de 400
    for i in range(0, len(needed), 400):
        chunk = needed[i:i+400]
        try:
            r = session.post(url, json=chunk, timeout=5)
            if r.status_code == 200:
                for item in r.json():
                    CACHE_NAMES[item["id"]] = item["name"]
        except Exception as e:
            print(f"Erro ao resolver names em bulk: {e}")

    return CACHE_NAMES

def get_jump_distance(origin_sys_id, dest_sys_id, flag="shortest"):
    if origin_sys_id == dest_sys_id:
        return 0
    key = (origin_sys_id, dest_sys_id, flag)
    if key in CACHE_ROUTES:
        return CACHE_ROUTES[key]

    try:
        url = f"https://esi.evetech.net/latest/route/{origin_sys_id}/{dest_sys_id}/?flag={flag}"
        r = session.get(url, timeout=3.5)
        if r.status_code == 200:
            route = r.json()
            jumps = max(0, len(route) - 1)
            CACHE_ROUTES[key] = jumps
            return jumps
    except Exception:
        pass

    if flag == "secure":
        return get_jump_distance(origin_sys_id, dest_sys_id, flag="shortest")
    return 999

def quote_fitting_near(eft_text, origin_system_name="Villore", min_security="high", max_jumps=None, sort_mode="cheapest", **kwargs):
    """
    Cotação do fitting em paralelo (ultra-rápida e resiliente):
    - Pesquisa na região local, na região do hub mais próximo e em Jita (garantia universal).
    - Prioriza Menor Preço real, Custo-benefício ou Menor distância conforme 'sort_mode'.
    - Mostra múltiplas ofertas de vendedores quando cotado um item individual.
    """
    t_start = time.time()
    ship_name, fit_name, item_counts = parse_eft_fitting(eft_text)
    if not item_counts:
        return None

    # Configura regras do filtro de segurança
    if isinstance(min_security, str):
        m_sec = min_security.lower().strip()
        if m_sec in ["high", "high-sec", "0.5"]:
            min_sec_val = 0.45
            route_flag = "secure"
            filter_label = "High-Sec Apenas (≥ 0.5)"
        elif m_sec in ["safe_high", "safe", "0.7"]:
            min_sec_val = 0.65
            route_flag = "secure"
            filter_label = "High-Sec Seguro (≥ 0.7)"
        elif m_sec in ["low", "low-sec", "0.1"]:
            min_sec_val = 0.05
            route_flag = "shortest"
            filter_label = "Low-Sec Permitido (≥ 0.1)"
        elif m_sec in ["all", "any", "qualquer"]:
            min_sec_val = -1.1
            route_flag = "shortest"
            filter_label = "Qualquer Segurança (Todas)"
        else:
            try:
                num = float(m_sec)
                min_sec_val = num - 0.05
                route_flag = "secure" if min_sec_val >= 0.45 else "shortest"
                filter_label = f"Segurança ≥ {num:.1f}"
            except ValueError:
                min_sec_val = 0.45
                route_flag = "secure"
                filter_label = "High-Sec Apenas (≥ 0.5)"
    elif isinstance(min_security, (int, float)):
        num = float(min_security)
        min_sec_val = num - 0.05
        route_flag = "secure" if min_sec_val >= 0.45 else "shortest"
        filter_label = f"Segurança ≥ {num:.1f}"
    else:
        min_sec_val = 0.45
        route_flag = "secure"
        filter_label = "High-Sec Apenas (≥ 0.5)"

    origin_id, origin_region_id, clean_origin_name = resolve_system_name(origin_system_name)

    name_to_id = resolve_type_ids(list(item_counts.keys()))

    # Descobre o trade hub mais próximo para fallback
    closest_hub_name = "Jita 4-4"
    closest_hub_jumps = 999
    closest_hub_region = 10000002

    for hname, hdata in REFERENCE_HUBS.items():
        j = get_jump_distance(origin_id, hdata["system_id"], flag=route_flag)
        if j < closest_hub_jumps:
            closest_hub_jumps = j
            closest_hub_name = hname
            closest_hub_region = hdata["region_id"]

    # Monta a lista de regiões prioritárias:
    # 1. Região local do piloto
    # 2. Região do hub mais próximo (ex: Dodixie em Sinq Laison)
    # 3. The Citadel (Jita - 10000002) para disponibilidade garantida
    regions_to_query = [origin_region_id]
    if closest_hub_region not in regions_to_query:
        regions_to_query.append(closest_hub_region)
    if 10000002 not in regions_to_query:
        regions_to_query.append(10000002)

    # 1. BUSCA PARALELA DE TODAS AS ORDENS DE MERCADO DOS ITENS NAS REGIÕES RELEVANTES
    unique_tids = set(name_to_id.values())
    orders_by_type = {tid: [] for tid in unique_tids}

    def fetch_orders_job(rid, tid):
        url = f"https://esi.evetech.net/latest/markets/{rid}/orders/?type_id={tid}&order_type=sell"
        try:
            r = session.get(url, timeout=3.5)
            if r.status_code == 200:
                return tid, r.json()
        except Exception:
            pass
        return tid, []

    fetch_tasks = []
    with ThreadPoolExecutor(max_workers=min(14, max(2, len(unique_tids) * len(regions_to_query)))) as executor:
        for tid in unique_tids:
            for rid in regions_to_query:
                fetch_tasks.append(executor.submit(fetch_orders_job, rid, tid))
        for fut in as_completed(fetch_tasks):
            tid, ords = fut.result()
            if ords:
                orders_by_type[tid].extend(ords)

    # 2. COLETA TODOS OS SISTEMAS ONDE EXISTEM ORDENS DE VENDA
    candidate_systems = set()
    for tid, ords in orders_by_type.items():
        for o in ords:
            sys_id = o.get("system_id")
            if sys_id:
                candidate_systems.add(sys_id)

    # 3. PRÉ-RESOLUÇÃO CONCORRENTE DE ROTAS E NÍVEL DE SEGURANÇA PARA TODOS OS SISTEMAS DAS ORDENS
    def resolve_system_env(sys_id):
        get_system_security(sys_id)
        get_jump_distance(origin_id, sys_id, flag=route_flag)

    unresolved_systems = [s for s in candidate_systems if s not in CACHE_SYSTEM_SECURITY or (origin_id, s, route_flag) not in CACHE_ROUTES]
    if unresolved_systems:
        with ThreadPoolExecutor(max_workers=min(14, len(unresolved_systems))) as executor:
            list(executor.map(resolve_system_env, unresolved_systems))

    # 4. CASAMENTO INTELIGENTE EM MEMÓRIA DE CADA ITEM (PREFERE NO RAIO; SENÃO NEAREST FALLBACK)
    items_quoted = []
    ids_to_resolve = set()
    total_in_radius = 0.0
    items_in_radius_count = 0

    for item_name, qty in item_counts.items():
        tid = name_to_id.get(item_name)
        if not tid:
            items_quoted.append({
                "name": item_name,
                "qty": qty,
                "in_radius": False,
                "jumps": -1,
                "station_name": "Item Desconhecido (Verifique o nome)",
                "system_name": "—",
                "system_security": 0.0,
                "sec_details": get_security_details(0.0),
                "price": 0.0,
                "total": 0.0
            })
            continue

        raw_orders = orders_by_type.get(tid, [])
        valid_orders = [o for o in raw_orders if float(o.get("price", 0.0)) > 0]

        candidates = []
        for o in valid_orders:
            dsys = o.get("system_id")
            sys_sec = get_system_security(dsys)
            jumps = get_jump_distance(origin_id, dsys, flag=route_flag)
            price = float(o.get("price", 0.0))
            loc_id = o.get("location_id")
            is_npc_station = loc_id < 100000000 # Estações NPC públicas

            candidates.append({
                "price": price,
                "volume_remain": int(o.get("volume_remain", 1)),
                "location_id": loc_id,
                "system_id": dsys,
                "system_security": sys_sec,
                "jumps": jumps,
                "is_npc": is_npc_station
            })

        # 1. Filtra ordens que atendem ao critério de segurança e raio de saltos exigido
        sec_candidates = [c for c in candidates if c["system_security"] >= min_sec_val]
        if max_jumps is not None and isinstance(max_jumps, (int, float)) and max_jumps >= 0:
            jump_candidates = [c for c in sec_candidates if c["jumps"] <= max_jumps]
            pool = jump_candidates if jump_candidates else sec_candidates
        else:
            pool = sec_candidates if sec_candidates else candidates

        if not pool:
            continue

        global_min_price = min(c["price"] for c in pool)
        s_mode = str(sort_mode).lower().strip() if sort_mode else "cheapest"

        def score_order(c):
            price = c["price"]
            jumps = c["jumps"]
            is_npc = c["is_npc"]

            if s_mode in ["nearest", "proximo", "saltos"]:
                # Prioriza 100% menor número de jumps; desempata por menor preço
                return (jumps, price, not is_npc)
            elif s_mode in ["balanced", "equilibrado", "custo_beneficio"]:
                # Aceita comprar mais perto se a diferença for pequena (<= 3% do menor preço)
                ratio = (price / global_min_price) if global_min_price > 0 else 1.0
                if jumps == 0 and ratio <= 1.05:
                    tier = 0
                elif ratio <= 1.08:
                    tier = 1
                else:
                    tier = 2
                return (tier, price, jumps, not is_npc)
            else:
                # "cheapest" (Padrão): MENOR PREÇO REAL EM 1º LUGAR!
                # Desempata por número de saltos
                return (price, jumps, not is_npc)

        pool.sort(key=score_order)

        # Se foi pesquisado um item único (ex: "Cap Recharger I"),
        # exibe todas as ofertas encontradas no raio (até 12 melhores ofertas por estação)!
        if len(item_counts) == 1:
            seen_locs = set()
            unique_orders = []
            for c in pool:
                if c["location_id"] not in seen_locs:
                    seen_locs.add(c["location_id"])
                    unique_orders.append(c)
                if len(unique_orders) >= 12:
                    break

            min_p = min(c["price"] for c in unique_orders)

            for idx, choice in enumerate(unique_orders):
                ids_to_resolve.add(choice["location_id"])
                ids_to_resolve.add(choice["system_id"])
                item_total = choice["price"] * qty

                badge = ""
                if choice["price"] == min_p:
                    badge = " 🏆 [Menor Preço]"
                elif choice["jumps"] == 0:
                    badge = " 🏠 [Mesmo Sistema]"

                items_quoted.append({
                    "name": f"{item_name}{badge}",
                    "raw_name": item_name,
                    "qty": qty,
                    "stock_avail": choice.get("volume_remain", qty),
                    "in_radius": True,
                    "jumps": choice["jumps"],
                    "location_id": choice["location_id"],
                    "system_id": choice["system_id"],
                    "system_security": choice["system_security"],
                    "sec_details": get_security_details(choice["system_security"]),
                    "price": choice["price"],
                    "total": item_total,
                    "is_best": idx == 0
                })

            best_choice = unique_orders[0]
            total_in_radius += best_choice["price"] * qty
            items_in_radius_count = len(unique_orders)
        else:
            best_choice = pool[0]
            ids_to_resolve.add(best_choice["location_id"])
            ids_to_resolve.add(best_choice["system_id"])
            item_total = best_choice["price"] * qty
            total_in_radius += item_total
            items_in_radius_count += 1

            items_quoted.append({
                "name": item_name,
                "raw_name": item_name,
                "qty": qty,
                "stock_avail": best_choice.get("volume_remain", qty),
                "in_radius": True,
                "jumps": best_choice["jumps"],
                "location_id": best_choice["location_id"],
                "system_id": best_choice["system_id"],
                "system_security": best_choice["system_security"],
                "sec_details": get_security_details(best_choice["system_security"]),
                "price": best_choice["price"],
                "total": item_total
            })

    # 5. RESOLUÇÃO BULK DOS NOMES DAS ESTAÇÕES E SISTEMAS
    name_map = resolve_names_bulk(list(ids_to_resolve))
    for it in items_quoted:
        if "location_id" in it:
            loc_id = it["location_id"]
            sys_id = it.get("system_id")
            s_name = name_map.get(loc_id)
            if not s_name:
                s_name = f"Estrutura {loc_id}" if loc_id >= 100000000 else f"Estação {loc_id}"
            it["station_name"] = s_name
            it["system_name"] = name_map.get(sys_id, f"Sistema {sys_id}")

    # Identifica concentração de compras e itens locais (0 jumps)
    station_counter = Counter(it.get("station_name") for it in items_quoted if it.get("station_name"))
    top_station, top_station_count = station_counter.most_common(1)[0] if station_counter else ("Nenhuma", 0)
    local_items_count = sum(1 for it in items_quoted if it.get("jumps") == 0)

    elapsed = round(time.time() - t_start, 2)
    total_items = len(items_quoted)

    rec = f"📍 Origem: <b>{clean_origin_name}</b> (Segurança: <b>{filter_label}</b>): <b>{total_items}/{total_items}</b> peças cotadas em <b>{elapsed}s</b>."
    if local_items_count > 0:
        rec += f"<br>🏠 <b>{local_items_count} peça(s)</b> encontradas <b>neste mesmo sistema (0 saltos)</b>!"
    if top_station_count > 1 and top_station != "Nenhuma":
        rec += f"<br>🎯 <b>Estação recomendada:</b> '{top_station}' concentra {top_station_count} das suas peças."

    # Salva cache atualizado no disco em background
    try:
        save_disk_cache()
    except Exception:
        pass

    return {
        "ship_name": ship_name,
        "fit_name": fit_name,
        "origin_system": clean_origin_name,
        "max_jumps": max_jumps,
        "filter_label": filter_label,
        "items": items_quoted,
        "total_in_radius": total_in_radius,
        "items_in_radius_count": items_in_radius_count,
        "total_items_count": total_items,
        "elapsed": elapsed,
        "recommendation": rec
    }
