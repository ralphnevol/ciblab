"""Cyber Research Lab — Fuzzing Discovery Runner.

Start the web application or run a live interactive demonstration of the
automated scientific discovery loop.

Usage:
    python run.py                # Inicia el servidor web interactivo (http://127.0.0.1:8000)
    python run.py --interactive  # Ejecuta la prueba en tiempo real con pausas y control humano
    python run.py --demo         # Ejecuta la prueba rápida automatizada
    python run.py --help         # Muestra esta ayuda
"""

import sys
import time
import uvicorn

# Ensure utf-8 encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.orchestration.omnigent_adapter import detect_omnigent
from app.orchestration.fuzz_lab import (
    DEFAULT_TARGET,
    approve_and_triage,
    start_fuzz_run,
    FUZZ_RUNS,
)


def run_interactive():
    print("\n" + "=" * 70)
    print(" 🧪 AGENTIC FUZZING LAB — PRUEBA EN TIEMPO REAL (HUMAN-IN-THE-LOOP)")
    print("=" * 70)

    omni_status = detect_omnigent()
    print(f"[*] Omnigent Runtime:   {omni_status['mode']} (v{omni_status.get('version', 'unknown')})")
    print("[*] Modelo LLM:         GPT-6 Luna (OpenAI)")
    print(f"[*] Objetivo:           {DEFAULT_TARGET.name}")
    print("[*] Formato de entrada: stdin (Buffer C sin verificación de límites)\n")

    input("👉 Presioná ENTER para iniciar la Fase 1 y 2 (Pregunta & Hipótesis)... ")

    print("\n" + "-" * 70)
    print("🧠 FASE 1 & 2: PREGUNTA CIENTÍFICA E HIPÓTESIS")
    print("-" * 70)
    print("[*] Enviando descripción del parser al Seed Agent (GPT-6 Luna)...")

    run_id = start_fuzz_run(
        question="¿Qué inputs específicos causan corrupción de memoria o crashes en este parser?",
        seed=42,
    )
    run = FUZZ_RUNS[run_id]

    # Buscar evento de hipótesis
    hyp_event = next((e for e in run.events if e.action == "hypothesis_and_corpus"), None)
    if hyp_event:
        print(f"\n💡 Hipótesis generada por GPT-6 Luna:")
        print(f'   "{hyp_event.output["hypothesis"]}"')
        print(f"\n📦 Corpus inicial de semillas generado:")
        for strat in hyp_event.output.get("seed_strategies", []):
            print(f"   • Semilla mutada: {strat}")

    print("\n" + "-" * 70)
    print("⚖️  FASE 3: PLANIFICACIÓN Y EXPERIMENTO DE FUZZING")
    print("-" * 70)
    plan_event = next((e for e in run.events if e.action == "experiment_selection"), None)
    if plan_event:
        print(f"[*] Planner evaluó los experimentos candidatos:")
        for c in plan_event.output.get("candidates", []):
            print(f"    - {c['id']} (Estrategia: {c['strategy']}, Prioridad: {c['priority']:.2f})")
        print(f"[*] Decisión del Planner: Seleccionado '{plan_event.output.get('selected')}'")

    print("\n[*] Execution Agent ejecutando mutaciones y pruebas contra el parser en sandbox...")
    for round_num in range(1, 4):
        time.sleep(0.3)
        print(f"    [Ronda {round_num}/3] Aplicando bitflips, null-bytes e inyecciones de formato...")

    print(f"\n💥 ¡CRASHES DETECTADOS! Total de fallos únicos observados: {run.crash_count}")

    print("\n" + "=" * 70)
    print("🛑 FASE 4: CONTROL DE SEGURIDAD Y POLÍTICA OMNIGENT")
    print("=" * 70)
    print("[!] POLÍTICA: require_human_approval_on_crash")
    print(f"[!] Se encontraron {run.crash_count} condiciones de fallo de memoria en el parser.")
    print("[!] Omnigent interrumpió el flujo para evitar consumo de cómputo innecesario.")
    
    resp = input("\n👉 ¿Aprobás como Científico Principal la reproducción y triaje? [S/n]: ").strip().lower()
    approved = resp not in ("n", "no")

    if not approved:
        print("[-] Operación rechazada por el humano. Experimento abortado.")
        approve_and_triage(run_id, approved=False)
        return

    print("[✓] Aprobación humana concedida. Desbloqueando Triage Agent...")

    print("\n" + "-" * 70)
    print("🔬 FASE 5: TRIAJE, REPRODUCCIÓN Y DECISIÓN ACTUALIZADA")
    print("-" * 70)
    print("[*] Triage Agent reproduciendo cada crash de forma determinística...")
    print("[*] Sintetizando taxonomía CWE y conclusiones con GPT-6 Luna...")

    discovery = approve_and_triage(run_id, approved=True)

    if discovery:
        print(f"\n[🏆] ¿Hipótesis confirmada?: {'SÍ (Confirmada)' if discovery.hypothesis_confirmed else 'NO'}")
        print(f"[+] Fallos únicos reproducidos: {discovery.crashes_found}")
        print(f"[+] Factor de aceleración vs análisis manual: {discovery.speedup_vs_manual:,.1f}x")

        print("\n[+] Taxonomía de Vulnerabilidades (CWE):")
        unique_cwes = {}
        for t in discovery.triage_results:
            key = f"{t.cwe_id} ({t.cwe_name})"
            unique_cwes[key] = unique_cwes.get(key, 0) + 1
        for cwe, count in unique_cwes.items():
            print(f"    • {cwe}: {count} ocurrencias confirmadas")

        print(f"\n[+] Adaptación para el siguiente ciclo (Bucle Científico):\n    {discovery.adaptation_event}")
        print(f"\n[+] Conclusión Científica Consolidada (GPT-6 Luna):\n    {discovery.scientific_conclusion}")

    print("\n" + "=" * 70)
    print(" ✅ CICLO CIENTÍFICO COMPLETADO EXITOSAMENTE")
    print("=" * 70 + "\n")


def run_demo():
    print("\n" + "=" * 65)
    print(" 🧪 AGENTIC FUZZING LAB — SCIENTIFIC DISCOVERY DEMO")
    print("=" * 65)

    omni_status = detect_omnigent()
    print(f"[*] Omnigent Runtime: {omni_status['mode']} (v{omni_status.get('version', 'unknown')})")
    print("[*] Model: GPT-6 Luna (OpenAI)")

    print("\n--- FASE 1 & 2: Pregunta, Evidencia e Hipótesis ---")
    run_id = start_fuzz_run(
        question="¿Qué inputs específicos causan corrupción de memoria o crashes en este parser?",
        seed=42,
    )
    run = FUZZ_RUNS[run_id]
    print(f"[+] Run iniciado: {run_id}")
    hyp_event = next((e for e in run.events if e.action == "hypothesis_and_corpus"), None)
    if hyp_event:
        print(f"[+] Hipótesis (GPT-6 Luna): {hyp_event.output['hypothesis']}")

    print("\n--- FASE 3: Experimento & Planificación ---")
    print(f"[+] Crashes encontrados: {run.crash_count}")

    print("\n--- FASE 4: Gate de Aprobación Humana (Omnigent Policy) ---")
    print("[🛑] Crashes detectados. Simulando aprobación humana...")

    print("\n--- FASE 5: Triaje, CWE y Decisión Actualizada ---")
    discovery = approve_and_triage(run_id, approved=True)

    if discovery:
        print(f"[🏆] Hipótesis confirmada: {discovery.hypothesis_confirmed}")
        print(f"[+] Crashes únicos: {discovery.crashes_found}")
        print(f"[+] Aceleración vs manual: {discovery.speedup_vs_manual:,.1f}x")
        print(f"[+] Conclusión: {discovery.scientific_conclusion}")
    print("\n" + "=" * 65 + "\n")


def start_server():
    print("\n" + "=" * 65)
    print(" 🧪 Cyber Research Lab — Fuzzing Discovery")
    print("=" * 65)
    omni = detect_omnigent()
    print(f"[*] Omnigent: {omni['mode']} (v{omni.get('version', 'unknown')})")
    print("[*] Modelo LLM: GPT-6 Luna")
    print("[*] Servidor web disponible en: http://127.0.0.1:8000")
    print("[*] Documentación OpenAPI:      http://127.0.0.1:8000/docs")
    print("[*] Presioná Ctrl+C para detener el servidor.\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


def run_omnigent(agent_name="seed-agent"):
    """Launch an agent through the native Omnigent runtime."""
    import os
    import subprocess
    from dotenv import load_dotenv

    load_dotenv()
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    agent_dir = f"omnigent/agents/{agent_name}"
    if not os.path.isdir(agent_dir):
        print(f"\n[!] Error: Agente '{agent_name}' no encontrado en omnigent/agents/")
        print("    Agentes disponibles: seed-agent, fuzz-orchestrator, execution-agent, safety-agent, triage-agent\n")
        return

    print("\n" + "=" * 65)
    print(f" 🚀 OMNIGENT NATIVE RUNNER — {agent_name.upper()}")
    print("=" * 65)
    print("[*] Levantando/verificando servidor Omnigent en http://127.0.0.1:6767...")
    subprocess.run([sys.executable, "-m", "omnigent", "server", "--background"], env=env)

    print(f"[*] Conectando sesión REPL con el agente en '{agent_dir}'...")
    print("[*] Presioná Ctrl+C para salir de la sesión interactiva.\n")
    subprocess.run(
        [sys.executable, "-m", "omnigent", "run", f"{agent_dir}/", "--server", "http://127.0.0.1:6767"],
        env=env,
    )


def register_agents():
    """Registra los 5 agentes del laboratorio en el store persistente de Omnigent."""
    import pathlib
    try:
        import omnigent.cli as c
        import omnigent.host.local_server as ls
        import omnigent.stores.agent_store.sqlalchemy_store as a
        import omnigent.runtime.agent_cache as ac

        d = ls._local_data_dir()
        db = f"sqlite:///{d}/chat.db"
        store = a.SqlAlchemyAgentStore(db, db)
        arts = c._create_artifact_store(str(d / "artifacts"))
        cache = ac.AgentCache(arts, d / "cache")

        agents = [
            "omnigent/agents/fuzz-orchestrator",
            "omnigent/agents/seed-agent",
            "omnigent/agents/execution-agent",
            "omnigent/agents/safety-agent",
            "omnigent/agents/triage-agent",
        ]
        print("\n" + "=" * 65)
        print(" 📦 REGISTRANDO AGENTES EN OMNIGENT STORE")
        print("=" * 65)
        for p in agents:
            c._preregister_agent(pathlib.Path(p), store, arts, cache)
        print("[✓] ¡Los 5 agentes están registrados y listos para la UI en http://127.0.0.1:6767!\n")
    except Exception as e:
        print(f"[!] Error registrando agentes: {e}")


if __name__ == "__main__":
    if "--omni" in sys.argv:
        idx = sys.argv.index("--omni")
        target_agent = sys.argv[idx + 1] if len(sys.argv) > idx + 1 and not sys.argv[idx + 1].startswith("-") else "seed-agent"
        run_omnigent(target_agent)
    elif "--register" in sys.argv:
        register_agents()
    elif "--interactive" in sys.argv or "-i" in sys.argv:
        run_interactive()
    elif "--demo" in sys.argv:
        run_demo()
    else:
        start_server()
