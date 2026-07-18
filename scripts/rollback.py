"""
scripts/rollback.py
===================
Roll back the @champion model alias to the previous stable version.

This is the emergency rollback mechanism for the blue-green deployment.
Target: rollback completes in under 5 minutes (typically under 30 seconds).

## When to rollback

- Business metric drops beyond pre-defined threshold
- Golden input test fails on /health
- Prediction distribution collapses or shifts dramatically
- Latency p95 exceeds 1s SLA for a sustained period
- Any guardrail breach after deployment

## Rollback principle

Rollback first, investigate second. The rollback completes in seconds.
The investigation can take hours. Users should not suffer during root
cause analysis.

## Usage

    # Roll back to the version tagged as previous_champion
    python scripts/rollback.py

    # Roll back to a specific version (bypasses the tag lookup)
    python scripts/rollback.py --version 2

    # Dry run — shows what would happen without making changes
    python scripts/rollback.py --dry-run

## Environment variables

    MLFLOW_TRACKING_URI   — MLflow server (default: sqlite:///mlflow.db)
    MODEL_NAME            — Registered model name (default: dispute-risk-model)
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

import mlflow

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

import os

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
MODEL_NAME = os.getenv("MODEL_NAME", "dispute-risk-model")
CHAMPION_ALIAS = "champion"
PREVIOUS_CHAMPION_TAG = "previous_champion_version"


def rollback(
    *,
    target_version: str | None = None,
    dry_run: bool = False,
) -> bool:
    """
    Roll back @champion to the previous stable version.

    Parameters
    ----------
    target_version : str, optional
        Specific version to roll back to. If None, uses the version
        stored in the 'previous_champion_version' registry tag.
    dry_run : bool
        If True, show what would happen without making changes.

    Returns
    -------
    bool : True if rollback succeeded (or would succeed in dry run).
    """
    start = time.monotonic()
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = mlflow.tracking.MlflowClient()

    logger.info(
        "ROLLBACK INITIATED for model='%s'. dry_run=%s target_version=%s",
        MODEL_NAME, dry_run, target_version or "auto (from tag)",
    )

    # --- Step 1: Identify current champion ---
    try:
        current_champion = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
        current_version = current_champion.version
        logger.info("Current @champion is version=%s", current_version)
    except Exception as exc:
        logger.error("Cannot identify current champion: %s", exc)
        return False

    # --- Step 2: Identify rollback target ---
    if target_version is None:
        # Look up the previous champion tag on the registered model
        try:
            model = client.get_registered_model(MODEL_NAME)
            tags = model.tags or {}
            target_version = tags.get(PREVIOUS_CHAMPION_TAG)
        except Exception as exc:
            logger.error("Failed to read registered model tags: %s", exc)
            return False

        if not target_version:
            logger.error(
                "No previous champion version found in registry tags. "
                "Either this is the first deployment, or promote.py was not used. "
                "Use --version to specify the rollback target explicitly."
            )
            return False

    if target_version == current_version:
        logger.warning(
            "Rollback target version=%s is already the current champion. Nothing to do.",
            target_version,
        )
        return True

    logger.info(
        "Rolling back from version=%s to version=%s.",
        current_version, target_version,
    )

    # --- Step 3: Verify target version exists ---
    try:
        target = client.get_model_version(MODEL_NAME, target_version)
        logger.info("Rollback target confirmed: version=%s status=%s", target_version, target.status)
    except Exception as exc:
        logger.error("Target version %s not found: %s", target_version, exc)
        return False

    if dry_run:
        elapsed = time.monotonic() - start
        logger.info(
            "[DRY RUN] Would reassign @champion from version=%s to version=%s. "
            "Estimated time to this point: %.1fs",
            current_version, target_version, elapsed,
        )
        return True

    # --- Step 4: Execute rollback (alias flip) ---
    try:
        client.set_registered_model_alias(MODEL_NAME, CHAMPION_ALIAS, target_version)
    except Exception as exc:
        logger.error("ROLLBACK FAILED: could not set alias: %s", exc)
        return False

    elapsed = time.monotonic() - start
    logger.info(
        "ROLLBACK COMPLETE in %.1fs. @champion is now version=%s (was %s). "
        "Restart the API service or wait for /health to confirm the new version is serving.",
        elapsed, target_version, current_version,
    )

    # Log rollback event as a registered model tag for audit trail
    try:
        import datetime
        client.set_registered_model_tag(
            MODEL_NAME,
            "last_rollback",
            f"rolled back from v{current_version} to v{target_version} "
            f"at {datetime.datetime.utcnow().isoformat()}",
        )
    except Exception:
        pass  # Audit tag is best-effort; don't fail the rollback over it

    return True


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Roll back the @champion model alias to the previous stable version. "
            "Target: complete in under 5 minutes."
        )
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Specific version to roll back to. If omitted, uses the previous_champion tag.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without modifying the registry.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    success = rollback(
        target_version=args.version,
        dry_run=args.dry_run,
    )
    sys.exit(0 if success else 1)
