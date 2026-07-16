# Generalization Skill

## Settings
```
OVERFITTING_RISK = 5         # How likely is this model to overfit?
                             # 1-3: Simple model, lots of data — low risk
                             # 4-7: Moderate complexity, medium data — worth monitoring
                             # 8-10: Complex model, small data — high risk, regularize aggressively

REGULARIZATION_NEED = 5      # How much regularization is needed?
                             # 1-3: None — data is large enough relative to complexity
                             # 4-7: Standard Ridge/Lasso or dropout
                             # 8-10: Aggressive — ensemble regularization, early stopping, data augmentation

ASSUMPTION_STRICTNESS = 5    # How rigorously must model assumptions hold?
                             # 1-3: Research / exploration — some violation is fine
                             # 4-7: Internal tool — document and account for violations
                             # 8-10: Production / regulated — must pass before deployment
```

---

## What this prevents

Two failure modes. Both are silent.

**Overfitting:** The model memorizes training data instead of learning patterns. Looks perfect in development. Fails on real data.

**Violated assumptions:** The model's assumptions about the data don't hold. It produces predictions that look plausible, pass RMSE checks, and lead to decisions made with false precision — confident and wrong.

---

## Part 1: Overfitting

### The three scenarios

```
Underfitting                 Just Right                Overfitting
(too simple)                 (generalizes)             (memorizes)

High train error             Low train error           Near-zero train error
High test error              Low test error            High test error

Straight line through        Gentle curve through      Wild curve through
curved data                  real pattern              every training point
```

### Bias vs Variance

**Bias** = how far is your model's average prediction from the truth?
- High bias → too simple → underfitting → systematic wrong answers

**Variance** = how much do predictions change when trained on different data?
- High variance → too complex → overfitting → memorizing noise

The tradeoff: reducing bias (more complexity) increases variance. Reducing variance (less complexity) increases bias. The sweet spot is where total error is minimized.

### Detecting overfitting

**Train-test performance matrix:**

| Training error | Test error | Diagnosis | Action |
|---|---|---|---|
| Low | Low | Generalizes well | Ship it |
| Low | High | Overfitting | Regularize, simplify, or get more data |
| High | High | Underfitting | More features, more complexity, more training |
| High | Low | Data problem | Check for leakage or sampling bias |

**K-fold cross-validation:**
Split data into K folds. Train on K-1, test on the remaining 1. Rotate K times. Average the scores. Every data point gets tested exactly once.

More reliable than a single train-test split because it uses all data for both training and evaluation.

---

## Part 2: Regularization

### The intuition

Overfitting produces wild, extreme parameter values. A weight of w = 50,000 means the model is amplifying tiny input changes into massive output swings.

The fix: penalize the model for having large weights. Add a "simplicity tax" to the loss function.

### Ridge Regression (L2)
```
Loss = MSE + λ × Σ(w²)
```
- Penalizes large weights by adding their square to the loss
- All weights shrink toward zero, but **none reach exactly zero**
- Every feature still participates in the prediction
- Use when: all features probably matter, want a stable model

### Lasso Regression (L1)
```
Loss = MSE + λ × Σ|w|
```
- Penalizes large weights by adding their absolute value to the loss
- Pushes some weights to **exactly zero** — automatic feature selection
- Tells you: "Out of your 50 features, only these 12 matter"
- Use when: many features, many probably irrelevant

### Elastic Net (L1 + L2 combined)
```
Loss = MSE + λ₁ × Σ|w| + λ₂ × Σ(w²)
```
- Handles correlated features better than Lasso alone
- Lasso arbitrarily picks one from a correlated group; Elastic Net keeps both (partially)
- Use when: unsure, or when you have groups of correlated features

### The λ (lambda) trade-off

| λ value | Effect |
|---|---|
| λ = 0 | No regularization — standard regression |
| λ small | Gentle nudge toward simplicity |
| λ large | Strong penalty — weights collapse toward zero |
| λ = ∞ | All weights = 0 — model predicts the mean for everything |

**How to choose λ:** Cross-validation. Try a range (0.001, 0.01, 0.1, 1, 10, 100), pick the one with the best validation RMSE.

### Regularization in other algorithms

| Algorithm | Regularization mechanism | What "simpler" means |
|---|---|---|
| Linear regression | L1/L2 on weights | Fewer features, smaller weights |
| Decision trees | Max depth, min samples per leaf | Fewer splits, broader rules |
| Random forest | Number of features considered per split | Less memorization per tree |
| Neural networks | Dropout, weight decay, early stopping | Fewer active neurons, smaller weights |
| XGBoost | max_depth, learning rate, subsample | Shallower trees, less aggressive boosting |

---

## Part 3: Model assumption diagnostics

A model with violated assumptions doesn't fail loudly. It gives confidently wrong answers.

Run this diagnostic suite after every regression training run:

### Diagnostic 1: Residuals vs Predicted
```
Plot: (predicted - actual) on y-axis, predicted on x-axis

What to look for:
- Random scatter → linearity and homoscedasticity hold ✓
- Curved pattern → non-linearity → add polynomial terms
- Funnel/fan shape → heteroscedasticity → log-transform target
- Clusters → model is missing subgroup structure
```

### Diagnostic 2: Q-Q Plot
```
Plot: theoretical quantiles vs sample quantiles of residuals

What to look for:
- Points on diagonal line → residuals approximately normal ✓
- S-curve (heavy tails) → more extreme errors than expected
- Curves at one end → skewed residuals
```

### Diagnostic 3: VIF (Variance Inflation Factor)
```
Checks for multicollinearity — features that are too similar to each other

VIF < 5: fine
VIF 5–10: monitor
VIF > 10: serious — remove one from the correlated pair

Fix: remove the feature with lower standalone correlation to target,
or combine them into a domain-meaningful ratio (BMI from height+weight)
```

### Diagnostic 4: Cook's Distance
```
Identifies data points that are disproportionately pulling the model

High Cook's Distance (> 4/n):
- Investigate the row: which features are extreme?
- Is it a data entry error? → investigate and possibly fix
- Is it a legitimate edge case? → document as known limitation
- If removed, how much does the model change? → refit and compare

Do NOT auto-remove high-influence points. Investigate first.
They are often the most informative data points.
```

### Diagnostic 5: Residuals over time (temporal data)
```
If data has a time dimension, plot residuals in time order

What to look for:
- Random scatter → independence holds ✓
- Wave pattern → autocorrelation → add lag features or use ARIMA
- Trend in residuals → model is missing a trend → add trend feature
- Residuals worsening toward end of test period → distribution shift
  → model may need retraining on more recent data
```

---

## Quick reference: violations and fixes

| Diagnostic | What you see | Assumption violated | Fix |
|---|---|---|---|
| Residuals vs Predicted | Curved pattern | Linearity | Add polynomial terms |
| Residuals vs Predicted | Funnel shape | Homoscedasticity | Log-transform target |
| Residuals vs Predicted | Clusters | Subgroup structure | Segment the model |
| Q-Q Plot | S-curve | Normality | Robust loss, quantile regression |
| VIF Table | VIF > 10 | No multicollinearity | Remove correlated feature |
| Residuals vs Time | Wave pattern | Independence | Lag features, ARIMA |
| Cook's Distance | High value | — | Investigate influential point |

---

## Prompt templates

### Overfitting detection
```
Train the model and diagnose overfitting:

1. Plot train and validation loss curves overlaid on the same chart.
   Label clearly: training = solid, validation = dashed.
   Tell me: where does the gap start opening (if at all)?

2. Report: train RMSE, validation RMSE, test RMSE.
   If train RMSE << test RMSE, we have overfitting.

3. Run 5-fold cross-validation.
   Report: mean CV RMSE ± standard deviation.
   High std = high variance model.

Diagnosis: state whether the model is underfitting, just right, or overfitting.
```

### Regularization sweep
```
Compare regularized vs unregularized models:

1. Baseline: Linear Regression (no regularization)
2. Ridge: try λ ∈ [0.01, 0.1, 1, 10, 100] using 5-fold CV
3. Lasso: try same λ range using 5-fold CV
   Also report: how many features did Lasso zero out at each λ?
4. Elastic Net: try l1_ratio ∈ [0.1, 0.5, 0.9] with optimal λ

Report as table:
| Model | Best λ | CV RMSE | Test RMSE | Features kept |
Show which model generalizes best to test data.
```

### Full diagnostic suite
```
Run the full diagnostic suite after training:

1. RESIDUALS VS PREDICTED — scatter plot. Describe: random / curved / funnel / clusters?
2. Q-Q PLOT — are residuals approximately normal?
3. RESIDUALS VS EACH FEATURE — flag any feature with a pattern (needs transformation)
4. VIF TABLE — flag VIF > 5. Suggest which to remove.
5. COOK'S DISTANCE — print top 10 most influential rows with their feature values.
6. RESIDUALS OVER TIME (if temporal) — plot in time order. Any wave patterns?

For each violation: name the assumption, explain the business impact, and suggest the specific fix.
```

### Neural network regularization
```
This model is overfitting (train loss << val loss).
Apply regularization in this order:

1. Add dropout (rate = 0.3) after each hidden layer
2. Add L2 weight decay (λ = 0.001) to the optimizer
3. Add early stopping: patience = 10, restore best weights
4. Reduce model capacity: [current hidden sizes] → [reduced sizes]

After each step, retrain and compare train vs val loss curves.
Stop when the gap between train and val loss is acceptable.
Report: which combination of regularization gave the best val RMSE?
```

---

## Anti-patterns

- Never celebrate low training loss without checking test loss
- Never choose model complexity before checking if simpler models generalize
- Never skip cross-validation on small datasets (single train-test split has high variance)
- Never use accuracy alone on imbalanced data — it hides the overfitting on the minority class
- Never skip diagnostics because "the RMSE looks fine" — violations fail silently
- Never auto-remove influential points — investigate them
- Never use confidence intervals from a model with heteroscedasticity — they're mathematically wrong

---

## The principle

A model that memorizes is not a model. It is a lookup table with extra steps.

Generalization — the ability to perform well on data the model has never seen — is the only thing that matters for any real use case. Everything in training (regularization, cross-validation, diagnostics) is in service of one question: will this model work on new data?

The diagnostics exist because a model cannot tell you about its own limitations. That responsibility belongs to the builder.
