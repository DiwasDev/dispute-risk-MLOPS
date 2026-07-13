# Training-Serving Parity and Skew

## Core Principle

Features must be useful and stable across the entire lifecycle. A top-tier model on paper can ship with skewed, unscaled inputs and produce gibberish scores in production. Another team bucketizing a key feature differently in training vs serving causes silent degradation. The goal is one code path, one set of frozen statistics, one transform pipeline -- shared between training and serving.

## What Training-Serving Skew Is

Training-serving skew is any difference between how data is processed during training and how it is processed during inference. It is one of the most common and most damaging silent failures in production ML. The model learns one version of reality during training but encounters a different version at serving time.

Skew can occur at multiple levels:

- **Feature computation skew**: features computed differently offline (batch) vs online (real-time). Different code paths, different libraries, different rounding, or different join timing.
- **Data distribution skew**: the population seen at serving time differs from the training population. New user segments, seasonal shifts, or product changes alter the input distribution.
- **Label skew**: the relationship between features and labels changes. What was true during training is no longer true at serving time.
- **Transform skew**: scaling parameters, bin edges, encoding maps, or imputation values differ between train and serve environments.

## The TLM Loop for Features

Apply the observe-explain-build-reflect loop to feature engineering:

1. **Observe**: how the data arrives, its ranges, drift patterns, and missingness.
2. **Explain**: which transforms protect decisions and why each is necessary.
3. **Build**: the smallest, monitorable pipeline where train equals serve.
4. **Reflect**: build dashboards for data health, feature health, and prediction health.

## The Five Specific Sources of Training-Serving Skew

These are the most common concrete causes of parity violations, in order of frequency:

1. **Different code paths:** Training computes features in Python (numpy, pandas). Serving recomputes them in Java, Go, or a different Python service using different libraries. Even subtle differences -- `np.std()` uses `ddof=0` by default, Java's `StandardDeviation` uses `ddof=1` -- produce different results. A 12% feature value difference can flip credit decisions for borderline applicants.

2. **Recomputed statistics:** Serving calculates mean, standard deviation, or quantiles from live data instead of loading the frozen values computed on the training set. As the live data distribution shifts, the scaling changes, and the model sees inputs it was never trained on.

3. **Different null handling:** Training imputes missing values with the training-set median (e.g., median=34). Serving uses a hardcoded default (0) or recomputes the median from live data (37). The model receives different values for the same missing input.

4. **Timezone and rounding differences:** A feature "hour of day" computed in IST during training but UTC during serving shifts values. Floating-point rounding (0.3333 vs 0.33) accumulates across multi-step feature pipelines.

5. **Library version changes:** scikit-learn changed solver defaults between versions. A library upgrade in the serving environment silently changes preprocessing behavior while the training environment still uses the old version.

**Detection methods:**
- **Golden-set parity test:** Maintain 50-100 fixed examples with known expected outputs. Run them through both training and serving pipelines on every deploy. Any difference is a skew bug.
- **Feature distribution comparison:** Compare serving-time feature distributions against training baselines. Unexplained divergence points to computation differences.
- **Prediction distribution comparison:** If predictions shift without a model change, a feature computation has likely changed.

## Common Sources of Parity Violations

### Scaling and Normalization
Computing normalization statistics online (at serving time) instead of freezing them from training is a frequent source of skew. The fix: compute scaling stats on the train split only, serialize them as versioned artifacts, and load the frozen stats in the serving pipeline. Retrain and recompute only when drift is detected.

### Imputation
Imputation can inject both leakage and skew. If the training pipeline imputes using stats from the full dataset (including validation/test), or if the serving pipeline uses a different imputation strategy, parity is broken. Impute using train-split stats, persist the same strategy and parameters, and apply identically in serving.

### Categorical Encoding
Training may use a vocabulary built from the full training set, but serving encounters new categories unseen during training. Strategies to maintain parity: use top-K encoding with an explicit "UNKNOWN" bucket, or use feature hashing which handles unseen categories by mapping any string to a fixed index. Monitor the collision rate and UNKNOWN rate in production.

### Discretization and Binning
Bin edges computed during training must be frozen and reused exactly during serving. Recomputing quantiles at serving time on different data creates skew. Simple quantile bins computed once on training data often suffice.

### Feature Crosses
Interaction features (e.g., plan_type x tenure_bin) must use the same component encoding in both environments. If the underlying categorical encoding drifts, the cross drifts with it.

## Online vs Offline Feature Computation

A critical architectural decision is whether features are computed offline (batch) or online (real-time). Each approach introduces different parity risks:

**Offline (batch) features**: computed on a schedule, stored in a feature store, and looked up at serving time. Risk: staleness if the batch job is delayed. Risk: the join between request-time data and batch-computed features uses different timing than training.

**Online (real-time) features**: computed at request time from raw signals. Risk: different code path than training. Risk: different library versions or data access patterns. The fix: share the same transform code between training and serving, ideally as a single library or containerized pipeline.

**Hybrid approach**: most production systems use both. Slowly-changing features (user profile, historical aggregates) are computed in batch. Fast-changing features (session signals, real-time counts) are computed online. Parity requires careful documentation of which features use which path and ensuring each path is tested.

## Debugging Training-Serving Skew

When model performance degrades in production but offline metrics look fine, suspect skew. Debugging strategies:

1. **Log serving inputs alongside predictions**. Compare the distribution of each feature at serving time against the training distribution. Significant divergence points to skew or drift.
2. **Run the training pipeline on serving data**. Feed production inputs through the exact training transform code and compare outputs to what the serving pipeline produced. Differences reveal transform skew.
3. **Ablation by feature group**. Disable feature groups one at a time in production (or in a shadow mode) to isolate which group is causing degradation.
4. **Canary monitoring**. Alert on sudden shifts in prediction distribution. If the prediction distribution changes but the input distribution is stable, a transform has likely changed.
5. **Unit tests for transforms**. Write tests that feed the same raw input through both the training and serving transform paths and assert identical outputs.

## The Production Checklist for Parity

Before any model goes to production, verify:

- Train/serve parity proven with unit tests for transforms.
- All scaling stats, bin edges, and encoders versioned and immutable in serving.
- Input, feature, and prediction distributions monitored with documented alert thresholds.
- Backfill and migration plan exists if a transform changes.
- Rollback path defined if a new feature hurts guardrail metrics.

## Common Traps and Quick Fixes

- **Recomputing normalization online**: freeze stats from training and load them at serving time.
- **"UNKNOWN" bucket absorbs everything new**: prefer hashing for high-cardinality categoricals to maintain signal from unseen values.
- **Too many feature crosses on small data**: start with simple overlaps and add crosses only after data volume supports them.
- **Beautiful features that are brittle in production**: fewer, safer transforms beat clever but fragile ones. Boring features that are stable, versioned, and monitored are the goal.

## Feature Store as Parity Guarantor

A feature store (even a simple one) can enforce parity by serving as the single source of truth for feature definitions, transform logic, and precomputed values. Both training and serving read from the same store, eliminating code-path divergence. When building a feature store, ensure it versions feature definitions, logs feature values at prediction time for later auditing, and supports both batch and online retrieval.

## When to Use This

- When deploying a model to production for the first time.
- When production metrics diverge from offline evaluation metrics.
- When adding new features to an existing production model.
- When migrating feature computation from batch to online or vice versa.
- When a transform, encoding, or scaling approach changes.
- When debugging silent model degradation.

## Red Flags to Watch For

- Training and serving use different codebases or libraries for feature transforms.
- Scaling or normalization stats are recomputed at serving time instead of loaded from training artifacts.
- No unit tests exist that verify identical transform outputs for the same input in train and serve paths.
- New categories appear in serving logs with no handling strategy (no UNKNOWN bucket, no hashing).
- Prediction distribution has shifted but no one has investigated why.
- Feature computation timing differs between training (event-time joins) and serving (request-time lookups).
- Bin edges, vocabulary maps, or imputation values are hardcoded rather than loaded from versioned artifacts.
- No monitoring exists for feature-level distributions in production.
- The team cannot reproduce a production prediction from logged inputs using the training pipeline.
- Offline metrics keep improving but business metrics are flat or declining.
