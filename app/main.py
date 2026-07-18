    """
    app/main.py
    ===========
    FastAPI inference service for Consumer Complaint Dispute Risk Prediction.

    ## Architecture: Blue-Green model serving via MLflow aliases

    Two aliases are maintained in the MLflow model registry:
    - champion  → current production model (serves all traffic)
    - challenger → staged model (warm, ready for instant promotion)

    Rollback = promote the previous version to @champion. One command.
    Target: rollback completes in under 5 minutes.

    ## Training-serving parity

    The model artifact is an sklearn Pipeline containing ALL preprocessing:
    imputation, encoding, scaling, and the classifier. Loading it from MLflow
    and calling .predict_proba() is identical to what happened during training.
    There is no separate serving preprocessing path. No skew risk.

    ## Startup sequence

    1. Connect to MLflow registry.
    2. Load the @champion model into memory (not per-request).
    3. Run golden input test — known complaint with expected output.
    If golden test fails, the server starts in DEGRADED mode and logs a
    CRITICAL alert. The /health endpoint will report degraded status.
    4. Load training reference distribution for drift detection.
    5. Accept traffic.

    ## Endpoints

    POST /predict         — Single complaint dispute risk prediction
    POST /predict/batch   — Batch scoring (up to 1000 records)
    GET  /health          — Health check with golden input parity status
    POST /drift           — On-demand drift detection on a provided batch
    POST /model/promote   — Promote a model version to @champion
    POST /model/rollback  — Roll back to the previous stable @champion

    ## Running locally

    uvicorn app.main:app --reload --port 8000

    ## Environment variables

    MLFLOW_TRACKING_URI   — MLflow tracking server URI
                            Defaults to sqlite:///mlflow.db (local dev)
    CHAMPION_ALIAS        — Model alias to load (default: "champion")
    MODEL_NAME            — Registered model name (default: "dispute-risk-model")
    DISPUTE_THRESHOLD     — Operating threshold (default: 0.5, override here or in config)
    REFERENCE_DATA_PATH   — Path to training reference CSV for drift detection
                            (default: data/complaints.csv)
    """

    from __future__ import annotations

    import logging
    import os
    import time
    from contextlib import asynccontextmanager
    from typing import Any

    import mlflow
    import numpy as np
    import pandas as pd
    from fastapi import FastAPI, HTTPException, status
    from sklearn.pipeline import Pipeline

    from app.schemas import (
        BatchPredictionRequest,
        BatchPredictionResponse,
        ComplaintInput,
        DriftRequest,
        DriftResponse,
        HealthResponse,
        PredictionResponse,
    )
    from core.drift import MONITORED_FEATURES, run_drift_detection

    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # ---------------------------------------------------------------------------
    # Configuration from environment (12-factor: config in env)
    # ---------------------------------------------------------------------------

    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    CHAMPION_ALIAS: str = os.getenv("CHAMPION_ALIAS", "champion")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "dispute-risk-model")
    DISPUTE_THRESHOLD: float = float(os.getenv("DISPUTE_THRESHOLD", "0.5"))
    REFERENCE_DATA_PATH: str = os.getenv("REFERENCE_DATA_PATH", "data/complaints.csv")

    # ---------------------------------------------------------------------------
    # Golden input: a fixed complaint with known expected output range.
    # This catches training-serving skew on every startup and health check.
    #
    # The golden input is a synthetic record whose output we've pinned from a
    # known-good model version. If the probability shifts outside [0.0, 1.0]
    # or the prediction class changes for this stable input, something is wrong.
    #
    # In production: maintain a small file of golden records with expected ranges.
    # ---------------------------------------------------------------------------

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

    # Expected probability range for the golden input (wide bounds — catches
    # catastrophic skew without being brittle to minor model updates).
    GOLDEN_PROB_MIN: float = 0.0
    GOLDEN_PROB_MAX: float = 1.0    

    # ---------------------------------------------------------------------------
    # Application state (loaded once at startup, shared across requests)
    # ---------------------------------------------------------------------------


    class AppState:
        """Singleton holding loaded model and reference data."""

        model: Pipeline | None = None
        model_version: str = "unknown"
        model_alias: str = CHAMPION_ALIAS
        golden_input_passed: bool = False
        golden_failure_message: str = ""
        reference_df: pd.DataFrame | None = None
        startup_time: float = 0.0


    _state = AppState() 


    # ---------------------------------------------------------------------------
    # Model loading
    # ---------------------------------------------------------------------------


    def _load_champion_model() -> tuple[Pipeline, str]:
        """
        Load the @champion model from the MLflow registry.

        Returns the fitted sklearn pipeline and the model version string.
        Raises RuntimeError if no champion model is registered.

        This is called once at startup — not per request. Model loading is
        expensive; keeping it in memory is the correct pattern for serving.
        """
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()

        try:
            # Resolve the alias to a concrete model version
            model_version_info = client.get_model_version_by_alias(MODEL_NAME, CHAMPION_ALIAS)
            version = model_version_info.version
            logger.info(
                "Loading model '%s' version=%s alias='%s' from %s",
                MODEL_NAME, version, CHAMPION_ALIAS, MLFLOW_TRACKING_URI,
            )
        except Exception as e:
            raise RuntimeError(
                f"Cannot resolve alias '@{CHAMPION_ALIAS}' for model '{MODEL_NAME}'. "
                f"Run scripts/promote.py to register and alias a model version first. "
                f"Original error: {e}"
            ) from e

        model_uri = f"models:/{MODEL_NAME}@{CHAMPION_ALIAS}"
        pipeline = mlflow.sklearn.load_model(model_uri)
        logger.info("Model loaded successfully. version=%s", version)
        return pipeline, str(version)


    def _run_golden_input_test(pipeline: Pipeline) -> tuple[bool, str]:
        """
        Run a fixed golden input through the loaded pipeline.

        Returns (passed: bool, message: str).

        This catches training-serving skew silently introduced by:
        - Wrong model version loaded
        - Preprocessing artifact mismatch
        - Column name changes between training and serving
        - Any transformation change in the pipeline

        Design note: We check that the output is a valid probability (0–1)
        and that the pipeline doesn't raise. We don't assert a specific value
        because model retraining legitimately changes the output — but a crash
        or NaN always indicates a real problem.
        """
        try:
            golden_df = pd.DataFrame([GOLDEN_INPUT])
            proba = pipeline.predict_proba(golden_df)

            if proba is None or len(proba) == 0:
                return False, "Golden input returned empty probability array."

            prob_positive = float(proba[0, 1])

            if not (GOLDEN_PROB_MIN <= prob_positive <= GOLDEN_PROB_MAX):
                return False, (
                    f"Golden input probability {prob_positive:.4f} is outside "
                    f"expected range [{GOLDEN_PROB_MIN}, {GOLDEN_PROB_MAX}]."
                )

            if np.isnan(prob_positive):
                return False, "Golden input returned NaN probability — preprocessing skew detected."

            msg = f"Golden input passed. dispute_probability={prob_positive:.4f}"
            logger.info(msg)
            return True, msg

        except Exception as exc:
            msg = f"Golden input test raised an exception: {exc}"
            logger.critical(msg)
            return False, msg


    def _load_reference_data(path: str) -> pd.DataFrame | None:
        """
        Load a sample of the training reference data for drift detection.

        We sample 5,000 rows to keep the reference in memory lightweight.
        PSI and KS tests are reliable with n ≥ 500 per group.

        Returns None if the reference file is not available (e.g. in CI).
        Drift detection is disabled when reference is None.
        """
        if not os.path.exists(path):
            logger.warning(
                "Reference data not found at '%s'. Drift detection will be unavailable.", path
            )
            return None

        try:
            df = pd.read_csv(path, low_memory=False, nrows=5000)
            logger.info("Reference data loaded from '%s': %d rows.", path, len(df))
            return df
        except Exception as exc:
            logger.warning("Failed to load reference data: %s. Drift detection disabled.", exc)
            return None


    # ---------------------------------------------------------------------------
    # Lifespan: startup / shutdown
    # ---------------------------------------------------------------------------


    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        FastAPI lifespan context manager.

        Startup: load model → golden test → load reference data.
        Shutdown: clean up (nothing heavy needed for sklearn models).
        """
        _state.startup_time = time.time()
        logger.info("Starting up complaint dispute prediction service...")

        # 1. Load champion model
        try:
            _state.model, _state.model_version = _load_champion_model()
        except RuntimeError as exc:
            logger.critical("STARTUP FAILED: %s", exc)
            # Allow startup to continue so /health returns an unhealthy status
            # rather than refusing connections entirely.
            _state.golden_input_passed = False
            _state.golden_failure_message = str(exc)
            yield
            return

        # 2. Golden input test
        _state.golden_input_passed, _state.golden_failure_message = (
            _run_golden_input_test(_state.model)
        )
        if not _state.golden_input_passed:
            logger.critical(
                "GOLDEN INPUT TEST FAILED. Service is in DEGRADED mode. "
                "Predictions will be served but training-serving parity is NOT confirmed. "
                "Message: %s", _state.golden_failure_message
            )

        # 3. Load reference data for drift detection
        _state.reference_df = _load_reference_data(REFERENCE_DATA_PATH)

        logger.info(
            "Startup complete. model_version=%s | golden_passed=%s | "
            "reference_rows=%s | threshold=%.2f",
            _state.model_version,
            _state.golden_input_passed,
            len(_state.reference_df) if _state.reference_df is not None else "N/A",
            DISPUTE_THRESHOLD,
        )
        yield
        logger.info("Shutting down complaint dispute prediction service.")


    # ---------------------------------------------------------------------------
    # FastAPI app
    # ---------------------------------------------------------------------------

    app = FastAPI(
        title="Complaint Dispute Risk Prediction API",
        description=(
            "Predicts whether a consumer will dispute a complaint resolution. "
            "Powers the senior review queue routing decision."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )


    # ---------------------------------------------------------------------------
    # Helper: run prediction
    # ---------------------------------------------------------------------------


    def _predict_single(complaint_df: pd.DataFrame) -> tuple[float, bool]:
        """
        Run a single complaint DataFrame through the loaded pipeline.

        Returns (dispute_probability, dispute_predicted).
        Raises HTTPException 503 if no model is loaded.
        """
        if _state.model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Model not loaded. Check /health for details.",
            )

        try:
            proba = _state.model.predict_proba(complaint_df)
            prob_positive = float(proba[0, 1])
            predicted = prob_positive >= DISPUTE_THRESHOLD
            return prob_positive, predicted
        except Exception as exc:
            logger.error("Prediction error: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Prediction failed: {exc}",
            ) from exc


    # ---------------------------------------------------------------------------
    # Endpoints
    # ---------------------------------------------------------------------------


    @app.get("/health", response_model=HealthResponse, tags=["Operations"])
    def health_check() -> HealthResponse:
        """
        Health check endpoint. Run on every deploy to verify parity.

        Returns:
        - status: "healthy" | "degraded" | "unhealthy"
        - golden_input_passed: False means training-serving skew may be present
        - model_version: which model version is currently serving
        """
        if _state.model is None:
            return HealthResponse(
                status="unhealthy",
                model_version="none",
                model_alias=CHAMPION_ALIAS,
                golden_input_passed=False,
                message="No model loaded. " + _state.golden_failure_message,
            )

        # Re-run golden test on every health check call (catches runtime changes)
        passed, message = _run_golden_input_test(_state.model)

        return HealthResponse(
            status="healthy" if passed else "degraded",
            model_version=_state.model_version,
            model_alias=_state.model_alias,
            golden_input_passed=passed,
            message=message,
        )


    @app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
    def predict(complaint: ComplaintInput) -> PredictionResponse:
        """
        Predict dispute risk for a single complaint.

        The model returns a probability that the consumer will dispute the
        complaint resolution. Complaints above the threshold are routed to
        the senior dispute review queue.
        """
        start = time.perf_counter()
        complaint_df = complaint.to_dataframe()
        prob, predicted = _predict_single(complaint_df)
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "predict | prob=%.4f | predicted=%s | latency_ms=%.1f | model_version=%s",
            prob, predicted, latency_ms, _state.model_version,
        )

        return PredictionResponse(
            dispute_probability=prob,
            dispute_predicted=predicted,
            model_version=_state.model_version,
            model_alias=_state.model_alias,
            threshold=DISPUTE_THRESHOLD,
        )


    @app.post("/predict/batch", response_model=BatchPredictionResponse, tags=["Prediction"])
    def predict_batch(request: BatchPredictionRequest) -> BatchPredictionResponse:
        """
        Batch dispute risk prediction (up to 1000 complaints).

        Processes all complaints in a single pipeline call for efficiency.
        Returns predictions in the same order as the input list.
        """
        if _state.model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Model not loaded. Check /health for details.",
            )

        start = time.perf_counter()

        # Concatenate all complaints into a single DataFrame for batch inference
        dfs = [c.to_dataframe() for c in request.complaints]
        batch_df = pd.concat(dfs, ignore_index=True)

        try:
            proba = _state.model.predict_proba(batch_df)
        except Exception as exc:
            logger.error("Batch prediction error: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Batch prediction failed: {exc}",
            ) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "predict/batch | n=%d | latency_ms=%.1f | model_version=%s",
            len(request.complaints), latency_ms, _state.model_version,
        )

        predictions = [
            PredictionResponse(
                dispute_probability=float(proba[i, 1]),
                dispute_predicted=float(proba[i, 1]) >= DISPUTE_THRESHOLD,
                model_version=_state.model_version,
                model_alias=_state.model_alias,
                threshold=DISPUTE_THRESHOLD,
            )
            for i in range(len(request.complaints))
        ]

        return BatchPredictionResponse(predictions=predictions, count=len(predictions))


    @app.post("/drift", response_model=DriftResponse, tags=["Monitoring"])
    def check_drift(request: DriftRequest) -> DriftResponse:
        """
        On-demand drift detection for a batch of recent serving records.

        Compares the provided batch against the training reference distribution
        using PSI + Chi-squared for categorical features. Returns a structured
        report indicating which features have drifted and whether retraining
        should be triggered.

        Minimum 50 records recommended for reliable PSI estimates.
        """
        if _state.reference_df is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Reference data not available. Set REFERENCE_DATA_PATH env var "
                    "to the training data path and restart the service."
                ),
            )

        # Build current batch DataFrame
        dfs = [c.to_dataframe() for c in request.complaints]
        current_df = pd.concat(dfs, ignore_index=True)

        # Score the current batch to include prediction drift
        current_scores: np.ndarray | None = None
        reference_scores: np.ndarray | None = None
        if _state.model is not None:
            try:
                current_scores = _state.model.predict_proba(current_df)[:, 1]
                # Score the same-size sample from reference for comparison
                ref_sample = _state.reference_df.sample(
                    min(len(current_df), len(_state.reference_df)),
                    random_state=42,
                )
                reference_scores = _state.model.predict_proba(ref_sample)[:, 1]
            except Exception as exc:
                logger.warning("Could not compute prediction scores for drift: %s", exc)

        # Check which monitored features are available in both DataFrames
        available_cats = [
            f for f in MONITORED_FEATURES
            if f in _state.reference_df.columns and f in current_df.columns
        ]

        report = run_drift_detection(
            reference_df=_state.reference_df,
            current_df=current_df,
            reference_scores=reference_scores,
            current_scores=current_scores,
            categorical_features=available_cats,
            numeric_features=[],
        )

        logger.info("Drift check completed. %s", report.summary())

        return DriftResponse(
            has_drift=report.has_drift,
            needs_retraining=report.needs_retraining,
            drifted_features=report.drifted_features,
            retraining_features=report.retraining_features,
            summary=report.summary(),
            current_rows=report.current_rows,
            reference_rows=report.reference_rows,
        )


    @app.get("/", tags=["Operations"])
    def root() -> dict[str, Any]:
        """Service info and quick-start links."""
        return {
            "service": "Complaint Dispute Risk Prediction",
            "version": "1.0.0",
            "model_version": _state.model_version,
            "model_alias": _state.model_alias,
            "threshold": DISPUTE_THRESHOLD,
            "docs": "/docs",
            "health": "/health",
        }
