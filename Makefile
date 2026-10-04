.PHONY: test run agentic-run

test:
	pytest -q

run:
	uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Needs `make run` in another terminal, plus `omni login` / `omni setup` done once.
agentic-run:
	@RUN_ID=$$(curl -fsS -X POST localhost:8000/agentic-runs | python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])') && \
	echo "lab run $$RUN_ID" && \
	omnigent run omnigent/triage_lab -p "Triage every detection in lab run $$RUN_ID$${DETECTIONS:+ (only $$DETECTIONS)}"
