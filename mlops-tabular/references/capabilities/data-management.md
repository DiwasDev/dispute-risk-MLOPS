# Data Management and Configuration

## Core Principle

Most ML wins or fails because of the data, not the algorithm. Treat training data as a living system that evolves with your product. Design that system on purpose: sampling, labels, lineage, fixes for drift. Curate before you iterate.

## The Data Lifecycle

The full lifecycle is: Collect, Sample, Label, Split, Train, Validate, Deploy, Monitor, Refresh data and labels. Revisit earlier steps after every release. Treat data like code with versions and changelogs. Data work is iterative -- production data is not finite or stationary.

## Sampling Strategies

Start simple, stay representative.

- **Simple random**: easiest, but can miss rare segments.
- **Stratified**: sample proportionally across important dimensions (country, device, class). Use this for email spam models stratified by country and device.
- **Weighted / importance**: oversample rare but valuable segments.
- **Reservoir**: for streaming data when you cannot hold everything in memory.

Non-probability (convenience) sampling is fast but biased. Probability sampling (random/stratified) is slower but trustworthy. A classifier built only from English tickets will fail in India -- fix with stratified samples by locale and channel.

## Label Sourcing

**Hand labels** are gold but expensive. Track label multiplicity -- multiple valid labels or annotator disagreement are common. Always capture who labeled, when, and under what instructions. Store all votes, not just the majority label.

**Natural labels** come from system feedback (clicks, travel time, conversions). Define windows where absence becomes negative. Short windows learn fast but risk mislabeling late events. Choose windows per product context.

**When hand labels are scarce**, use four tools:

1. **Weak supervision**: combine noisy heuristic rules. A model learns which rules are accurate. Validate with a small, clean labeled set.
2. **Semi-supervision**: train on a small labeled set, pseudo-label high-confidence unlabeled examples, retrain, repeat. Keep a clean validation set to prevent confirmation loops.
3. **Transfer learning**: adapt a pretrained model with few labels (2-5k labeled tickets instead of 200k from scratch). Try zero-shot or few-shot when data is very limited.
4. **Active learning**: show annotators only uncertain, disagreeing, or out-of-distribution examples. Trickle random samples to avoid bias. Cuts label costs while raising quality on the decision boundary.

Always maintain a set of verified labels to calibrate or audit regardless of which tool you use.

## Data Lineage

Track where each sample and label came from and when. Lineage enables debugging performance drops and uncovering bias. When a crowdsourced batch causes an accuracy fall, lineage reveals the issue immediately.

Every row should carry lineage fields: source system, collection timestamp, labeler identity, label timestamp, sampling method, and any transformations applied.

## Class Imbalance

Rare classes make accuracy misleading. A 1% fraud rate means an always-not-fraud model gives 99% accuracy but 0 recall. Prefer precision/recall, PR-AUC, and cost-aware metrics.

**Data-level fixes**: oversample minority, undersample majority, or use SMOTE-style synthesis. Pair resampling with validation to avoid inflated metrics. Use stratified splits for realistic rates.

**Algorithm-level fixes**: use class weights and try focal or class-balanced loss. Validate with slice metrics to avoid overfitting to the minority.

## Splits That Reflect Reality

- Keep train/validation/test splits honest.
- Use time-based splits for time-dependent data.
- Split by keys (region, device) for product-scoped models.
- Treat your validation set as a contract -- do not leak information across splits.

## Feature Engineering for Tabular Data

Features must be useful and stable across the lifecycle. A top-tier model on paper shipped with skewed, unscaled inputs produces gibberish scores in production.

**Augmentation**: label-preserving transforms that create more varied inputs for more robust models. For tabular, this means perturbation -- adding small noise to inputs at train time to reduce sensitivity and reveal brittle features.

**Data synthesis**: create plausible labeled examples for rare classes or ranges. Keep distributions realistic, document how generated, and use to seed coverage -- replace with real data later.

**Handling missing values**: options are drop, simple impute, or model-based impute. Imputation can inject leakage if it peeks at labels or future info. Impute using train-split stats and persist the same strategy and stats in serving.

**Scaling**: scale for comparable magnitudes (needed for logistic regression, GBDTs are less sensitive). Min-max to [0,1] or [-1,1], or standardize to zero-mean/unit-variance. Compute on the train split, reuse frozen stats in serving, retrain when drifted.

**Discretization (binning)**: turn continuous features into bins (quantile or domain bins). Guards against weird unseen values at serving time. Simple quantiles often suffice.

**Encoding categoricals that evolve**: one-hot for small, stable sets. Top-K with an "UNKNOWN" bucket for the tail (beware new categories). Hashing trick maps any string to a fixed index, handles unseen categories, and collisions are usually acceptable.

**Feature crossing**: create interaction features (e.g., marital_status x num_children). Watch for combinatorial explosion and overfit risk. Match cross complexity to data volume.

## Leakage Detection

Leakage means a feature "sees the future" or the label. Common sources: scaling with stats including validation/test, imputing with label info, target encoding without out-of-fold. Leakage produces dazzling offline metrics but disastrous production performance.

Run these checks every time:
- Time-aware splits: train < validate < test by event time.
- Transform parity: same code path and frozen stats for train and serve.
- Out-of-fold encodings for target/mean encoders.
- Ablation test: drop suspicious features and audit impact.
- Canary monitor: alert on sudden distribution or prediction shifts.

## Configuration Management

Treat all configuration (hyperparameters, feature lists, threshold values, sampling parameters) as versioned artifacts alongside code and data. Every experiment should be reproducible from its configuration snapshot.

## Quality Pitfalls and Defenses

Common failures: label noise, drifting inputs, mixing data without tags. Defenses: data lineage, per-batch metrics, immutable holdout sets. When a new vendor batch causes a dip, lineage flags the wrong labels immediately.

## Monitoring and Refresh Cadence

Monitor input distributions, feature health, output distributions, and ground-truth metrics. Set retrain triggers based on drift detection or KPI degradation. Shipping the model is not the end -- it is the beginning of the data maintenance lifecycle.

## When to Use This

- When designing the data pipeline for a new ML project.
- When model performance degrades and you suspect data quality issues.
- When labels are scarce, expensive, or delayed.
- When onboarding a new data source or vendor.
- When setting up monitoring for a production ML system.
- When class imbalance is causing misleading evaluation results.

## Red Flags to Watch For

- No data lineage -- you cannot trace a training example back to its source.
- Convenience sampling only, with no stratification plan.
- Labels arrive from a single source with no quality audit or disagreement tracking.
- Validation set is not immutable or is contaminated by training data.
- Imputation or scaling stats are computed on the full dataset instead of the train split only.
- No plan for handling new categories or unseen values at serving time.
- Resampling is applied before splitting, inflating validation metrics.
- No retrain triggers or refresh cadence defined.
- Feature transforms differ between training and serving code paths.
- Synthetic data is used without documentation of how it was generated or plans to replace it.
