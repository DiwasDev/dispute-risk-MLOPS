# Loss Design Skill

## Settings
```
COST_ASYMMETRY = 5           # How different are over vs under-prediction costs?
                             # 1-3: Symmetric — wrong in either direction costs the same
                             # 4-7: Moderate — one direction is somewhat worse
                             # 8-10: Highly asymmetric — one type of mistake is catastrophically worse

OUTLIER_SENSITIVITY = 5      # How much do rare but extreme errors matter?
                             # 1-3: Outliers acceptable — care about typical case
                             # 4-7: Outliers matter — don't want any catastrophic misses
                             # 8-10: Outliers dominate — one massive error destroys value

BUSINESS_CLARITY = 5         # How well-defined is the cost of errors?
                             # 1-3: No cost structure — use default and revisit
                             # 4-7: Rough costs known — encode directionally
                             # 8-10: Exact costs known — encode precisely in loss
```

---

## What this prevents

The AI defaults to MSE for every regression problem. Always. Without asking.

MSE says: "Being off by Rs 10,000 is exactly 100× worse than being off by Rs 1,000."

That is sometimes right. Usually it's wrong. Your business has a cost structure — and MSE almost certainly doesn't match it. A model trained with the wrong loss function will optimize for the wrong objective, look fine on metrics, and quietly fail the actual business need.

---

## Core rule: establish the cost structure before choosing the loss

Answer these before writing any model code:

**Q1. What is the cost of over-predicting? Under-predicting?**
- Too much inventory: waste, storage cost
- Too little inventory: lost sales, customer frustration
- Are these equal? Almost never.

**Q2. Is a large error much worse than a small one, or equally bad?**
- Medical dosing: 10× error is not 10× worse — it's potentially lethal
- Delivery estimate: 2 days off vs 4 days off may feel identical to the customer

**Q3. Do you care about the typical case or the worst case?**
- Insurance: you need to cover catastrophic claims, not just average ones
- Customer satisfaction: you care about everyone's experience

**Q4. Is there a threshold that matters more than anything else?**
- "Within 10%, the business is fine"
- "Miss by more than 3 days and the customer cancels"

---

## Loss function decision guide

| Situation | Use this | Why |
|---|---|---|
| Errors equally costly both ways | MSE | Standard, punishes large errors more |
| Outliers exist, don't want them to dominate | MAE | All errors equal, robust to outliers |
| Under-prediction worse than over | Asymmetric / pinball loss | Directly encodes direction penalty |
| Need to cover X% of cases | Quantile loss at Xth percentile | "Prediction below actual X% of the time" |
| Large errors catastrophically bad | MSE or Huber | Squaring punishes big errors heavily |
| Large errors acceptable, typical matters | MAE | Flat penalty, not outlier-dominated |
| Outliers AND asymmetry | Huber + asymmetric weighting | Best of both |

---

## Real-world loss design examples

### Delivery time prediction
```
Over-prediction (arriving early): no cost
Under-prediction (arriving late, 1 day): Rs 500 in refunds
Under-prediction (arriving late, 3+ days): Rs 2,000 + churn risk

MSE is wrong — treats early and late identically.
Use asymmetric loss: under-prediction penalized 3–4× more.
Result: model deliberately forecasts conservatively.
Under-promise, over-deliver, built into the math.
```

### Perishable goods demand
```
Over-ordering 1 unit = Rs 50 wasted
Under-ordering 1 unit = Rs 200 lost sale + unhappy customer

Under-ordering is 4× worse.
Use quantile loss at the 80th percentile.
Model forecasts slightly high, covers 80% of actual demand,
rarely runs out of stock.
```

### Insurance reserve setting
```
Finance team needs to cover 95% of claims in reserves.
Don't care about the average claim — care about the tail.

Use quantile loss at the 95th percentile.
Model predicts: "What amount will 95% of claims fall below?"
Not expected value — the safe upper bound.
```

---

## The loss-metric consistency rule

These three must be aligned or your results are meaningless:

| Train with | Evaluate with | Not with |
|---|---|---|
| MSE | RMSE (same units as target) | Accuracy |
| MAE | MAE, MAPE | RMSE (skewed by outliers) |
| Asymmetric loss | Total business cost | RMSE |
| Quantile loss | Coverage % | RMSE |
| Cross-entropy | Log-loss, AUC-ROC | MSE |

If you train with asymmetric loss and evaluate with RMSE, you're measuring the wrong thing. The model optimized correctly — you scored it incorrectly.

---

## Prompt templates

### Defining the cost structure
```
Before choosing a loss function, define the cost structure:

Over-prediction (model predicts higher than actual):
- What happens in the real world? [...]
- Cost per unit of error: Rs [...]

Under-prediction (model predicts lower than actual):
- What happens in the real world? [...]
- Cost per unit of error: Rs [...]

Symmetric? [Yes / No]
Catastrophic threshold beyond which errors are a different category? [...]

Recommend:
1. The right loss function for this cost structure
2. How to implement it (sklearn / PyTorch / TensorFlow)
3. A baseline MSE model to compare against
```

### Implementing asymmetric loss
```
Our cost structure:
- Over-prediction penalty: Rs X per unit
- Under-prediction penalty: Rs Y per unit
- Ratio Y/X = [ratio]

Implement:
1. Custom asymmetric loss with penalty ratio [ratio]
2. Standard MSE model as baseline
3. Compare both on:
   - RMSE (technical)
   - Total estimated cost using penalty structure (business)
   - % of predictions in the "expensive" direction
Show comparison as a table.
```

### Quantile loss for coverage problems
```
We need our forecast to cover [X]% of actual demand.
This is a coverage problem, not an average prediction problem.

Implement:
1. Quantile regression at the [X]th percentile
2. Standard MSE model as baseline
3. Evaluate both on:
   - % of actuals that fell below prediction (should be ~X%)
   - Average over-prediction (cost of excess inventory)
   - Average under-prediction (cost of shortage)
   - Total cost: over = Rs A/unit, under = Rs B/unit
```

### Comparing loss functions
```
Train the same model architecture with 3 different loss functions:
1. MSE (baseline)
2. MAE (outlier-robust)
3. Huber loss (delta = [value])

For each report:
- Training loss curve (all 3 overlaid)
- Test RMSE and MAE
- Error distribution histogram (show the shape differences)
- Worst 10 prediction errors

I'll decide based on which error distribution matches my business tolerance.
```

---

## Anti-patterns

- Never default to MSE without establishing the cost structure first
- Never train with one loss and evaluate with a completely different metric
- Never use MAE when large errors are catastrophically worse than small ones
- Never use MSE when your data has significant outliers you don't care about
- Never report only technical loss to stakeholders — always translate to cost in their units
- Never use the same loss for all targets in a project — each prediction may have different costs

---

## The principle

The loss function is not a technical detail. It is a business decision encoded in mathematics.

The model minimizes exactly what you tell it to minimize. If you tell it to minimize MSE, it produces predictions that minimize average squared error — not predictions that minimize your inventory waste, customer churn, or refund costs.

Nobody else can make this decision. The agent doesn't know your cost structure. You do. Encode it.
