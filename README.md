# Triage Lab

A small research project for a security hackathon. **All data is synthetic** (made up). No real company, person or system is involved.

## The problem, in plain words

Security teams get thousands of alerts a month from "detection rules". Some rules are very noisy and waste analysts' time. The usual fix is simple: if a rule almost never finds a real attack, switch it off.

That fix has a flaw. Some rules are *quiet* but are the only thing that would catch a rare, serious attack. Our example is a rule that spots an employee who is leaving and copies sensitive files to personal cloud storage, personal email or a USB drive. It rarely fires and nobody has ever confirmed a hit, so a simple rule says "switch it off". But it might be the only protection against that kind of data theft.

**Our question:** which rules can we switch off or tune down without losing real protection?

## What we built

1. **A simple baseline** (`baseline/`). It switches off any rule with very few real hits. This is what we compare against.
2. **A team of six AI agents** running on [Omnigent](https://github.com/omnigent-ai/omnigent). Each does one job:
   - *Evidence*: looks for public sources (like MITRE ATT&CK) and quotes them.
   - *Hypothesis*: writes a testable guess, such as "switching off rule X loses nothing".
   - *Planner*: picks an experiment to test the guess.
   - *Runner*: runs the experiment with real code.
   - *Analysis*: says whether the guess held up.
   - *Safety*: flags risks and asks a human to approve.
3. **A simulator** (`sim/`). It makes fake attack scenarios, replays them against the rules, and checks which rules catch what. It runs on 20 different random seeds, so no result depends on one lucky run.
4. **Guardrails**: a human must approve the final decisions, and there is a spending limit.

Every message between agents is saved in `research_record.jsonl`, so every decision can be traced.

## What happened

| | Simple rule | Triage Lab |
|---|---|---|
| Rules switched off | 11 | 3 |
| Attack scenarios no longer detected (average per run) | 30.3 | 0 |
| Analyst hours saved per month | 846 | 335 |

- The simple rule would have switched off 11 rules. For 8 of them, switching off loses protection in at least one of the 20 test runs. Only 2 of those 8 lose protection in most runs (a proxy rule and the leaving-employee rule).
- Removing the leaving-employee rule would lose about 23 attack scenarios per run, in all 20 runs. The final decision keeps the rule and only trims it slightly.
- The lab switched off 3 rules, tuned 2, kept 1, and left 5 for a person to investigate.
- The whole loop took about 12 minutes, and a human approved the final decisions.
- The simple rule saves more hours, but only because it also switches off rules that protect against attacks.

Full details, tables and sources are in `report.md`.

## What went wrong on the way (and how we fixed it)

- Our first version planted the "special" attack scenarios for specific rules, so the test was guaranteed to find them. We rebuilt it so scenarios are created without knowing about the rules.
- The first citations said "verified" but supported nothing. Now a citation only counts if its exact quote is found on the page.
- The first run used a single random seed. Now everything runs on 20 seeds and results show an average and a range.
- The first run could not finish unattended, because the agents need an interactive session to receive each other's replies. See `KICKOFF.md`.

## What to read

| File | What it is |
|---|---|
| `report.md` | The results of the run: tables, sources, uncertainty |
| `research_record.jsonl` | Every handoff between agents |
| `KICKOFF.md` | How to run the full loop yourself |
| `config.yaml`, `agents/` | The agent specifications and policies (one folder per agent, with its tools) |
| `sim/`, `run_experiments.py`, `build_report.py` | The experiment code |
| `baseline/` | The simple rule used for the comparison |
| `data/` | The made-up portfolio of 30 rules |

## How the loop works

Question, then evidence, hypothesis, experiment plan, experiment, result, analysis, and a decision. If an experiment shows a rule is needed, the earlier "switch it off" verdict is reopened and the agents test a gentler fix (raising the rule's threshold). Each agent hands the next one a small JSON message, and every message is logged. A safety agent reviews, and a human approves before anything is final.

## What we would test next

1. Replace the made-up attack strengths with replays of real, labelled incidents, to see if the leaving-employee rule's value holds up.
2. Give that rule richer signals (days until departure, how sensitive the repository is, what is normal for the person's team) instead of a single threshold.
3. Weigh each lost attack scenario by how much damage it could do, so saved hours are compared fairly with risk.
4. Study the rules that lose protection in only some runs, and write a narrower rule for those cases.

## Limits

The data is made up and the numbers show that the method works, not how a real company would fare. Agent guesses are labelled as AI-generated and were reviewed by a human only at the final approval step.
