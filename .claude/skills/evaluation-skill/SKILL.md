# Evaluation Skill

## Settings
```
STAKEHOLDER_LEVEL = 5        # Who reads the evaluation report?
                             # 1-3: Non-technical (CEO, ops, finance)
                             # 4-7: Semi-technical (PM, analyst, team lead)
                             # 8-10: Technical (data scientist, engineer)

BASELINE_EXISTS = 5          # Is there a current process to compare against?
                             # 1-3: No existing process — first-time prediction
                             # 4-7: Manual process exists but not measured
                             # 8-10: Measured baseline exists (manual forecasts, rule-based system)

DECISION_STAKES = 5          # How consequential are the decisions made from predictions?
                             # 1-3: Low stakes — informational, no hard action
                             # 4-7: Medium — resource allocation, scheduling
                             # 8-10: High stakes — financial commitments, patient safety, legal
```

---

## What this prevents

The AI reports RMSE by default. Always.

Your manager, your client, your CEO — none of them know what RMSE means. None of them care. They care about: "Is this better than what we do today? How much money does it save? How many bad outcomes does it prevent?"

Reporting RMSE to a business stakeholder is like telling someone their car's fuel efficiency in joules per meter. Technically correct. Completely useless for making a decision.

---

## Core rule: always produce two sets of metrics

**Set 1 — Technical metrics** (for you, to debug and improve the model)
- RMSE: average magnitude of error in original units
- MAE: median-robust alternative
- R-squared: % of variance explained
- MAPE: % error (useful when scale varies across predictions)

**Set 2 — Business metrics** (for stakeholders, to justify the project and make decisions)
- Cost impact in currency
- Comparison to current process / baseline
- % of predictions within an acceptable tolerance
- Number of avoided bad outcomes

If you can only produce one set, produce the business metrics.

---

## Metric reference

### Regression metrics

| Metric | What it tells you | When to prefer |
|---|---|---|
| RMSE | Average magnitude of error, in original units | When large errors are catastrophic |
| MAE | Average absolute error, all errors equal weight | When outliers exist and you care about typical case |
| R-squared | Fraction of variance explained (1.0 = perfect) | When you want a quality percentage |
| MAPE | Average % error | When relative error matters more than absolute |

**Intuitive translations:**
- RMSE = Rs 2,300 → "On average, predictions are off by Rs 2,300"
- R² = 0.85 → "Model explains 85% of variation; 15% is noise or missing features"
- MAPE = 8% → "Predictions are typically within 8% of the actual value"

### Classification metrics

| Metric | What it tells you |
|---|---|
| Accuracy | % of all predictions correct (misleading for imbalanced data) |
| Precision | When we predict positive, how often are we right? |
| Recall | Of all actual positives, what % did we catch? |
| F1 | Harmonic mean of precision and recall |
| AUC-ROC | At random, how often do we rank a positive above a negative? |

---

## Translating to business metrics

| Technical metric | Business translation |
|---|---|
| RMSE = Rs 2,300 | "Inventory planning off by Rs 2,300/order. At 500 orders/month = Rs 11.5L/month avoidable waste" |
| MAPE = 8% | "Within 8% of actual. For a Rs 1Cr order, off by Rs 8L on average" |
| Recall = 0.74 | "We catch 74% of churners before they leave. At Rs 8K lifetime value and 100 churners/month = Rs 5.9L recoverable revenue" |
| R² = 0.85 | "85% of price variation explained. Unexplained 15% is noise we'd need more data to capture" |

---

## The baseline comparison framework

Always answer: "Is this better than what we do today?"

| Baseline type | How to measure |
|---|---|
| No model (predict the mean) | R² = 0.0 by definition. Any positive R² beats this. |
| Simple rule (IF-ELSE) | Build it, measure its RMSE/accuracy, compare |
| Manual human process | Collect historical manual predictions, measure their error |
| Previous ML model | Keep old model's metrics as the bar to beat |
| Naive time-series (last period's value) | "Next month = this month." Measure error. |

If the model doesn't beat the baseline in business terms, it should not ship — even if its RMSE is lower.

---

## Stakeholder-specific reporting formats

### Non-technical (STAKEHOLDER_LEVEL 1–3)
```
One-page summary:
1. What we built: [one sentence]
2. How it compares to current process: [% improvement or Rs saved]
3. Confidence: [% of predictions within acceptable range]
4. Recommendation: [ship / needs X before shipping]

Exclude: RMSE, R-squared, confusion matrix, AUC
```

### Semi-technical (STAKEHOLDER_LEVEL 4–7)
```
Summary dashboard:
1. Business metric: Rs impact vs baseline
2. Coverage: % within acceptable tolerance
3. Worst cases: top 10 biggest misses and their impact
4. Reliability: consistent performance across time periods / segments?

Include: MAPE and MAE (intuitive). Explain before including R-squared or AUC.
```

### Technical (STAKEHOLDER_LEVEL 8–10)
```
Full technical report:
- All metrics: RMSE, MAE, R², MAPE
- Baseline comparison table
- Performance by segment and time period
- Error distribution histogram
- Residual analysis
- Feature importances
- Confidence intervals where applicable
```

---

## The segment performance trap

A model with good overall RMSE can be catastrophically bad on the segments that matter most.

Example: Predicting loan default. Overall accuracy = 91%.
- Accuracy on low-risk customers (80% of data): 97% ✓
- Accuracy on high-risk customers (20% of data): 64% ✗

The model is excellent at predicting people who will repay (easy, majority class). It's terrible at predicting default — the entire point of the exercise.

**Always break down performance by the segments where errors are most costly.**

---

## Prompt templates

### Business evaluation design
```
Evaluate with both technical and business metrics.

Technical (for our debugging):
- RMSE, MAE, R-squared on the test set

Business (for the stakeholder):
1. % of predictions within ±[X]% of actual
2. Total cost of prediction errors on test set:
   - Over-prediction: Rs [A] per unit
   - Under-prediction: Rs [B] per unit
3. Compare against baseline [describe current process]:
   show which method had lower total cost

Final table:
| Method | RMSE | Total error cost (Rs) | % within tolerance | Recommended? |
```

### Month-by-month breakdown
```
For the test period, produce:

| Month | Actual | Predicted | Error | % Error | Cost of error |
|-------|--------|-----------|-------|---------|--------------|
| Jan   | ...    | ...       | ...   | ...     | ...          |
...
| TOTAL | ...    | ...       | ...   | ...     | ...          |

Add a row for the current manual forecasting method if data is available.
Final row: "Model saves Rs X vs current process on this test period."

This is the format for the manager presentation.
```

### Multi-model comparison for stakeholders
```
I tested 3 models. Produce a comparison for non-technical stakeholders:

| Model | Plain English description | % within 10% | Cost of errors (Rs) | Recommended? |
|-------|--------------------------|---------------|---------------------|-------------|
| Linear Regression | Straight-line pattern | ... | ... | ... |
| Ridge | Adjusted for complexity | ... | ... | ... |
| Random Forest | Pattern-learning ensemble | ... | ... | ... |

Recommended model: [name]
One-sentence reason a manager would understand: [...]
```

### Segment performance analysis
```
Break down model performance by:
- [Segment 1: e.g., product category / customer tier / region]
- [Segment 2: e.g., high-value vs low-value transactions]

For each segment:
- Sample size
- RMSE and MAE
- % of predictions within tolerance

Flag any segment where performance is significantly worse than average.
These are segments where the model should not be used yet, or where
additional training data is needed.
```

---

## Anti-patterns

- Never report only RMSE to a non-technical stakeholder
- Never celebrate model accuracy without comparing to a baseline
- Never report overall accuracy without checking segment performance
- Never present a model as "ready to ship" without a business cost estimate
- Never use accuracy alone for imbalanced classification
- Never omit the worst-case errors — they're often what kills the project in production
- Never compare two models using different metrics — standardize on one business metric for the final decision

---

## The principle

The metric you optimize during training and the metric you report to stakeholders are two different things, and they should be.

You optimize technical metrics to make the model better. You report business metrics to justify the project, make deployment decisions, and demonstrate value.

A model that reduced RMSE by 12% is a technical achievement. A model that saved Rs 2.3Cr per quarter in inventory waste is a business achievement. Both describe the same model. Only one gets budget approved.
