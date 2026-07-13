# MLOps Architecture Document

## 1. MLOps Pipeline Overview

This architecture is designed to deliver a high-performing, production-grade model for **Consumer Complaint Dispute Risk Prediction** powered by a CI/CD framework.

### Full Pipeline Stages:
1. **Data Ingestion**: Raw intake data from Azure Blob Storage (training) and real-time API (predictions).
   - Training: Batch ingestion of historical snapshots.
   - Real-Time: FastAPI intake.
2. **Data Validation**: Schema checks on ingest, ensuring feature consistency and quality.
3. **Feature Engineering**: Preprocessing for tabular and categorical inputs, feature scaling, and one-hot encoding.
4. **Model Training**: Baseline Logistic Regression; future iterations with boosted trees.
5. **Evaluation**: Metrics tracking (PR-AUC, Recall@Precision, F2).
6. **Model Registry**: MLflow to track staging and production models.
7. **Deployment**: FastAPI endpoint for real-time predictions.
8. **Monitoring**: Drift and performance validation.

### Maturity Level:
Targeting **Level 2 (CI/CD)** with automated deployments and validation workflows to ensure reliability.

---

## 2. Data Plan
### Summary:
- **Source**: Ingest historical consumer complaint data (357,810 records) via Azure Blob Storage.
- **Real-Time Scenario**: Accept new complaint data via FastAPI for real-time scoring.

### Key Features:
1. Schema Validation: Type, null check, and cardinality enforcement.
2. Storage Strategy:
   - Raw Snapshots: Immutable versioned storage.
   - Intermediate Data: Cleaned and preprocessed feature datasets with lineage.
3. Tracking Artifacts:
   - Transformation statistics, validation reports for reproducibility.

---

## 3. Feature Engineering Plan
### Initial Preprocessing:
1. **Numeric Features**:
   - Feature scaling (zero-mean/unit-variance).
   - Log transformation for skewed fields.
2. **Categorical Features**:
   - One-hot encoding for low-cardinality fields (e.g., `Product`, `Submitted via`).
   - Frequency encoding for high-cardinality (e.g., `Company`).
3. **Text Features (`Consumer complaint narrative`)**:
   - Extract simple features like text length and keyword presence.
4. **Time Features (`Date received`)**:
   - Cyclical encoding (hour/day-of-week sinusoidal transformation).

### Implementation:
- Attach preprocessing logic to the training pipeline using `scikit-learn.Pipeline`.
- Save artifacts (e.g., encoders, scalers) for reuse during inference.

---

## 4. Training & Evaluation Plan
### Framework:
1. **Baseline**: Logistic Regression with `class_weight=balanced`.
2. **Experimental Iterations**:
   - Evaluate tree-based algorithms and boosting (e.g., XGBoost). 
   - Test oversampling strategies (e.g., SMOTE).
3. **Split Strategy**:
   - Time-based holdout (train/validation split).

### Metrics:
- **Primary**: PR-AUC.
- **Guardrail**: Recall@Precision, F2.

### Experiment Tracking:
- ZenML for modular orchestration.
- MLflow to log metrics, artifacts, and configurations.

---

## 5. Deployment Plan
### Key Principles:
- FastAPI-based real-time inference service.
- Automated CI/CD using GitHub Actions + ZenML pipelines.

### Workflow:
1. Pre-deployment testing via golden inputs.
2. Deploy new models directly if metrics surpass the current production benchmarks.
3. Rollback Strategy:
   - Instantly demote failing models in MLflow and re-promote prior production versions.

---

## 6. Monitoring & Drift Detection Plan
### Metrics to Monitor:
1. **Drift Metrics**:
   - Population Stability Index (PSI) for key features.
2. **Performance Metrics**:
   - PR-AUC, Recall@Precision (evaluated on delayed labels).
3. **System Metrics**:
   - Endpoint latency (p95 < 1s).

### Quarterly Review:
- Update baselines and recalibrate thresholds every three months.

---

## 7. Versioning & Governance
- Data snapshots, pipeline configurations, and models will be version-controlled via MLflow.
- Maintain full lineage tracking for reproducibility.

---

## 8. ZenML Stack Specification
| Component           | Choice            |
|---------------------|-------------------|
| **Orchestrator**    | ZenML             |
| **Artifact Store**  | Azure Blob Storage|
| **Model Registry**  | MLflow            |
| **Prediction API**  | FastAPI           |

---

## 9. MVP Scope
- Deliver an end-to-end baseline pipeline supporting Logistic Regression with training, deployment, and real-time inference.
- Activate monitoring for basic drift metrics.

---

## 10. Deferred Components
1. Advanced NLP-based text features (e.g., embeddings).
2. Automatic drift-based retraining triggers.
3. Shadow testing and traffic strategies for true production traffic.