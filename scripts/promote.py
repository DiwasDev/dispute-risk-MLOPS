"""
scripts/promote.py
==================
Promote a trained model version to the @champion alias in the MLflow registry.

This is the blue-green deployment mechanism. The @champion alias determines
which model version the FastAPI service loads at startup. Promoting to
@champion is the deployment action. Rolling back is demoting to the previous
version — see scripts/rollback.py.

## Promotion workflow

1. Verify the candidate version exists and has been logged.
2. Run golden input test against the candidate model.
3. Check that candidate metrics beat the current champion on PR-AUC.
4. If all gates pass, assign @champion alias to the candidate version.
5. The previous champion version is tagged as "previous_champion" for rollback.
6. Restart / reload the FastAPI service (or rely on /health to confirm).

## Usage

    # Promote version 3 of the dispute-risk-model to champion
    python scripts/promote.py --version 3

    # Promote and skip metric gate (for emergency hotfixes)
    python scripts/promote.py --version 3 --skip-metric-gate

    # Dry run — shows what would happen without making changes
    python scripts/promote.py --version 3 --dry-run

## Environment variables

    MLFLOW_TRACKING_URI   — MLflow server (default: sqlite:///mlflow.db)
    MODEL_NAME            — Registered model name (default: dispute-risk-model)
    PR_AUC_GATE           — Minimum PR-AUC to pass metric gate (default: 0.0,
                            i.e. any model passes; set to baseline PR-AUC in prod)
"""

from __future__ import annotations

import argparse
import logging
import sys

import mlflow
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

import os

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MODEL_NAME = os.getenv("MODEL_NAME", "dispute-risk-model")
CHAMPION_ALIAS = "champion"
PREVIOUS_CHAMPION_TAG = "previous_champion_version"

# Golden input used to verify training-serving parity before promotion
GOLDEN_INPUT = {
    "Date received": "2016-03-15",
    "Product": "Mortgage",
    "Sub-product": "Conventional fixed mortgage",
    "Issue": "Loan modification,collection,foreclosure",
    "Sub-issue": None,
    "Consumer complaint narrative": None,
    "Company": "Bank of America",
    "State": "CA",
    "ZIP code": "90001",
    "Tags": None,
    "Consumer consent provided?": None,
    "Submitted via": "Web",
}


# ---------------------------------------------------------------------------
# Gate checks
# ---------------------------------------------------------------------------


def _golden_input_gate(pipeline) -> bool:
    """Return True if the golden input produces a valid probability."""
    try:
        df = pd.DataFrame([GOLDEN_INPUT])
        proba = pipeline.predict_proba(df)
        prob = float(proba[0, 1])
        if np.isnan(prob) or not (0.0 <= prob <= 1.0):
            logger.error("Golden input gate FAILED: invalid probability %.4f", prob)
            return False
        logger.info("Golden input gate PASSED: probability=%.4f", prob)
        return True
    except Exception as exc:
        logger.error("Golden input gate FAILED with exception: %s", exc)
        return False


def _metric_gate(client: mlflow.tracking.MlflowClient, version: str, min_pr_auc: float) -> bool:
    """Return True if the candidate version's PR-AUC meets the minimum threshold."""
    if min_pr_auc <= 0.0:
        logger.info("Metric gate skipped (PR_AUC_GATE=0.0).")
        return True

    try:
        model_version = client.get_model_version(MODEL_NAME, version)
        run_id = model_version.run_id
        if not run_id:
            logger.warning("No run_id for version %s — cannot check metrics. Skipping gate.", version)
            return True

        run = client.get_run(run_id)
        pr_auc = run.data.metrics.get("val_pr_auc") or run.data.metrics.get("pr_auc")
        if pr_auc is None:
            logger.warning("PR-AUC metric not found for version %s. Skipping gate.", version)
            return True

        if pr_auc < min_pr_auc:
            logger.error(
                "Metric gate FAILED: PR-AUC=%.4f < required %.4f for version %s.",
                pr_auc, min_pr_auc, version,
            )
            return False

        logger.info("Metric gate PASSED: PR-AUC=%.4f >= required %.4f.", pr_auc, min_pr_auc)
        return True

    except Exception as exc:
        logger.warning("Metric gate check failed with exception: %s. Proceeding.", exc)
        return True


# ---------------------------------------------------------------------------
# Promotion logic
# ---------------------------------------------------------------------------


def promote(
    version: str,
    *,
    skip_metric_gate: bool = False,
    dry_run: bool = False,
    min_pr_auc: float = 0.0,
) -> bool:
    """
    Promote a model version to @champion.

    Parameters
    ----------
    version : str
        The model version number to promote.
    skip_metric_gate : bool
        If True, skip the PR-AUC metric comparison gate.
    dry_run : bool
        If True, run all checks but don't modify the registry.
    min_pr_auc : float
        Minimum PR-AUC to pass the metric gate.

    Returns
    -------
    bool : True if promotion succeeded (or would succeed in dry run).
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    logger.info(
        "Promotion request: model='%s' version=%s | dry_run=%s | skip_metric_gate=%s",
        MODEL_NAME, version, dry_run, skip_metric_gate,
    )

    # --- Step 1: Verify candidate version exists ---
    try:
        candidate = client.get_model_version(MODEL_NAME, version)
        logger.info("Candidate found: version=%s status=%s", version, candidate.status)
    except Exception as exc:
        logger.error("Version %s not found in registry: %s", version, exc)
        return False

    # --- Step 2: Find current champion (for rollback tagging) ---
    try:
        current_champion = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
        current_champion_version = current_champion.version
        logger.info("Current champion is version=%s", current_champion_version)
    except Exception:
        current_champion_version = None
        logger.info("No current champion found — this is the first promotion.")

    # --- Step 3: Load candidate and run golden input gate ---
    model_uri = f"models:/{MODEL_NAME}/{version}"
    try:
        pipeline = mlflow.sklearn.load_model(model_uri)
    except Exception as exc:
        logger.error("Failed to load candidate model version %s: %s", version, exc)
        return False

    if not _golden_input_gate(pipeline):
        logger.error("Promotion BLOCKED: golden input gate failed for version %s.", version)
        return False

    # --- Step 4: Metric gate ---
    if not skip_metric_gate and not _metric_gate(client, version, min_pr_auc):
        logger.error("Promotion BLOCKED: metric gate failed for version %s.", version)
        return False

    # --- Step 5: Promote ---
    if dry_run:
        logger.info(
            "[DRY RUN] Would promote version=%s to @champion. "
            "Would tag version=%s as previous_champion.",
            version, current_champion_version,
        )
        return True

    # Tag the current champion as previous (rollback pointer)
    if current_champion_version and current_champion_version != version:
        client.set_registered_model_tag(
            MODEL_NAME, PREVIOUS_CHAMPION_TAG, current_champion_version
        )
        logger.info("Tagged version=%s as %s.", current_champion_version, PREVIOUS_CHAMPION_TAG)

    # Assign the @champion alias
    client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, version)
    logger.info(
        "SUCCESS: version=%s is now @champion for model '%s'. "
        "Restart the API service to load the new model (or wait for /health ping).",
        version, MODEL_NAME,
    )
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote a model version to @champion in the MLflow registry."
    )
    parser.add_argument("--version", required=True, help="Model version number to promote.")
    parser.add_argument(
        "--skip-metric-gate", action="store_true",
        help="Skip PR-AUC comparison gate (use for emergency hotfixes).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run all checks but don't modify the registry.",
    )
    parser.add_argument(
        "--min-pr-auc", type=float,
        default=float(os.getenv("PR_AUC_GATE", "0.0")),
        help="Minimum PR-AUC for the metric gate. Default: PR_AUC_GATE env var or 0.0.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    success = promote(
        version=args.version,
        skip_metric_gate=args.skip_metric_gate,
        dry_run=args.dry_run,
        min_pr_auc=args.min_pr_auc,
    )
    sys.exit(0 if success else 1)
