"""Cyber Research Lab — Fuzzing Discovery Runner.

Start the web application or run a quick terminal demonstration of the
automated scientific discovery loop.

Usage:
    python run.py           # Starts the web server (http://127.0.0.1:8000)
    python run.py --demo    # Runs the complete scientific method loop in terminal
    python run.py --help    # Shows this help
"""

import sys
import uvicorn

# Ensure utf-8 encoding on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.orchestration.omnigent_adapter import detect_omnigent


def run_demo():
    print("\n" + "=" * 65)
    print(" 🧪 AGENTIC FUZZING LAB — SCIENTIFIC DISCOVERY DEMO")
    print("=" * 65)

    omni_status = detect_omnigent()
    print(f"[*] Omnigent Runtime: {omni_status['mode']} (v{omni_status.get('version', 'unknown')})")
    print("[*] Model: gpt-6-luna")

    from app.orchestration.fuzz_lab import start_fuzz_run, approve_and_triage

    print("\n--- FASE 1 & 2: Pregunta, Evidencia e Hipótesis ---")
    run_id = start_fuzz_run(
        question="¿Qué inputs específicos causan corrupción de memoria o crashes en este parser?",
        seed=42,
    )
    print(f"[+] Run iniciado: {run_id}")
    print("[+] Seed Agent formuló la hipótesis y generó el corpus de semillas mutadas.")

    print("\n--- FASE 3: Experimento & Planificación ---")
    print("[+] Planner evaluó 2 experimentos candidatos y seleccionó el de mayor aprendizaje esperado.")
    print("[+] Execution Agent corrió las pruebas contra el parser sintético.")

    print("\n--- FASE 4: Gate de Aprobación Humana (Omnigent Policy) ---")
    print("[🛑] Crashes detectados. Omnigent detiene la ejecución para pedir aprobación humana.")
    print("[✓] Simulando aprobación humana...")

    print("\n--- FASE 5: Triaje, CWE y Decisión Actualizada ---")
    discovery = approve_and_triage(run_id, approved=True)

    if discovery:
        print(f"[🏆] Hipótesis confirmada: {discovery.hypothesis_confirmed}")
        print(f"[+] Crashes únicos encontrados: {discovery.crashes_found}")
        print(f"[+] Aceleración vs análisis manual: {discovery.speedup_vs_manual}x")
        print("\n[+] Taxonomía de Vulnerabilidades (CWE):")
        for t in discovery.triage_results:
            print(f"    • {t.cwe_id} ({t.cwe_name}) — Severidad: {t.severity}")
        print(f"\n[+] Adaptación para el siguiente ciclo:\n    {discovery.adaptation_event}")
        print(f"\n[+] Conclusión Científica:\n    {discovery.scientific_conclusion}")
    print("\n" + "=" * 65 + "\n")


def start_server():
    print("\n" + "=" * 65)
    print(" 🧪 Cyber Research Lab — Fuzzing Discovery")
    print("=" * 65)
    omni = detect_omnigent()
    print(f"[*] Omnigent: {omni['mode']} (v{omni.get('version', 'unknown')})")
    print("[*] Servidor web disponible en: http://127.0.0.1:8000")
    print("[*] Documentación OpenAPI:      http://127.0.0.1:8000/docs")
    print("[*] Presioná Ctrl+C para detener el servidor.\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    if "--demo" in sys.argv:
        run_demo()
    else:
        start_server()
