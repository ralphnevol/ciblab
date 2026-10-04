"""Assemble report.md from research_record.jsonl plus code-measured replays. Reports only what is in the record or
recomputed from the seeded synthetic simulation (20 seeds). ALL DATA IS SYNTHETIC."""
import csv, hashlib, json, os, re, sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "baseline"))
from sim.core import SEEDS, REPLAY_N, RULES, agg, replay
from sim import catalog as C
from lab.tools import score_detections

recs = [json.loads(l) for l in open(os.path.join(ROOT, "research_record.jsonl")) if l.strip()]
P = lambda stage: [r["payload"] for r in recs if r["stage"] == stage]
base_rows = score_detections(os.path.join(ROOT, "baseline", "data", "portfolio.csv"))
base = {r["detection_id"]: r for r in base_rows}
base_dec = [r["detection_id"] for r in base_rows if r["verdict"] == "decommission"]
N = len(SEEDS)

results = [x for p in P("result") for x in p.get("results", [])]
control = next((x for x in results if x.get("type") == "control"), None)
remove_res = {x["rule_id"]: x for x in results if x.get("type") == "remove"}
tighten_res = {x["rule_id"]: x for x in results if x.get("type") == "tighten"}  # later iteration overrides
finals = {v["rule_id"]: v for p in P("final_verdict") for v in p.get("verdicts", [])}
approved = any(p.get("human_approved") for p in P("final_verdict"))
reopened = sorted({p.get("detection_id") for p in P("reopen")})
fmt = lambda a, nd=1: "n/a" if not a else f"{a['mean']:.{nd}f} ({a['min']:.{nd}f} to {a['max']:.{nd}f})"


def verdict_of(rid): return finals.get(rid, {}).get("verdict", "pending")
def thr_of(rid): return (finals.get(rid, {}).get("params") or {}).get("threshold")


# --- code-measured comparison over all seeds: baseline plan vs lab plan ---
lab_off = [r for r in base_dec if verdict_of(r) == "decommission"]
lab_th = {r: thr_of(r) for r in base_dec if verdict_of(r) == "retune" and thr_of(r) is not None}
hrs = lambda per: sum(v["alerts"] * RULES[r]["mins"] / 60 for r, v in per.items())
cmp = {"base": {"lost": [], "hours": []}, "lab": {"lost": [], "hours": []}}
for s in SEEDS:
    _, c0, _ = replay(s); nat0 = replay(s, "baseline")[0]  # coverage: campaign replay; hours: natural-prevalence window
    for key, kw in (("base", dict(disabled=base_dec)), ("lab", dict(disabled=lab_off, thresholds=lab_th))):
        _, c, _ = replay(s, **kw)
        cmp[key]["lost"].append(len(set(c0) - set(c))); cmp[key]["hours"].append(hrs(nat0) - hrs(replay(s, "baseline", **kw)[0]))
wrong = [(r, remove_res[r]["coverage_loss"]["seeds_with_loss"]) for r in base_dec
         if r in remove_res and remove_res[r]["coverage_loss"]["seeds_with_loss"] >= 1 and verdict_of(r) != "decommission"]

# --- citation verification: a quote counts only if it appears in the cached text of the fetched page ---
norm = lambda t: re.sub(r"\s+", " ", t.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def cite_status(c):
    if c.get("fetch_status") != "FETCHED": return "UNVERIFIED (fetch failed)"
    f = os.path.join(ROOT, "cache", "pages", hashlib.sha1(c.get("url", "").encode()).hexdigest() + ".txt")
    if c.get("supports") == "yes" and c.get("quote") and os.path.exists(f) and norm(c["quote"]) in norm(open(f).read()):
        return "SUPPORTED (quote found in fetched page)"
    return "NOT SUPPORTED (no verified quote)"


# --- timing from the record ---
ts0 = min(r["ts"] for r in recs)
t_q = next((r["ts"] for r in recs if r["stage"] == "question"), ts0)
t_safe = next((r["ts"] for r in recs if r["stage"] == "safety"), None)
t_fin = next((r["ts"] for r in recs if r["stage"] == "final_verdict"), None)
agent_of = {"evidence": "evidence", "hypothesis": "hypothesis", "experiment_plan": "planner", "result": "runner",
            "analysis": "analysis", "safety": "safety"}
spec_time = []
for i, r in enumerate(recs):
    to = agent_of.get(r["stage"])
    if not to: continue
    d = [x for x in recs[:i] if x["stage"] == "dispatch" and x["payload"].get("to") == to]
    start = d[-1]["ts"] if d else recs[i - 1]["ts"]
    spec_time.append((to, r["payload"].get("iteration", 1) if isinstance(r["payload"], dict) else 1, r["ts"] - start,
                      "dispatch record" if d else "gap from previous record"))
n_hyp = sum(len(p.get("hypotheses", [])) for p in P("hypothesis"))
n_exp = sum(x.get("n_experiments", 1) - 1 for x in P("result"))
loop_min = ((t_safe or recs[-1]["ts"]) - t_q) / 60

L = ["# Triage Lab Results (ALL DATA SYNTHETIC)", "",
     "**Question:** which detections can be decommissioned or retuned without losing true-positive coverage?", "",
     f"Record: {len(recs)} entries in `research_record.jsonl`. Human approval on final verdicts: "
     f"**{'granted' if approved else 'NOT recorded'}**. Every replay number below is the mean and (min to max) over "
     f"{N} fixed seeds ({SEEDS[0]} to {SEEDS[-1]}); no result rests on one seed.", "",
     "## Ranked verdicts (rule-only baseline vs lab)", "",
     "| Rank | ID | Detection | Baseline verdict | Baseline hours/mo | Seeds where removal loses coverage | Scenarios lost if removed (mean, range) | Lab final verdict | Hours recovered per month (natural-window mean) |",
     "|---|---|---|---|---|---|---|---|---|"]
for i, rid in enumerate(sorted(base_dec, key=lambda r: -base[r]["cost_hours"]), 1):
    x = remove_res.get(rid); cl = x["coverage_loss"] if x else None
    v = verdict_of(rid); th = thr_of(rid)
    rec_h = None
    if v == "decommission" and x: rec_h = x["hours_saved"]["mean"]
    if v == "retune" and rid in tighten_res:
        rec_h = next((s["hours_saved"]["mean"] for s in tighten_res[rid]["sweep"] if s["threshold"] == th), None)
    seeds_txt = "%d of %d" % (cl["seeds_with_loss"], N) if cl else "n/a"
    L.append(f"| {i} | {rid} | {base[rid]['name']} | decommission | {base[rid]['cost_hours']:.1f} | "
             f"{seeds_txt} | {fmt(cl['scenarios_lost'], 2) if cl else 'n/a'} | "
             f"{v}{f' (threshold {th})' if th is not None else ''} | {rec_h if rec_h is not None else 0:.1f} |")

L += ["", "## Measured improvement vs the rule-only baseline", "",
      f"| Metric ({N} seeds, mean and range; coverage from the attack-campaign replay, hours from natural-prevalence windows) | Baseline (rule-only) | Triage Lab |", "|---|---|---|",
      f"| Decommission verdicts | {len(base_dec)} | {len(lab_off)} |",
      f"| Attack scenarios left undetected by the verdicts, per seed | {fmt(agg(cmp['base']['lost']), 2)} | {fmt(agg(cmp['lab']['lost']), 2)} |",
      f"| Analyst hours recovered per month | {fmt(agg(cmp['base']['hours']))} | {fmt(agg(cmp['lab']['hours']))} |",
      f"| Wrongly decommissioned rules prevented (removal lost coverage in at least 1 seed) | 0 | {len(wrong)} of {len(base_dec)}: "
      f"{', '.join(f'{r} ({k}/{N} seeds)' for r, k in wrong) or 'none'} |",
      f"| Of those, robust (lost coverage in at least {N // 2} seeds) | n/a | "
      f"{', '.join(r for r, k in wrong if k >= N // 2) or 'none'} |", "",
      f"Nominal portfolio hours at stake for the baseline's {len(base_dec)} decommission verdicts: "
      f"{sum(base[r]['cost_hours'] for r in base_dec):.1f}h/month (alert volume x analyst minutes in the baseline window). "
      "The baseline recovers hours only by also disabling rules that carry coverage.", ""]

L += ["## Discovery acceleration (measured, no manual baseline assumed)", ""]
if t_safe:
    L.append(f"- Loop wall-clock, question to safety review (before the human approval step): **{loop_min:.1f} min**. "
             f"Through final verdict, including the human approval wait: {((t_fin or t_safe) - t_q) / 60:.1f} min.")
L.append(f"- Hypotheses evaluated: {n_hyp}; experiments run: {n_exp} (each aggregated over {N} seeds). "
         f"Throughput: {n_hyp / loop_min:.2f} hypotheses/min and {n_exp / loop_min:.2f} experiments/min over the loop.")
for p in P("result"):
    if "wall_seconds_parallel" in p:
        L.append(f"- Experiment stage (code): {p['n_experiments']} experiments took {p['wall_seconds_parallel']}s in parallel; "
                 f"the sum of their individual times (sequential equivalent) is {p['sum_experiment_seconds_sequential']}s.")
L += ["- Specialist (LLM) stages ran one after another because each needs the previous stage's output; only the experiment "
      "code parallelised. Observed per-stage time:", "", "| Specialist | Iteration | Seconds | Measured from |", "|---|---|---|---|"]
L += [f"| {a} | {it} | {sec:.0f} | {how} |" for a, it, sec, how in spec_time]
L += ["", "No manual-review comparison is stated: no manual baseline was measured in this project, and one would have to be "
      "an estimate with its own basis.", ""]

L += ["## Reconciling baseline stats with the replay (verified from the code)", "",
      "`data/portfolio.csv` is generated by `sim/make_portfolio.py` from a seeded 30-day baseline window that uses the same "
      "event generator as the replay. The two differ in attack prevalence: the baseline window has natural prevalence "
      "(see `baseline` in `sim/catalog.py`, zero insider scenarios), the replay is a campaign of "
      f"{REPLAY_N} instances of every behaviour template per seed. Analysts confirm a true-positive alert with probability "
      f"{C.CONFIRM_PROB['default']} ({C.CONFIRM_PROB['D031']} for the insider rule), and every alert is triaged in this model.", "",
      "| ID | Baseline alerts | Ground-truth TP alerts (baseline window) | Analyst-confirmed TP (portfolio.csv) | Replay TP alerts per seed (mean, range) |",
      "|---|---|---|---|---|"]
truth = {r["detection_id"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "portfolio_truth.csv")))}
for rid in sorted(base_dec):
    t = truth[rid]; tps = [replay(s)[0][rid]["tp"] for s in SEEDS]
    L.append(f"| {rid} | {t['baseline_alerts']} | {t['baseline_ground_truth_tp']} | {t['baseline_confirmed_tp']} | {fmt(agg(tps))} |")
L += ["", "What this shows, and what it does not:",
      "- Baseline-versus-replay TP differences come mainly from prevalence (a campaign has far more attacks than a quiet 30-day "
      "window), not from analyst under-labelling: ground truth and confirmed counts differ only by the confirmation probability.",
      "- The insider rule has zero baseline true positives because the baseline window contains zero insider scenarios "
      "(an assumption: such incidents are rare), so rule-based triage cannot see its value. That is the structural point of the case study.",
      "- An earlier version of this lab had a circularity defect: its unique-coverage scenarios were injected rule by rule, so the replay was guaranteed to find them, and its hand-written portfolio true-positive counts disagreed with the replay (0 versus 5 and 6). It was fixed by generating scenarios from behaviour templates that never mention a rule, deriving coverage by replay, and generating the portfolio from the same generator. This mismatch no longer exists.",
      "- Not tested: a hypothesis that real analysts leave low-volume alerts untriaged. This model triages every alert, so it cannot "
      "support or refute that.", ""]

d = "D031"
L += ["## Case study: departing-user sensitive data egress (D031)", ""]
x = remove_res.get(d)
if x:
    cl = x["coverage_loss"]
    L += [f"1. Baseline: decommission ({base[d]['tp']} confirmed TP in {base[d]['fires']} alerts, {base[d]['cost_hours']:.1f}h/month).",
          f"2. Experiment {x['experiment_id']} (remove): scenarios lost per seed {fmt(cl['scenarios_lost'], 1)}; coverage lost in "
          f"{cl['seeds_with_loss']} of {N} seeds; hours saved {fmt(x['hours_saved'], 1)}.",
          f"3. Behaviour templates that lost coverage (counts summed over seeds): {cl['behaviour_templates_lost_total_over_seeds']}. "
          f"Templates absent from this list were also detected by other rules (derived, not assumed).",
          f"4. Verdict reopened: {'yes (reopen entry in the record)' if d in reopened else 'not recorded'}."]
if d in tighten_res:
    L += ["5. Follow-up retune sweep (mean over seeds; TP retention shown as mean and minimum):", "",
          "| Threshold | TP retention mean (min) | Alert reduction mean | Hours saved mean | Scenarios lost max | Seeds with loss |",
          "|---|---|---|---|---|---|"]
    L += [f"| {s['threshold']} | {s['tp_retention']['mean']:.3f} ({s['tp_retention']['min']:.3f}) | {s['alert_reduction']['mean']:.3f} | "
          f"{s['hours_saved']['mean']:.2f} | {s['scenarios_lost']['max']:.0f} | {s['seeds_with_loss']} of {s['n_seeds']} |"
          for s in tighten_res[d]["sweep"]]
L += ["", f"Final {d} verdict: **{verdict_of(d)}** {finals.get(d, {}).get('params') or ''}", ""]

L += ["## Agent analyses and uncertainty", ""]
for p in P("analysis"):
    for a in p.get("analyses", []):
        L.append(f"- **{a.get('detection_id')}** (iteration {p.get('iteration')}): {a.get('verdict')} / {a.get('next_action')}, "
                 f"robustness {a.get('robustness')}. {a.get('interpretation', '')} *Uncertainty:* {a.get('uncertainty', '')}")
L += ["", "### Hypotheses (all AGENT-GENERATED)", ""]
for p in P("hypothesis"):
    for h in p.get("hypotheses", []):
        L.append(f"- {h.get('hypothesis_id')} [{h.get('label')}, confidence {h.get('confidence')}]: {h.get('claim')} "
                 f"*Uncertainty:* {h.get('uncertainty')}")
L += ["", "### Safety review", ""]
for p in P("safety"):
    for r in p.get("reviews", []):
        L.append(f"- {r.get('detection_id')}: {r.get('decision')} (risk {r.get('risk')}); flags {r.get('flags')}; rollback: {r.get('rollback')}")

L += ["", "## Citations (a citation counts only if its quote is found in the fetched page)", ""]
for p in P("evidence"):
    for e in p.get("evidence", []):
        sup = [(cl.get("claim"), c, cite_status(c)) for cl in e.get("claims", []) for c in cl.get("citations", [])]
        good = [t for t in sup if t[2].startswith("SUPPORTED")]
        L.append(f"- **{e.get('detection_id')}** ({', '.join(e.get('techniques', []))}): "
                 + ("" if good else "**No supporting evidence found.** ") + f"{e.get('note', '')}")
        for claim, c, st in sup:
            L.append(f"  - {st}: [{c.get('url')}]({c.get('url')}) for claim \"{claim}\"" +
                     (f"; quote: \"{c.get('quote')}\"" if st.startswith("SUPPORTED") else ""))
L += ["", "## Controls and caveats", ""]
if control:
    L.append(f"- Controls over {control.get('n_seeds')} seeds: no-op replay identical = {control.get('noop_identical_all_seeds')}; "
             f"disabling every rule detects zero scenarios = {control.get('disable_all_detects_zero')}; generation deterministic = "
             f"{control.get('deterministic')}. Baseline scenario recall {fmt(control.get('baseline_scenario_recall'), 3)}, "
             f"scenarios no rule detects per seed {fmt(control.get('undetected_scenarios_baseline'), 2)} of {control.get('n_scenarios')}.")
L += ["- Baseline comparison: every experiment is measured against the all-rules-enabled replay of the same seed.",
      "- Scenarios come from behaviour templates written without reference to any rule; coverage is derived by replay. Modelling "
      "assumptions that remain: attack-step magnitudes are drawn from distributions more intense than benign ones, and no rule "
      "other than D021 and D031 reads proxy, DLP, USB or mail-gateway telemetry. Results validate the method, not real-world coverage.",
      "- Synthetic data throughout; agent hypotheses are AGENT-GENERATED and unreviewed until a human approves."]
open(os.path.join(ROOT, "report.md"), "w").write("\n".join(L) + "\n")
print(f"report.md written ({len(recs)} records)")
