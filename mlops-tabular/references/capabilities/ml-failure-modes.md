# Production ML Failure Modes

## Why Models Fail in Production

91% of ML models degrade in production without detection. The failures are rarely dramatic crashes -- they are silent degradations where the system continues serving predictions that look plausible but are wrong. Understanding the common failure modes is the first step toward building systems that detect and prevent them.

ML systems differ from traditional software in a fundamental way: **ML Behavior = Code + Data + Parameters + Configuration + Environment.** In traditional software, code is the single source of truth. In ML, there are four sources of truth that must all be correct simultaneously. A bug in any one of them can produce a system that runs without errors but makes wrong predictions.

## The Five Silent Killers

### 1. The Accuracy Trap (Metric Mirage)

Choosing the wrong evaluation metric creates a model that appears excellent but is useless for the business problem.

**How it happens:** A fraud detection model achieves 99.2% accuracy. The team celebrates. But the dataset has 0.8% fraud rate -- a model that predicts "not fraud" for every transaction achieves 99.2% accuracy while catching zero fraud.

**Real-world impact:** A hate speech classifier shows accuracy of 96.8% and AUC of 0.92, but recall is only 0.40 -- meaning 60% of hate speech escapes detection. The high AUC is an artifact of the massive number of true negatives inflating the FPR denominator.

**Why AUC inflates with class imbalance:** AUC-ROC plots TPR vs FPR. With 1% positive class, the denominator of FPR (true negatives + false positives) is massive. Even hundreds of false positives barely move FPR, making the ROC curve look excellent while precision is terrible.

**Prevention:** Match the metric to the business cost. If false negatives are expensive, optimize recall. If false positives are expensive, optimize precision. For imbalanced data, use PR-AUC instead of ROC-AUC.

### 2. Data Leakage (The Cheating Model)

Information from the future or from the test set leaks into training, producing inflated metrics that collapse in production.

**How it happens:** A team scales features before splitting train/test. The scaler's mean and standard deviation include test set statistics, giving the model hints about data it should never have seen. AUC drops from 0.953 to 0.78 when the leak is fixed.

**Common leak sources:**
- Scaling or encoding before train/test split
- Features computed using future information (e.g., "total purchases this month" available at prediction time on day 1)
- Target encoding using the full dataset instead of just training folds
- Time-series data split randomly instead of temporally

**Prevention:** Always split first, then preprocess. Use sklearn.Pipeline to enforce correct ordering. For time-series, split by time. Question every feature: "Would this be available at the moment of prediction in production?"

### 3. Model Drift (The World Changes)

The model was correct when trained, but the world has moved on. The relationship between inputs and outputs has changed.

**How it happens:** A housing price model trained on 2019 data works well through 2020. By 2021, post-pandemic market dynamics have changed the relationship between features (square footage, location, school ratings) and prices. The model's predictions become increasingly wrong.

**Real-world impact:** Zillow's automated home-buying algorithm (Zestimate) accumulated $881 million in losses when the housing market shifted in ways the model did not anticipate. The model continued making confident predictions as the underlying market dynamics changed.

**Another example:** Google Flu Trends initially outperformed CDC surveillance but gradually degraded by overfitting to spurious correlations in search terms rather than actual flu dynamics. When search behavior changed, the model's predictions diverged from reality.

**Prevention:** Monitor feature and prediction distributions continuously. Set drift detection thresholds (PSI, KS test). Establish retraining triggers. Never assume a model's accuracy is permanent.

### 4. Training-Serving Skew (The Twin That Isn't)

Features are computed differently at training time and serving time, causing the model to see a different version of reality in production.

**How it happens:** Training computes features in Python with numpy. Serving recomputes them in Java with a different statistics library. The standard deviation calculation uses `ddof=0` in one and `ddof=1` in the other. A 12% difference in feature values flips credit decisions for borderline applicants.

**Five specific sources of skew:**
1. **Different code paths:** Python training vs Java serving using different libraries for the same computation
2. **Recomputed statistics:** Serving calculates mean/std from live data instead of loading frozen training statistics
3. **Different null handling:** Training imputes with median=34, serving uses default=0 or recomputed median=37
4. **Timezone and rounding differences:** IST vs UTC changes hour-of-day features; floating point rounding (0.3333 vs 0.33) accumulates across feature pipelines
5. **Library version changes:** scikit-learn changed solver defaults between versions; a library upgrade silently changes preprocessing behavior

**Prevention:** Use a single preprocessing pipeline (sklearn.Pipeline) for both training and serving. Serialize the fitted pipeline and load it at serving time. Run golden-set parity tests: 50-100 fixed examples with known outputs, verified on every deploy.

### 5. Irreproducibility (The One-Time Result)

A model worked once but cannot be recreated. Different team members get different results from the "same" code.

**How it happens:** Random seeds are not fixed. Data snapshots are not versioned ("just use the latest data"). Library versions float. Configuration is hardcoded and modified ad-hoc. Six months later, the team cannot reproduce the model that is running in production, making debugging and retraining impossible.

**Real-world impact:** Knight Capital lost $440 million in 45 minutes due to a deployment that activated old, untested code. The system operated without proper version control, monitoring, or rollback capability. When things went wrong, the team could not quickly identify what was running or revert to a known-good state.

**Prevention:** Version everything: code (git), data (snapshots with dates), configuration (config files), environment (pinned requirements). Use experiment tracking to record every run's exact setup. The goal: given a model version, you can always trace back to the exact code, data, config, and environment that produced it.

## The Common Thread

All five failure modes share one property: **the system does not crash.** It continues running, serving predictions, looking healthy to infrastructure monitoring. CPU usage is normal. Latency is fine. No errors in the logs. The only sign of failure is in the predictions themselves -- and without proper monitoring, no one notices until the business impact is severe.

This is why MLOps exists. Not because ML systems are hard to build (they are), but because they are hard to keep working. The infrastructure around the model -- validation, monitoring, drift detection, versioning, rollback -- is what separates a demo from a production system.

## When to Use This

- At the start of any ML project, to motivate why MLOps discipline matters before diving into implementation.
- When a team wants to skip problem framing, monitoring, or versioning -- use these case studies to explain the risk.
- When debugging a production model that is underperforming -- check these five failure modes as a diagnostic checklist.
- When training new team members on production ML risks.

## Key Statistics

- 91% of ML models degrade in production without detection (MIT research)
- Zillow: $881M loss from model drift in housing market predictions
- Knight Capital: $440M loss in 45 minutes from deployment without version control and monitoring
- Google Flu Trends: outperformed CDC initially, then overfitted to spurious search correlations and diverged from reality
