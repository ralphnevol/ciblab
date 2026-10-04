# KICKOFF: run the full Triage Lab loop interactively

All data is synthetic. This is the run that produces `research_record.jsonl` and `report.md`. Two headless attempts
failed (headless `-p` runs exit when the orchestrator's first turn ends) because the orchestrator relies
on the interactive runtime to wake on the inbox when a specialist finishes. Run it in a live terminal session.

## Before you start

- Nothing to install or log in to. `omnigent config list` shows the Claude subscription as the default
  credential, and the local server answers on `127.0.0.1:6767`.
- `research_record.jsonl` and `report.md` must not exist yet (the top level is clean). If a previous run left them
  there, move them aside first.

## 1. Start the session (no `-p`)

```bash
cd ~/hack-nation/triage-lab
omnigent run .
```

The terminal prints a line like `Omnigent session: http://127.0.0.1:6767/c/<id>` and opens the REPL. Keep this
terminal open for the whole run. Do not quit when the orchestrator says it is "waiting for the inbox": that is the
design, and the specialists' replies wake it automatically.

## 2. Paste this kickoff message into the REPL

```text
Run the Triage Lab discovery loop now, following your instructions exactly. All data is synthetic.
```

## 3. Approve the final verdicts

At step 8 the orchestrator calls `finalize_verdict` once. The Omnigent policy `human_approval_on_final_verdicts`
returns ASK, so the run pauses with an approval request for that call. It should appear in the REPL. The session
URL printed at start is the web UI for the same session, so you can also look there. Review the verdict list in the
request (it should show D031, the insider-risk rule, with a non-decommission verdict if the experiment refuted its
decommission, plus the verdicts for the other 10 candidates, and the safety agent's flags in `research_record.jsonl`), then approve or deny. If you deny, the orchestrator is told to
record the denial and stop, and `report.md` will show `pending` for the verdicts.

Approval times out after 3600 seconds (`ask_timeout` in `config.yaml`). The `cost_budget` policy also asks you at
USD 3 and 6 of session spend and hard-stops at USD 10.

## 4. After the run

The orchestrator calls `build_report` at the end. If `report.md` is missing, run it yourself:

```bash
python3 build_report.py
```

Then read `report.md` for the results.

## Watching progress from a second terminal

```bash
cd ~/hack-nation/triage-lab
watch -n 5 'python3 -c "import json;[print(r[\"seq\"],r[\"stage\"],r[\"agent\"]) for r in map(json.loads,open(\"research_record.jsonl\"))]"'
```

(`watch` is not installed on macOS by default; `brew install watch`, or rerun the python one-liner by hand.)

Expected record order: question, then a `dispatch` record before each specialist (used to time them), evidence,
hypothesis, experiment_plan, result, analysis, then (if a remove experiment shows coverage loss) reopen, hypothesis,
experiment_plan, result, analysis for iteration 2, then safety, then final_verdict. The baseline has 11 decommission
candidates, so expect more records than the earlier 8-candidate run. The evidence agent also writes fetched page
text to `cache/pages/`; `build_report.py` uses it to check every quote.
