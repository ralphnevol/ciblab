"""Synthetic event log from behaviour templates + rule replay + multi-seed experiments. ALL DATA IS SYNTHETIC.

Scenario generation never consults the rules (see catalog.py). Coverage is derived: a scenario is detected when an
enabled rule fires on at least one of its events."""
import csv, hashlib, json, os, random, statistics, time
from functools import lru_cache
from . import catalog as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(ROOT, "data", "portfolio.csv")
SEEDS = list(range(1337, 1357))  # 20 replay seeds
BASELINE_SEED = 20260101         # the 30-day baseline window that portfolio.csv is derived from
REPLAY_N = 6                     # scenario instances per template in a replay campaign
RULES = {r["id"]: r for r in C.RULES}
TEMPLATES = {t["name"]: t for t in C.TEMPLATES}


def make_events(seed, mode):
    """mode 'baseline': natural attack prevalence; 'replay': a campaign with REPLAY_N instances per template."""
    rng, ev = random.Random(seed), []

    def add(action, vol, scenario=None, dest="corp", sens=0, departing=0, ros=None):
        ev.append({"action": action, "vol": vol, "dest": dest, "sens": sens, "departing": departing,
                   "ros": rng.betavariate(2, 6) * 100 if ros is None else ros, "scenario": scenario})

    beta = lambda ab: rng.betavariate(*ab) * 100
    for r in C.RULES:  # benign background, one pool per action
        if r["id"] not in ("D021", "D031"):
            for _ in range(r["n_benign"]):
                add(r["actions"][0], beta(r["ben"]))
    for _ in range(1000):  # benign proxy uploads (D021's input): most go to approved destinations
        add("net_upload", beta((2, 5)), dest=rng.choices(["corp", "ext_unknown", "personal_cloud"], [60, 25, 15])[0])
    for a, n in (("cloud_sync_upload", 300), ("email_attach_external", 400), ("usb_write", 200), ("repo_bulk_read", 150)):
        for _ in range(n):  # benign egress by non-departing users or to approved channels
            add(a, beta((2, 5)), dest=rng.choice(["corp", "corp", "usb" if a == "usb_write" else "corp"]),
                sens=rng.choice([0, 1]), departing=int(rng.random() < .04))
    for _ in range(14):  # benign departing-user egress of sensitive-looking data to a personal channel
        a = rng.choice(C.INSIDER_ACTIONS)
        add(a, beta((2, 5)), dest="personal_email" if a == "email_attach_external" else "usb" if a == "usb_write"
            else "personal_cloud", sens=rng.choice([2, 3]), departing=1, ros=beta((3, 3)))
    for t in C.TEMPLATES:  # attack / insider scenarios
        for k in range(t["baseline"] if mode == "baseline" else REPLAY_N):
            sid, ros = f"{t['name']}-{k}", beta((8, 2))
            for s in t["steps"]:
                if rng.random() > s["p"]:
                    continue
                for _ in range(s.get("reps", 1)):
                    ab = s.get("vol") or C.ATTACK_VOL.get(s["action"], (6, 2.5))
                    add(s["action"], beta(ab), sid, dest=s.get("dest", "corp"), ros=ros if t.get("insider") else None,
                        sens=rng.choice([2, 3]) if t.get("insider") else 0, departing=int(bool(t.get("insider"))))
    return ev


def _matches(r, e):
    c = r["cond"]
    return (e["action"] in r["actions"] and e["dest"] in c.get("dest_in", [e["dest"]])
            and e["sens"] >= c.get("sens_min", 0) and e["departing"] >= c.get("departing", 0))


@lru_cache(maxsize=64)
def load_log(seed, mode):
    ev = make_events(seed, mode)
    return ev, [[(r["id"], e[r["metric"]]) for r in C.RULES if _matches(r, e)] for e in ev]


def replay(seed, mode="replay", disabled=(), thresholds=None):
    """-> (per-rule {alerts, tp}, {scenario: set(rules that caught it)}, all scenarios)."""
    ev, idx = load_log(seed, mode)
    th, off = thresholds or {}, set(disabled)
    per = {r: {"alerts": 0, "tp": 0} for r in RULES}
    caught, scen = {}, {e["scenario"] for e in ev if e["scenario"]}
    for e, hits in zip(ev, idx):
        for rid, v in hits:
            if rid in off or v < max(RULES[rid]["t0"], th.get(rid, 0)):
                continue
            per[rid]["alerts"] += 1
            if e["scenario"]:
                per[rid]["tp"] += 1
                caught.setdefault(e["scenario"], set()).add(rid)
    return per, caught, scen


def agg(vals):
    vals = [v for v in vals if v is not None]
    return {"mean": round(statistics.mean(vals), 3), "min": round(min(vals), 3), "max": round(max(vals), 3)} if vals else None


def _hours(per, rid):
    return per[rid]["alerts"] * RULES[rid]["mins"] / 60


def run_experiment(spec):
    """spec: {id, type: remove|tighten|control, rule_id, thresholds?, seeds?}. Deterministic; aggregates over seeds.
    Alerts, TP, precision, TP retention and coverage come from the attack-campaign replay; analyst HOURS come from the
    same seed's natural-prevalence baseline window (a campaign's true-positive alerts are not wasted triage time)."""
    t0, seeds, kind, rid = time.time(), spec.get("seeds") or SEEDS, spec["type"], spec.get("rule_id")
    out = {"experiment_id": spec["id"], "type": kind, "rule_id": rid, "n_seeds": len(seeds), "seeds": [seeds[0], seeds[-1]]}
    if kind == "control":
        noop, none_caught, rec, undet, det = True, True, [], [], True
        for s in seeds:
            b = replay(s)
            noop &= replay(s)[:2] == b[:2]
            none_caught &= not replay(s, disabled=list(RULES))[1]
            det &= log_hash(s) == log_hash(s)
            rec.append(len(b[1]) / len(b[2])); undet.append(len(b[2]) - len(b[1]))
        out.update(noop_identical_all_seeds=noop, disable_all_detects_zero=none_caught, deterministic=det,
                   baseline_scenario_recall=agg(rec), undetected_scenarios_baseline=agg(undet),
                   n_scenarios=len(replay(seeds[0])[2]))
    elif kind == "remove":
        lost, tps, hrs, al, prec, tpl, uniq = [], [], [], [], [], {}, []
        for s in seeds:
            per, caught, scen = replay(s)
            _, caught2, _ = replay(s, disabled=[rid])
            gone = sorted(set(caught) - set(caught2))
            lost.append(len(gone)); tps.append(per[rid]["tp"]); hrs.append(_hours(replay(s, "baseline")[0], rid)); al.append(per[rid]["alerts"])
            prec.append(per[rid]["tp"] / per[rid]["alerts"] if per[rid]["alerts"] else None)
            for g in gone:
                tpl[g.rsplit("-", 1)[0]] = tpl.get(g.rsplit("-", 1)[0], 0) + 1
        out.update(baseline={"alerts": agg(al), "tp_alerts": agg(tps), "precision": agg(prec), "hours": agg(hrs)},
                   coverage_loss={"scenarios_lost": agg(lost), "seeds_with_loss": sum(x > 0 for x in lost),
                                  "per_seed": lost, "behaviour_templates_lost_total_over_seeds": tpl},
                   tp_alerts_lost=agg(tps), hours_saved=agg(hrs))
    elif kind == "tighten":
        rows = {t: {"ret": [], "red": [], "hrs": [], "lost": []} for t in spec.get("thresholds", [40, 50, 60, 70, 80, 90])}
        for s in seeds:
            per, caught, _ = replay(s)
            b, nat = per[rid], replay(s, "baseline")[0]
            for t, acc in rows.items():
                pv, cv, _ = replay(s, thresholds={rid: t})
                v = pv[rid]
                acc["ret"].append(v["tp"] / b["tp"] if b["tp"] else None)
                acc["red"].append(1 - v["alerts"] / b["alerts"] if b["alerts"] else None)
                acc["hrs"].append(_hours(nat, rid) - _hours(replay(s, "baseline", thresholds={rid: t})[0], rid)); acc["lost"].append(len(set(caught) - set(cv)))
        out["sweep"] = [{"threshold": t, "tp_retention": agg(a["ret"]), "alert_reduction": agg(a["red"]),
                         "hours_saved": agg(a["hrs"]), "scenarios_lost": agg(a["lost"]),
                         "seeds_with_loss": sum(x > 0 for x in a["lost"]), "n_seeds": len(seeds)} for t, a in rows.items()]
    out["duration_s"] = round(time.time() - t0, 3)
    return out


def log_hash(seed, mode="replay"):
    return hashlib.sha256(json.dumps(make_events(seed, mode), sort_keys=True).encode()).hexdigest()[:16]


def load_portfolio():
    return {r["detection_id"]: {"name": r["name"], "fires": int(r["fires_30d"]), "tp": int(r["true_positives"]),
                                "mins": float(r["analyst_minutes_per_alert"]), "technique": r["mitre_technique"]}
            for r in csv.DictReader(open(PORTFOLIO))}
