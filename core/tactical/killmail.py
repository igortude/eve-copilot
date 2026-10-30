# -*- coding: utf-8 -*-
"""
Análise de killmails (manual, seções 18 e 21). Usa APENAS a ESI pública (dados públicos permitidos).
Aceita: JSON de killmail ESI colado, URL ESI (/killmails/<id>/<hash>/), "id hash" ou URL do zKillboard.
Nenhuma leitura do cliente do jogo.
"""
import json
import re
import urllib.request

ESI = "https://esi.evetech.net/latest"
UA = {"User-Agent": "eve-tactical-copilot/1.0 (personal training tool)", "Accept": "application/json"}


def _get(url, data=None, timeout=12):
    req = urllib.request.Request(url, data=data, headers={**UA, **({"Content-Type": "application/json"} if data else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_input(text: str) -> dict:
    """Retorna {'json': dict} ou {'id':..., 'hash':...} ou {'zkill_id':...} ou {'error':...}."""
    t = (text or "").strip()
    if not t:
        return {"error": "Killmail vazio."}
    if t.startswith("{"):
        try:
            return {"json": json.loads(t)}
        except Exception as e:
            return {"error": f"JSON inválido: {e}"}
    m = re.search(r"killmails/(\d+)/([0-9a-f]{40})", t)
    if m:
        return {"id": int(m.group(1)), "hash": m.group(2)}
    m = re.match(r"^(\d+)\s+([0-9a-f]{40})$", t)
    if m:
        return {"id": int(m.group(1)), "hash": m.group(2)}
    m = re.search(r"zkillboard\.com/kill/(\d+)", t)
    if m:
        return {"zkill_id": int(m.group(1))}
    return {"error": "Formato não reconhecido. Cole JSON ESI, 'id hash', URL ESI ou URL do zKillboard."}


def summarize(km: dict, names: dict | None = None) -> dict:
    """Resumo neutro: sem inferir ações que o killmail não demonstra."""
    victim = km.get("victim", {})
    attackers = km.get("attackers", [])
    names = names or {}
    def n(i):
        return names.get(i, f"typeID {i}") if i is not None else "desconhecido"
    return {
        "killmail_id": km.get("killmail_id"),
        "time": km.get("killmail_time"),
        "victim_ship": n(victim.get("ship_type_id")),
        "victim_ship_id": victim.get("ship_type_id"),
        "damage_taken": victim.get("damage_taken"),
        "attackers_count": len(attackers),
        "attacker_ships": sorted({n(a.get("ship_type_id")) for a in attackers if a.get("ship_type_id")}),
        "attacker_weapons": sorted({n(a.get("weapon_type_id")) for a in attackers if a.get("weapon_type_id")}),
        "system_id": km.get("solar_system_id"),
    }


def fetch_and_summarize(text: str) -> dict:
    """Rede: executar fora da thread da UI."""
    p = parse_input(text)
    if "error" in p:
        return p
    try:
        if "zkill_id" in p:
            z = _get(f"https://zkillboard.com/api/killID/{p['zkill_id']}/")
            if not z:
                return {"error": "zKillboard não retornou dados."}
            p = {"id": z[0]["killmail_id"], "hash": z[0]["zkb"]["hash"]}
        km = p["json"] if "json" in p else _get(f"{ESI}/killmails/{p['id']}/{p['hash']}/")
        ids = {km.get("victim", {}).get("ship_type_id")}
        for a in km.get("attackers", []):
            ids.update({a.get("ship_type_id"), a.get("weapon_type_id")})
        ids = [i for i in ids if i]
        names = {}
        if ids:
            try:
                res = _get(f"{ESI}/universe/names/", data=json.dumps(ids).encode())
                names = {r["id"]: r["name"] for r in res}
            except Exception:
                names = {}
        return {"summary": summarize(km, names), "raw": km}
    except Exception as e:
        return {"error": f"Falha ao consultar a ESI: {e}"}
