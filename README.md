# Consumer Complaint Dispute Risk Prediction

Predicts whether a consumer will dispute a complaint resolution. Routes high-risk complaints to the senior dispute review queue before the resolution is sent.

**Problem**: CFPB receives ~360K complaints/year. Manual review of every complaint is not scalable. The model identifies which complaints are likely to be disputed, so the review team can prioritize.

**Target metric**: PR-AUC (primary). F2-score and Recall@Precision as guardrails.

---

## Project Structure

```
core/           Pure Python library — no ZenML or MLflow imports
  preprocessing.py   Feature engineering sklearn Pipeline
  training.py        Model training and MLflow logging
  evaluation.py      PR-AUC, F2, bootstrapped CIs, slice evaluation
  validation.py      Schema validation and null rate baseline
  drift.py           PSI + KS + Chi-squared drift detection
  monitoring.py      Four-layer monitoring: snapshots + alerts

steps/          ZenML pipeline steps (thin wrappers over core/)
  ingest.py          Load + validate raw data
  preprocess.py      Time-based train/val split
  train.py           Fit pipeline + log to MLflow
  evaluate.py        Compute metrics + log to MLflow
  monitor.py         Serving window drift detection + alert checking

pipelines/      ZenML orchestration
  training_pipeline.py   End-to-end training pipeline

app/            FastAPI inference service
  main.py            /predict, /health, /drift endpoints
  schemas.py         Pydantic request/response models

scripts/        Deployment operations
  promote.py         Promote model version to @champion (blue-green)
  rollback.py        Roll back @champion in < 5 minutes

tests/          Unit tests (pytest, no ZenML/MLflow server required)
  test_preprocessing.py
  test_training.py
  test_evaluation.py
  test_validation.py
  test_drift.py
  test_serving.py

configs/
  training_config.yaml   Single source of truth for all hyperparameters

data/           Raw data (not committed — download separately)
  complaints.csv
```

---

## Quick Start

**Prerequisites**: Python 3.12, venv at `venv/`

```bash
source venv/bin/activate
```

### Run training pipeline

```bash
python run_training.py
# or
python -m pipelines.training_pipeline
```

### Start the inference API

```bash
# First: register and alias a trained model version (see Deployment below)
uvicorn app.main:app --reload --port 8000
```

API docs at `http://localhost:8000/docs`

### Run all tests

```bash
pytest tests/ -v
```

### Code quality

```bash
black .
ruff check .
```

---

## Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| Primary metric | PR-AUC | 21% positive rate; PR-AUC penalizes minority class failure more than ROC-AUC |
| Class imbalance | `class_weight="balanced"` + threshold tuning | Dataset has 76K minority examples — SMOTE is not warranted |
| Encoding | OHE for low-cardinality, TargetEncoder for high-cardinality | Prevents one-hot explosion on 3K+ company names |
| Training-serving parity | Single sklearn Pipeline artifact | Preprocessing and model are serialized together — no separate serving code path |
| Deployment strategy | Blue-green via MLflow model aliases | Instant rollback (alias flip), zero code changes, under 5 minutes |
| Drift detection | PSI (primary) + Chi-squared | PSI is architecture's specified method; chi-squared complements for categorical features |

---

## Deployment (Blue-Green)

The API loads the `@champion` model alias from MLflow at startup.

### Promote a new model to production

```bash
# After training, get the version number from MLflow, then:
python scripts/promote.py --version 3

# Gates checked before promotion:
#   1. Golden input test (training-serving parity)
#   2. PR-AUC metric gate (set PR_AUC_GATE env var)

# Dry run first to see what would happen:
python scripts/promote.py --version 3 --dry-run
```

### Rollback in under 5 minutes

```bash
# Roll back to previous champion (stored in registry tag):
python scripts/rollback.py

# Roll back to a specific version:
python scripts/rollback.py --version 2

# Dry run:
python scripts/rollback.py --dry-run
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `MLFLOW_TRACKING_URI` | `sqlite:///mlflow.db` | MLflow backend |
| `MODEL_NAME` | `dispute-risk-model` | Registered model name |
| `CHAMPION_ALIAS` | `champion` | Alias the API loads |
| `DISPUTE_THRESHOLD` | `0.5` | Decision threshold for routing |
| `REFERENCE_DATA_PATH` | `data/complaints.csv` | Training data for drift detection |

---

## Monitoring

### Health check

```bash
curl http://localhost:8000/health
```

Returns golden input parity status, model version, and serving health.

### On-demand drift detection

```bash
curl -X POST http://localhost:8000/drift \
  -H "Content-Type: application/json" \
  -d '{"complaints": [...]}'
```

### Scheduled monitoring (ZenML)

```python
from steps.monitor import monitor_model
snapshot, drift_report, alert_report = monitor_model(
    serving_log_path="logs/serving_2016-03-15.csv",
    reference_data_path="data/complaints.csv",
    model_version="3",
)
```

### Drift thresholds (PSI)

| PSI | Status | Action |
|---|---|---|
| < 0.10 | Stable | No action |
| 0.10–0.25 | Moderate | Investigate |
| > 0.25 | Significant | Trigger retraining review |

### Alert severity

| Severity | Examples | Response |
|---|---|---|
| Critical | Zero predictions, prediction collapse | Page immediately |
| High | Prediction mean drift, latency p95 > 1s | Respond within hours |
| Medium | Null rate spike, positive rate > 60% | Respond within one business day |
| Low | Slow persistent shifts | Weekly review |

---

## Incident Response (First Hour)

1. **Check `/health`** — golden input passed? If not, rollback immediately.
2. **Check drift panels** — which features drifted? Is it data or concept drift?
3. **Run golden inputs** — do outputs match expected values?
4. **Annotate timeline** — what deployed? What changed upstream?
5. **Decide action** (fastest to slowest):
   - Rollback (< 5 min): `python scripts/rollback.py`
   - Threshold adjustment (immediate)
   - Recalibration (hours)
   - Retraining (days)

---

## Data

- **Source**: CFPB Consumer Complaint Database
- **Size**: 357,810 records (Dec 2011 – Sep 2016)
- **Target**: `Consumer disputed?` (Yes/No) — 21% positive rate
- **Split**: time-based cutoff 2016-01-01 (~83% train, ~17% validation)
- **Leakage columns** (never used): `Company response`, `Timely response?`, `Date sent to company`

---

## Architecture

See `architecture.md` for the full MLOps architecture document.

**Stack**: ZenML (orchestration) · MLflow (experiment tracking + registry) · FastAPI (serving) · scikit-learn Pipeline (training-serving parity)

**Maturity level**: Level 2 (CI/CD) — automated training, evaluation gates, blue-green deployment, drift monitoring.
