"""
Pokemon Pipeline — Orquestador principal
Ejecuta: Extract -> Transform -> Validate -> Load
Con manejo de errores, logging y reporte final
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# ─── LOGGING ─────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
log = logging.getLogger("pokemon.pipeline")

sys.path.insert(0, str(Path(__file__).parent))

from src.extract import extract_all
from src.transform import transform_all
from src.validate import validate_all
from src.load import load_all


# ─── PIPELINE ────────────────────────────────────────────────────────────────

def run_pipeline(fail_on_validation: bool = False) -> dict:
    """
    Ejecuta el pipeline completo E->T->V->L.

    Args:
        fail_on_validation: si True, detiene el pipeline si la validación falla
    """
    start = time.time()
    log.info("Iniciando pipeline Pokemon ETL")

    result = {
        "status":     "running",
        "started_at": datetime.now().isoformat(),
        "steps":      {}
    }

    # ── STEP 1: EXTRACT ───────────────────────────────────────────────────────
    try:
        log.info("\n--- STEP 1: EXTRACT ---")
        t0  = time.time()
        raw = extract_all()
        result["steps"]["extract"] = {
            "status":       "ok",
            "duration_sec": round(time.time() - t0, 2),
            "records":      {k: len(v) for k, v in raw.items()}
        }
        log.info(f"Extract completado en {result['steps']['extract']['duration_sec']}s")
    except Exception as e:
        log.error(f"Extract fallo: {e}")
        result["status"] = "failed"
        result["steps"]["extract"] = {"status": "failed", "error": str(e)}
        _print_summary(result, time.time() - start)
        return result

    # ── STEP 2: TRANSFORM ─────────────────────────────────────────────────────
    try:
        log.info("\n--- STEP 2: TRANSFORM ---")
        t0          = time.time()
        transformed = transform_all(raw)
        result["steps"]["transform"] = {
            "status":       "ok",
            "duration_sec": round(time.time() - t0, 2),
            "tables":       {k: len(v) for k, v in transformed.items()}
        }
        log.info(f"Transform completado en {result['steps']['transform']['duration_sec']}s")
    except Exception as e:
        log.error(f"Transform fallo: {e}")
        result["status"] = "failed"
        result["steps"]["transform"] = {"status": "failed", "error": str(e)}
        _print_summary(result, time.time() - start)
        return result

    # ── STEP 3: VALIDATE ──────────────────────────────────────────────────────
    try:
        log.info("\n--- STEP 3: VALIDATE ---")
        t0             = time.time()
        validation_ok  = validate_all(transformed)
        result["steps"]["validate"] = {
            "status":       "ok" if validation_ok else "warnings",
            "duration_sec": round(time.time() - t0, 2),
            "passed":       validation_ok
        }
        if not validation_ok and fail_on_validation:
            log.error("Validacion fallo — pipeline detenido (fail_on_validation=True)")
            result["status"] = "failed"
            _print_summary(result, time.time() - start)
            return result
        log.info(f"Validate completado en {result['steps']['validate']['duration_sec']}s")
    except Exception as e:
        log.error(f"Validate fallo: {e}")
        result["steps"]["validate"] = {"status": "failed", "error": str(e)}

    # ── STEP 4: LOAD ──────────────────────────────────────────────────────────
    try:
        log.info("\n--- STEP 4: LOAD ---")
        t0           = time.time()
        load_results = load_all(transformed)
        result["steps"]["load"] = {
            "status":       "ok" if all(load_results.values()) else "partial",
            "duration_sec": round(time.time() - t0, 2),
            "targets":      load_results
        }
        log.info(f"Load completado en {result['steps']['load']['duration_sec']}s")
    except Exception as e:
        log.error(f"Load fallo: {e}")
        result["steps"]["load"] = {"status": "failed", "error": str(e)}

    # ── RESUMEN FINAL ─────────────────────────────────────────────────────────
    result["status"]      = "completed"
    result["finished_at"] = datetime.now().isoformat()
    _print_summary(result, time.time() - start)

    return result


def _print_summary(result: dict, total_sec: float):
    print("\n" + "=" * 60)
    print("  PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Status  : {result['status'].upper()}")
    print(f"  Duracion: {round(total_sec, 2)}s")
    print()
    for step, info in result.get("steps", {}).items():
        status   = info.get("status", "?")
        icon     = "OK" if status == "ok" else ("WARN" if status == "warnings" else "FAIL")
        duration = f"{info.get('duration_sec', '?')}s" if "duration_sec" in info else ""
        print(f"  [{icon}] {step:<12} {duration}")
    print("=" * 60)


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pokemon ETL Pipeline")
    parser.add_argument("--fail-on-validation", action="store_true",
                        help="Detener pipeline si la validacion falla")
    args = parser.parse_args()

    result = run_pipeline(fail_on_validation=args.fail_on_validation)
    sys.exit(0 if result["status"] == "completed" else 1)
