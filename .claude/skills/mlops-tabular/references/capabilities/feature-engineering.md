# Feature Engineering & Feature Stores

## Why Feature Engineering Matters

Features are the language you use to explain the world to your model. A well-chosen feature encodes domain knowledge that took humans years to develop. Most gains in production ML come not from fancier models but from better features -- starting simple, encoding existing heuristics, and avoiding premature complexity.

The goal is not to invent clever transformations but to reliably deliver correct, fresh, documented features to both training and serving with zero discrepancy between the two paths.

## Start Simple: Heuristics as Features

Most products already have rules that work reasonably well. These existing heuristics are gold -- they encode domain intuition that should not be discarded when transitioning to ML.

There are four ways to use an existing heuristic:

**Preprocess with it:** if a rule is very strong and reliable, apply it before the model even sees the data. Example: block blacklisted senders before the spam model runs.

**Include the score as a feature:** feed the heuristic's output directly into the model as a feature. The model learns how much weight to give it. Example: a ranking model receives the old rule-based score (keyword overlap plus freshness bonus) as one of its input features.

**Use it as a label or pseudo-label:** when labeled data is scarce, heuristic outputs can bootstrap the training set.

**Start raw, refine later:** begin with the heuristic as a baseline, then gradually replace or augment it with learned features as the model matures.

This approach provides a smooth handover from rules to ML with a clear rollback path. If the model underperforms, the heuristic-based system is still available.

## Feature Engineering Techniques for Tabular Data

**Numeric features:** use raw values when the scale is meaningful. Apply log transforms for heavily skewed distributions. Bin into categories when the relationship is non-linear and you want the model to learn step functions. Always save the binning edges or scaling parameters as artifacts.

**Categorical features:** encode using one-hot, ordinal, or target encoding depending on cardinality and model type. For high-cardinality categoricals (thousands of unique values), consider frequency encoding or embedding-based approaches. Handle unknown categories at serving time by mapping them to a dedicated "unknown" bucket.

**Time-based features:** extract day of week, hour of day, month, is-weekend, days-since-event. For cyclical features (hour, day of week), consider sine/cosine encoding to preserve the circular relationship.

**Aggregation features:** compute counts, means, medians, and ratios over time windows. Examples: number of purchases in last 7 days, average session duration over last 30 days, ratio of clicks to impressions this week. These require careful handling of time to avoid data leakage.

**Interaction features:** combine two features to capture relationships the model might miss. Example: price-per-square-foot from price and area. Keep interactions simple and interpretable for first models.

**Text-derived features:** for tabular systems that include text columns, extract simple signals like length, keyword counts, or presence of specific patterns before resorting to embeddings.

## Naming and Documentation

Every feature should have a clear, descriptive name and documentation that answers:

- What does this feature represent in business terms?
- How is it computed? What is the exact logic?
- What are its expected value ranges?
- What data sources does it depend on?
- When was it introduced, and by whom?
- Are there known edge cases or failure modes?

Poor feature naming leads to confusion, bugs, and duplication. A feature called "f_23" tells you nothing; "user_purchase_count_7d" tells you everything.

## Feature Validation

Before a feature reaches the model, validate it:

- **Schema check:** is the type correct (numeric, categorical, boolean)?
- **Range check:** does the value fall within expected bounds? A percentage feature should be between 0 and 1. An age feature should not be negative.
- **Null check:** what fraction of values are null? Is this within the expected range? A sudden spike in nulls often signals an upstream data problem, not a genuine change in the world.
- **Distribution check:** does the distribution match what was seen in training? A feature that was normally distributed during training but is now bimodal may indicate a data pipeline change.
- **Uniqueness and cardinality check:** for categorical features, has the number of unique values changed dramatically?

Fail fast on validation failures. It is better to reject a batch of data than to train or serve on corrupted features.

## Feature Stores

A feature store is a centralized system that computes, stores, and serves features consistently for both training and inference. It solves the fundamental problem of training-serving skew by ensuring the same feature computation logic is used everywhere.

### Online vs. Offline Serving

**Offline (batch) serving:** features are precomputed on a schedule (e.g., nightly) and stored in a table or file. Training reads from this store. Batch inference reads from this store. Good for features that do not need real-time freshness: user profile aggregates, historical counts, precomputed embeddings.

**Online (real-time) serving:** features are computed or retrieved at request time with low latency. Needed when freshness matters: current cart contents, recent click stream, live inventory counts. Typically backed by a key-value store for fast lookups.

**The parity requirement:** the feature computation logic must be identical between the offline path (used for training) and the online path (used for serving). If training computes "average purchase amount over 30 days" one way and serving computes it differently, you have training-serving skew regardless of how sophisticated your model is.

### Point-in-Time Correctness

When building training datasets, features must be computed as of the time the label was generated, not as of "now." If you are predicting whether a user will churn next month, the features should reflect the user's state at the beginning of that month, not their current state. Violating this introduces data leakage -- the model appears to perform well offline but fails in production because it was trained with information from the future.

Feature stores help enforce point-in-time correctness by storing features with timestamps and providing lookups that respect time boundaries.

### Feature Versioning

Features evolve over time. A feature's computation logic may change, its data source may be updated, or its definition may be refined. Version features explicitly:

- When the computation logic changes, create a new version (e.g., user_activity_score_v2) rather than silently modifying the existing feature.
- Record which feature versions were used in each experiment and each production model.
- Maintain backward compatibility: the old version should remain available until all models that depend on it are retrained.

## Time-Series Feature Considerations

Time-series features (rolling averages, trends, seasonal patterns) introduce unique challenges:

**Lookback windows must be consistent:** if training computes a 7-day rolling average, serving must use the same 7-day window, computed the same way (e.g., same handling of missing days, same inclusion/exclusion of the current day).

**Freshness requirements:** some time-series features can be precomputed nightly; others need real-time updates. Design your feature pipeline around the freshness your use case actually requires, not the freshest you could theoretically provide.

**Cold-start handling:** new entities (new users, new products) have no history. Define explicit cold-start strategies: use population-level defaults, use the most similar cohort's features, or use a separate cold-start model.

**Data leakage from aggregation:** when computing aggregate features for training, ensure the aggregation window does not include the label period. A feature "number of returns in the last 30 days" used to predict "will this customer return an item" must not include the return event being predicted.

## Training-Serving Parity for Features

The single most important principle in feature engineering for production ML: identical inputs must produce identical feature values in training and serving.

Common parity failures and their fixes:

- **Preprocessing statistics recomputed online:** training standardizes features using training-set mean and variance. Serving recomputes mean/variance from live traffic, producing different scaled values. Fix: save training statistics as artifacts and load them in serving.
- **Different code paths:** training uses a Python script, serving uses a Java microservice, and the logic has subtle differences. Fix: use a shared feature computation library, or compute features once and store them in a feature store.
- **Missing feature handling differs:** training fills nulls with the training-set median. Serving fills nulls with zero. Fix: define null-handling logic once and enforce it in both paths.
- **Time zone or rounding differences:** training data is in UTC, serving data is in local time. Fix: standardize on one time zone throughout the pipeline.

## When to Use This

- You are designing the feature set for a new model and need to decide which features to include and how to compute them.
- You are experiencing training-serving skew and need to diagnose whether features are the cause.
- Your team is computing features in multiple places (notebooks, scripts, serving code) and wants to centralize.
- You need to serve features with low latency for a real-time model.
- You are building time-series features and need to avoid data leakage.

## Red Flags to Watch For

- Features are computed differently in training and serving code paths with no parity test.
- Preprocessing statistics (means, variances, bin edges) are recomputed from live data instead of loaded from training artifacts.
- No feature validation exists -- null spikes or out-of-range values silently reach the model.
- Features have cryptic names with no documentation of their meaning or computation logic.
- Time-series features do not respect point-in-time correctness, leaking future information into training.
- The team is adding complex interaction features or embeddings before establishing a baseline with simple features.
- New features are added to the model without versioning, making it impossible to know which features a specific model version used.
- There is no cold-start strategy for new entities that lack historical features.
- Categorical features have no handling for unseen categories at serving time.
