# Data Drift and Concept Drift

## Core Principle

A model that was good at launch can silently degrade as the world changes. The grocery demand forecasting case is instructive: a good model launched, the world changed and inputs drifted, there was no early warning on shifts, and waste and lost sales followed. Drift detection is not optional infrastructure -- it is the early warning system that prevents silent model failure.

## Types of Drift

### Data Drift (Covariate Shift)

Data drift occurs when the distribution of input features changes between training and serving, but the underlying relationship between features and the target remains the same. The model was trained on one population and is now seeing a different one.

Examples: a new user demographic enters the product, seasonal patterns shift purchasing behavior, a partner changes the format of data they send, or an upstream pipeline introduces missing values where there were none before.

Data drift is about P(X) changing. The model may still be correct in principle, but it is operating in a region of feature space where it has little training data and therefore low confidence.

### Concept Drift

Concept drift occurs when the relationship between inputs and the target changes. Even if the input distribution stays the same, the correct prediction for a given input is now different. P(Y|X) has changed.

Examples: user preferences shift (what was popular is no longer), a regulatory change alters which transactions are fraudulent, an economic shift changes the relationship between income and spending, or a competitor enters the market and changes conversion dynamics.

Concept drift is harder to detect than data drift because it requires ground-truth labels to confirm. By the time you have labels, the damage may already be done.

### Gradual vs Sudden Drift

- **Gradual drift**: slow, continuous change over weeks or months. Typical in user behavior, market conditions, and seasonal patterns. Can be addressed with periodic retraining on a schedule.
- **Sudden drift**: abrupt change caused by an event -- a product launch, a policy change, a pandemic, a data pipeline bug. Requires immediate detection and rapid response.
- **Recurring drift**: cyclical patterns (weekday vs weekend, holiday seasons). Can sometimes be anticipated and handled with time-aware features or separate models.

## Detection Strategies

### Statistical Tests for Feature Distributions

Monitor each input feature's distribution over time. Compare the current serving distribution to a reference distribution (typically the training set or a recent stable window).

- **Kolmogorov-Smirnov (KS) test**: compares two continuous distributions. Good general-purpose test. Reports the maximum distance between cumulative distribution functions.
- **Chi-squared test**: for categorical features. Compares observed vs expected category frequencies.
- **Population Stability Index (PSI)**: widely used in financial ML. Measures how much a distribution has shifted. PSI < 0.1 is typically stable, 0.1-0.25 is moderate shift, > 0.25 is significant.
- **Jensen-Shannon divergence**: symmetric measure of distribution difference. Works for both continuous and discrete distributions.
- **Wasserstein distance (Earth Mover's Distance)**: measures the cost of transforming one distribution into another. More sensitive to the shape of the shift than KS.

### Monitoring Prediction Distribution

Even without ground truth, monitor the distribution of model predictions. If the prediction distribution shifts significantly while you have not intentionally changed the model, something in the input pipeline or feature distributions has changed. This is an indirect but fast signal.

### Performance-Based Detection

When ground-truth labels become available (even with delay), compare model performance metrics on recent data against the training baseline or a rolling window. A sustained drop in precision, recall, AUC, or business metrics signals concept drift.

For systems with fast feedback loops (clicks, conversions), this can be near-real-time. For systems with slow labels (fraud confirmed weeks later), use proxies and monitor them alongside eventual ground truth.

### Window-Based Monitoring

Use sliding windows to compare distributions:
- **Fixed reference window**: compare current data against the training set distribution. Simple and stable, but the reference grows stale over time.
- **Sliding reference window**: compare current data against a recent window (e.g., last 30 days vs the 30 days before that). Detects relative change but may miss gradual long-term drift.
- **ADWIN (Adaptive Windowing)**: automatically adjusts window size based on detected change rate. More sophisticated but harder to implement.

## Retrain Triggers

Not every detected drift requires retraining. Design a trigger framework:

### Automatic Retrain Triggers
- Feature drift exceeds threshold (e.g., PSI > 0.25) on multiple important features simultaneously.
- Prediction distribution shift exceeds threshold with no corresponding model or pipeline change.
- Ground-truth performance metrics drop below a defined floor for a sustained period.
- Business KPI degrades beyond an acceptable margin.

### Scheduled Retraining
- For domains with known seasonality or gradual drift, retrain on a fixed schedule (weekly, monthly) using fresh data.
- The schedule should be informed by the observed drift velocity in your domain.

### Manual Review Triggers
- A known external event occurs (new product launch, regulatory change, market shift) that is expected to change the data distribution or concept.
- A single feature shows extreme drift but overall performance has not yet degraded -- investigate before retraining.

## Response Playbook

When drift is detected:

1. **Verify it is real drift, not a pipeline bug.** Check upstream data pipelines, schema changes, missing value patterns, and join failures. Many apparent drifts are actually data engineering issues.
2. **Assess severity.** Is it affecting business metrics or just feature distributions? Is it affecting all segments or just one?
3. **Determine the type.** Is it data drift (input distribution changed) or concept drift (relationship changed)? This determines the response.
4. **For data drift**: retrain on recent data that includes the new distribution. If the shift is in a specific segment, consider segment-specific models or feature engineering to handle the new regime.
5. **For concept drift**: retraining may not suffice if the relationship has fundamentally changed. May need to revise the feature set, adjust the label definition, or re-frame the problem.
6. **Validate the fix.** After retraining, compare the new model's performance on recent data against the old model. Deploy with a canary or shadow mode before full rollout.
7. **Update the reference distribution.** Reset the drift detection baseline to reflect the new normal.

## Guardrails for Feedback Loops

In systems where model predictions influence future training data (recommenders, ad targeting, fraud systems), drift detection must account for self-reinforcing loops. A model that under-recommends a category will collect fewer positive signals for that category, reinforcing the under-recommendation.

**The feedback loop danger is particularly insidious in high-stakes domains:** A lending model that rejects applicants from certain neighborhoods creates a data void -- it never observes whether those applicants would have repaid. Future training data confirms the model's bias (all observed defaults come from approved applicants), creating a self-fulfilling discriminatory cycle. The model's predictions literally shape the reality it learns from.

**Guardrails against feedback loops:**
- Inject exploration: reserve a percentage of decisions for random or rule-based processing, ensuring the model observes outcomes it would not have chosen
- Monitor diversity metrics: track whether predictions are becoming increasingly concentrated in a narrow range
- Compare against holdout populations not exposed to model predictions
- Log counterfactual predictions: record what the model would have predicted for cases handled differently, enabling offline evaluation of alternative policies
- Periodically audit model behavior across demographic slices for emerging bias patterns

## When to Use This

- When deploying any model to production (drift monitoring should be part of the launch checklist).
- When a production model's business metrics degrade without any code or model changes.
- When an external event is expected to change user behavior or data patterns.
- When deciding on a retraining schedule for a production model.
- When investigating whether a model needs retraining or a fundamentally different approach.
- When building the monitoring dashboard for a new ML system.

## Red Flags to Watch For

- No drift monitoring exists for a production model.
- Only model-level metrics are monitored, with no feature-level distribution tracking.
- Retraining is purely calendar-based with no data-driven triggers.
- Drift alerts fire but no one investigates or responds.
- A sudden drift is assumed to be "real" without first checking for pipeline bugs or data quality issues.
- The reference distribution for drift detection has never been updated since initial training.
- Ground-truth labels arrive with long delay but no proxy metrics are monitored in the interim.
- Feedback loop effects are not accounted for in systems where predictions influence future data.
- The team retrains on drifted data without investigating whether the concept (not just the distribution) has changed.
- Performance degradation is attributed to "the model getting old" without diagnosing whether the cause is data drift, concept drift, or a pipeline issue.
