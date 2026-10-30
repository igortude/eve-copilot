# -*- coding: utf-8 -*-
"""Testes do núcleo tático (sem UI). Execute: python3 -m pytest tests -q"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tactical import ships, engine, enemies, fw, training, recommend, simulator, killmail, vision  # noqa: E402

EFT = """[Tormentor, Arak VI - Scram Kiting]

Damage Control II
Small Ancillary Armor Repairer
Extruded Compact Heat Sink
Multispectrum Coating II

1MN Monopropellant Enduring Afterburner
Faint Epsilon Scoped Warp Scrambler
X5 Enduring Stasis Webifier

Dual Modulated Pulse Energy Beam I
Dual Modulated Pulse Energy Beam I
Dual Modulated Pulse Energy Beam I

Small Energy Locus Coordinator I
Small Auxiliary Nano Pump I
Small Explosive Armor Reinforcer I

Hobgoblin I x2

Imperial Navy Multifrequency S x3
Imperial Navy Standard S x3
Imperial Navy Radio S x3
Nanite Repair Paste x80
"""


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    import core.tactical as t
    monkeypatch.setattr(t, "DATA_DIR", str(tmp_path))


# ---------------- Ship Manager / EFT ----------------
def test_eft_parse_manual_sample():
    r = ships.parse_eft(EFT)
    assert r["ok"] and r["hull"] == "Tormentor"
    assert [len(r["slots"][s]) for s in ("low", "mid", "high", "rig")] == [4, 3, 3, 3]
    assert r["drones"] == [{"name": "Hobgoblin I", "qty": 2}]
    assert any(c["name"] == "Nanite Repair Paste" and c["qty"] == 80 for c in r["cargo"])
    d = r["derived"]
    assert d["propulsion"] == "Afterburner" and "Warp Scrambler" in d["tackle"] and d["drones"] is True
    assert d["tank_type"].startswith("Active Armor")


def test_eft_validation_marks_pending_not_invented():
    v = ships.parse_eft(EFT)["validation"]
    pend = " ".join(v["pending"])
    for k in ("CPU", "Powergrid", "Calibração", "habilidades"):
        assert k in pend and "PENDENTE" in pend


def test_eft_invalid_header():
    r = ships.parse_eft("Tormentor sem colchetes")
    assert not r["ok"] and r["errors"]


def test_ship_manager_multiple_ships_and_import():
    m = ships.ShipManager()
    m.add("Punisher")
    parsed, prof = m.import_eft(EFT)
    assert prof["ship"] == "Tormentor" and prof["propulsion"] == "Afterburner"
    assert {"Punisher", "Tormentor"} <= set(m.names())
    assert ships.ShipManager().get("Punisher") is not None  # persistência


def test_recommended_range_recalculates_when_weapon_changes():
    p = ships.template_for("Tormentor")
    assert ships.recommended_range_m(p)["source"] == "manual"
    p["weapon_stats"].update(optimal_m=3000, scram_range_m=7500)
    r1 = ships.recommended_range_m(p)
    assert r1["source"] == "calculado" and r1["value"] == 3000
    p["weapon_stats"]["optimal_m"] = 9000
    assert ships.recommended_range_m(p)["value"] == 6800  # limitado ao scrambler*0.9


# ---------------- Enemy Analyzer ----------------
def test_enemy_distinguishes_facts_and_hypotheses():
    a = enemies.analyze_enemy("Merlin", ships.template_for("Tormentor"))
    assert a["known"] and a["facts"]["Classe"] == "Frigate"
    assert "Possíveis armamentos" in a["hypotheses"]
    assert "DESCONHECIDO" in a["message"]
    labels = a["hypotheses"]["Possíveis armamentos"]
    assert any("Blasters" in l for l in labels) and any("Railguns" in l for l in labels)  # não presume um só


def test_enemy_unknown_ship_is_not_invented():
    a = enemies.analyze_enemy("Nave Inexistente 9000")
    assert not a["known"] and a["risk_hint"] == "DESCONHECIDO" and not a["hypotheses"]


# ---------------- Engagement Risk ----------------
def _p():
    return ships.template_for("Tormentor")


def test_risk_unknown_when_info_missing():
    r = engine.classify_engagement({"player": _p(), "enemy": "Rifter", "distance_m": 4000})
    assert r["classification"] == "DESCONHECIDO" and r["missing"]


def test_risk_never_has_percentages():
    r = engine.classify_engagement({"player": _p(), "enemy": "Atron", "enemy_weapon": "blaster", "enemy_faster": False,
                                    "enemy_tackle": False, "own_cap_pct": 90})
    assert r["classification"] in ("FAVORÁVEL", "EQUILIBRADO", "DESFAVORÁVEL")
    assert "%" not in r["disclaimer"].replace("não há probabilidade", "")


def test_risk_numbers_unfavorable():
    assert engine.classify_engagement({"player": _p(), "enemy": "Merlin", "enemy_count": 3})["classification"] == "DESFAVORÁVEL"


# ---------------- Decision / Range ----------------
def test_scenario_a_blasters_keep_at_range_window():
    d = engine.decide({"player": _p(), "enemy": "Atron", "enemy_weapon": "blaster"})
    assert "A" in d["scenarios"] and d["movement"] == "KEEP AT RANGE"
    assert "4.000" in d["distance"] and "7.000" in d["distance"]


def test_scenario_a_does_not_recommend_7km_if_lasers_cannot_apply():
    p = _p()
    p["weapon_stats"].update(optimal_m=2000, falloff_m=2000, scram_range_m=7500)
    d = engine.decide({"player": p, "enemy": "Atron", "enemy_weapon": "blaster"})
    assert d["window"]["hi"] <= 3000
    assert any("Não recomendar" in c for c in d["cautions"])


def test_scenario_c_missiles_no_orbit_only():
    d = engine.decide({"player": _p(), "enemy": "Kestrel", "enemy_weapon": "light_missile"})
    assert "C" in d["scenarios"] and d["movement"] != "ORBIT"
    assert any("Orbit" in c for c in d["cautions"])


def test_scenario_d_faster_enemy_not_kar_guaranteed():
    d = engine.decide({"player": _p(), "enemy": "Atron", "enemy_weapon": "blaster", "enemy_faster": True})
    assert "D" in d["scenarios"] and d["movement"] == "PILOTAGEM MANUAL"
    assert any("NÃO trate Keep at Range" in c for c in d["cautions"])


def test_scenario_e_multiple_enemies_retreat():
    d = engine.decide({"player": _p(), "enemy": "Incursus", "enemy_count": 3})
    assert "E" in d["scenarios"] and d["movement"] == "RETIRADA"


def test_scenario_b_orbit_is_not_automatic():
    d = engine.decide({"player": _p(), "enemy": "Rupture", "enemy_weapon": "autocannon"})
    assert "B" in d["scenarios"] and any("Orbit" in c for c in d["cautions"])


def test_no_decision_without_data():
    d = engine.decide({"player": _p(), "enemy": None})
    assert d["movement"] is None and not d["complete"]
    card = engine.combat_card({"player": _p(), "enemy": None})
    assert not card["ok"] and "INSUFICIENTES" in card["text"]


def test_combat_card_format_matches_manual():
    c = engine.combat_card({"player": _p(), "enemy": "Rifter", "distance_m": 4000})
    for k in ("INIMIGO: Rifter", "RISCO: DESCONHECIDO", "DISTÂNCIA: 4 KM", "MOVIMENTO: KEEP AT RANGE",
              "TACKLE: WARP SCRAMBLER + STASIS WEBIFIER", "PRIORIDADE: MANTER A DISTÂNCIA",
              "PERIGO: CONTROLE DE RANGE", "RETIRADA:"):
        assert k in c["text"]


# ---------------- Weapon application ----------------
def test_weapon_application_pending_when_missing():
    r = engine.weapon_application(optimal_m=3000)
    assert r["status"] == "PENDENTE" and "Tracking" in r["missing"]


def test_weapon_application_effective_dps_below_nominal():
    r = engine.weapon_application(optimal_m=3000, falloff_m=5000, tracking_rad_s=0.1, sig_res_m=40,
                                  target_sig_m=35, distance_m=9000, transversal_ms=300, nominal_dps=60)
    assert r["status"] == "OK" and r["effective_dps"] < 60


def test_weapon_application_perfect_conditions():
    r = engine.weapon_application(optimal_m=5000, falloff_m=5000, tracking_rad_s=0.5, sig_res_m=40,
                                  target_sig_m=400, distance_m=3000, angular_rad_s=0.0)
    assert r["chance_to_hit"] == pytest.approx(1.0)


# ---------------- Ammo ----------------
def test_ammo_atron_6km_standard_like_manual():
    r = engine.recommend_ammo(6000, _p())
    assert r["crystal"] == "Standard" and "alcance" in " ".join(r["motive"]).lower()
    assert "Confirmar Optimal Range" in r["observation"]


def test_ammo_uses_pilot_ranges_when_given():
    r = engine.recommend_ammo(6000, _p(), crystal_ranges={"Multifrequency": 3000, "Standard": 7000, "Radio": 11000})
    assert r["crystal"] == "Standard"


def test_ammo_pending_without_distance():
    assert engine.recommend_ammo(None)["status"] == "PENDENTE"


# ---------------- Capacitor / Armor / Alerts ----------------
def test_capacitor_never_auto_drops_scrambler():
    r = engine.capacitor_advice(10, _p(), scram_on=True)
    assert r["level"] == "CRÍTICO" and any("scrambler" in l for l in r["lines"])


def test_armor_not_waiting_for_critical():
    r = engine.armor_advice(60, paste_count=15, profile=_p())
    assert r["level"] == "ATIVAR" and any("Nanite" in l for l in r["lines"])


def test_alerts_range_lost_and_tracking():
    a = engine.generate_alerts({"profile": _p(), "enemy": "Atron", "distance_m": 1200, "planned_range_m": 4000,
                                "shots": 12, "miss_ratio": 0.8})
    keys = {x["key"] for x in a}
    assert {"range", "tracking"} <= keys


def test_alerts_incoming():
    a = engine.generate_alerts({"profile": _p(), "enemy": "Atron", "prev_distance_m": 9000, "distance_m": 8000,
                                "planned_range_m": 4000})
    assert a and a[0]["title"].startswith("⚠️ INIMIGO APROXIMANDO") and "Prepare Webifier." in a[0]["lines"]


# ---------------- FW ----------------
def test_fw_distinguishes_activities_and_verifies():
    assert len(fw.ACTIVITY_KINDS) == 4 and "Pirate Insurgencies" in fw.ACTIVITY_KINDS
    assert "VERIFIQUE" in fw.check_entry("Novice", "Frigate")["message"]


def test_dscan_parse_counts_and_alerts():
    txt = "1\tBob\tIncursus\t1 AU\n2\tAl\tAtron\t2 AU\n3\tX\tMerlin\t3 AU\n4\tY\tCombat Scanner Probe\t4 AU"
    r = fw.parse_dscan(txt)
    assert r["by_class"]["Frigate"] == 3 and r["probes"] == 1 and len(r["alerts"]) == 2


# ---------------- Training / AAR / History ----------------
def test_concept_answer_orbit_cruiser():
    c = training.answer_concept("Por que devo orbitar uma cruiser?")
    assert c and "drones, webifiers" in c["answer"]


def test_aar_only_states_evidence():
    r = training.after_action_review({"ship": "Tormentor", "enemy": "Atron", "result": "DERROTA", "min_distance_m": 500,
                                      "planned_range_m": 4000, "enemy_weapon": "blaster"}, _p())
    assert "perdeu_range" in r["tags"] and "500 m" in r["text"] and "POSSÍVEL CONSEQUÊNCIA" in r["text"]
    r2 = training.after_action_review({"ship": "Tormentor", "enemy": "Atron", "result": "DERROTA"}, _p())
    assert "Evidência insuficiente" in r2["text"] and r2["tags"] == ["sem_dados"]


def test_history_pattern_detection():
    h = training.PilotHistory()
    for _ in range(3):
        h.add({"result": "DERROTA", "problems": ["perdeu_range"], "ship_lost": True, "isk_lost": 1e6})
    h.add({"result": "VITÓRIA", "enemy_destroyed": True, "isk_destroyed": 2e6})
    s = h.stats()
    assert s["combats"] == 4 and s["wins"] == 1 and s["losses"] == 3 and s["ships_lost"] == 3
    pat = h.patterns()
    assert pat and pat[0]["priority"] == "ALTA" and "Range Control" in pat[0]["training"]
    assert training.PilotHistory().stats()["combats"] == 4  # persistência


def test_history_no_pattern_with_few_losses():
    h = training.PilotHistory()
    h.add({"result": "DERROTA", "problems": ["perdeu_range"]})
    assert h.patterns() == []


# ---------------- Recommendation ----------------
def test_recommendation_does_not_favor_expensive():
    r = recommend.recommend({"account": "Alpha", "budget": "baixo", "style": "scram kite", "experience": "Beginner",
                             "faction_pref": "Amarr"})
    assert r and all(x["cost"] == "baixo" for x in r) and r[0]["pros"] and r[0]["cons"]
    r2 = recommend.recommend({"account": "Omega", "budget": "alto", "style": "kite", "experience": "Beginner"})
    assert any(x["cost"] == "baixo" for x in r2)  # nave barata continua entre as recomendadas


def test_recommendation_not_limited_to_tormentor():
    names = {x["name"] for x in recommend.recommend({"account": "Alpha", "budget": "baixo", "style": "brawl"}, top_n=8)}
    assert len(names - {"Tormentor"}) >= 4


# ---------------- Simulator ----------------
def test_simulator_kar_does_not_retreat():
    s = simulator.RelativeMotionSim()
    s.player_mode, s.player_range, s.enemy_mode, s.enemy_range = "KEEP AT RANGE", 4000, "APROXIMAR", 500
    for _ in range(600):
        m = s.step(0.1)
    assert m["distance"] < 2500
    assert any("range perdido" in msg for _, msg in s.log)


def test_simulator_orbit_has_angular_velocity():
    s = simulator.RelativeMotionSim()
    s.e = [2000.0, 0.0]
    s.player_mode, s.player_range, s.enemy_mode = "ORBIT", 2000, "PARADO"
    for _ in range(200):
        m = s.step(0.1)
    assert m["angular"] > 0.05 and abs(m["distance"] - 2000) < 400


def test_simulator_web_slows_enemy():
    a, b = simulator.RelativeMotionSim(), simulator.RelativeMotionSim()
    b.player_web_on_enemy = True
    for s in (a, b):
        s.enemy_mode, s.enemy_range = "APROXIMAR", 100
        for _ in range(100):
            s.step(0.1)
    assert b.metrics()["distance"] > a.metrics()["distance"]


# ---------------- Killmail / Vision ----------------
def test_killmail_parse_and_summary():
    km = {"killmail_id": 1, "victim": {"ship_type_id": 5, "damage_taken": 100},
          "attackers": [{"ship_type_id": 7}, {"ship_type_id": 8}]}
    assert killmail.parse_input('{"a":1}')["json"] == {"a": 1}
    assert killmail.parse_input("lixo")["error"]
    s = killmail.summarize(km, {5: "Tormentor", 7: "Atron", 8: "Atron"})
    assert s["victim_ship"] == "Tormentor" and s["attackers_count"] == 2 and s["attacker_ships"] == ["Atron"]
    assert killmail.parse_input("https://esi.evetech.net/latest/killmails/123/" + "a" * 40 + "/")["id"] == 123


def test_vision_marks_unreadable_unknown():
    out = vision.format_result({"nave_atual": "Tormentor", "capacitor": None})
    assert "Tormentor" in out and "DESCONHECIDO (não legível" in out
    assert vision.analyze_image("x.png", "http://localhost:11434", "")["ok"] is False
    assert vision.extract_json('blá {"capacitor": null} blá') == {"capacitor": None}
