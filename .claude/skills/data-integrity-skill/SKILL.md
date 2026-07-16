# Data Integrity Skill

## Settings
```
DATA_IS_TEMPORAL = 5         # Does the data have a time dimension?
                             # 1-3: No time — customer profiles, product specs
                             # 4-7: Some time — cohort data, versioned records
                             # 8-10: Fully temporal — sales, prices, events, logs

GROUP_SENSITIVITY = 5        # Can the same entity appear in train and test?
                             # 1-3: Each row is independent (single product review)
                             # 4-7: Some grouping (multiple purchases per customer)
                             # 8-10: Strong grouping — same entity must NEVER be in both sets

PRODUCTION_RISK = 5          # How bad is a silent failure in production?
                             # 1-3: Internal experiment, no real decisions
                             # 4-7: Internal tool, wrong outputs are inconvenient
                             # 8-10: Customer-facing, financial, or medical — silent failure is catastrophic
```

---

## What this prevents

Data leakage is the #1 cause of models that work in notebooks but fail in production.

The model looks amazing during testing. 98% accuracy. Everyone celebrates. It ships. It's useless. Or worse — it's confidently wrong on real decisions.

Why? The training data accidentally contained information that would not exist at prediction time in the real world.

The agent will never catch this. It will build, train, evaluate, and report great metrics — without ever checking if those metrics are real.

---

## Three types of leakage

### Type 1: Future data in training (temporal leakage)
A feature that, in real life, you would only know AFTER the event you're predicting.

**Test for every feature:**
> "At the exact moment I need to make a prediction in production, would I actually have this value?"

| Scenario | The leak | Why it destroys |
|---|---|---|
| Predicting hospital readmission | "Follow-up appointment scheduled" | Appointments are booked after discharge |
| Predicting customer churn | "Customer contacted support to cancel" | By the time this exists, it's too late |
| Predicting loan default | "Number of debt collection calls received" | Calls happen after default begins |
| Predicting exam score | "Hours spent reviewing correct answers" | Students review after the exam |
| Forecasting sales | Random split on monthly time-series | Future months leak into training |

### Type 2: Wrong split type (contamination)
A random split on structured data causes future or related information to leak.

- **Time-series + random split:** model trains on December to predict January, and also trains on January to predict December. Future leaks into past.
- **Customer data + random split:** same customer in train and test. Model memorizes customer-specific patterns. Fails completely on new customers.
- **Geographic data + random split:** same city in both. Fails on new cities.

### Type 3: Preprocessing leakage (the subtle one)
Every step that "learns from data" must be fitted only on training data.

**Wrong:**
```python
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)        # fits on ALL data including test
X_train, X_test = train_test_split(X_scaled)
```

**Right:**
```python
X_train, X_test = train_test_split(X)     # split FIRST
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)   # fit on train only
X_test_scaled = scaler.transform(X_test)          # apply to test
```

Same rule applies to: imputers, encoders, PCA, target encodings, feature selection that uses the target.

---

## The correct split for every situation

| Real-world use case | Wrong split | Right split |
|---|---|---|
| Predicting tomorrow from today | Random 80/20 | Time-based: train months 1–10, test 11–12 |
| Predicting for NEW customers | Random (same customer in both) | Group-based: customer IDs never shared |
| Predicting for new cities/regions | Random (same city in both) | Geographic: hold out entire cities for test |
| Drug trial outcome | Random | Patient-based: no patient in both sets |
| Next quarter revenue | Random | Temporal: always train before test |

**The principle:** The split must mirror how the model will be used in production. If it predicts the future, training must come before test in time. If it predicts for new entities, those entities must be absent from training.

---

## Leakage warning signs

| Signal | Likely cause |
|---|---|
| Accuracy > 95% on first try | Strong leakage. Real-world data is messy. |
| A feature has correlation > 0.95 with the target | Feature may directly encode the target. |
| Huge accuracy drop from notebook to production | Training distribution didn't match production. |
| Model degrades over time | Temporal leakage — memorized past, can't generalize to future. |
| Great on existing customers, fails on new ones | Group leakage — same customers in train and test. |

---

## Prompt templates

### Pre-modeling leakage audit
```
Before any modeling, run a leakage audit:

1. List every feature. For each, state whether it would be available
   at prediction time in production. Flag any that would NOT.
   Explain why.

2. Check: any feature with correlation > 0.95 with the target?
   These are likely leaking the answer.

3. This is a [time-series / grouped / independent] dataset.
   What is the correct split strategy? Justify it.
   Do NOT use random split unless you can justify it explicitly.

4. Show the data sorted by [date / entity_id] so I can visually
   verify the split boundary makes sense.
```

### Temporal split enforcement
```
This dataset has a time dimension (column: [date_column]).

Rules for this project:
1. NEVER use random train-test split.
2. Split time-based: train on [start] to [date], test on [date] to [end].
   Test period must always come AFTER training period.
3. For cross-validation use TimeSeriesSplit — never KFold.
4. Show a plot of train vs test split by date.
   Verify there is no temporal overlap.
5. After training, show performance broken down by month in the test set.
   Consistent = no leakage. Degrades over time = distribution shift.
```

### Group-based split enforcement
```
This dataset has grouped structure: multiple rows per [customer / patient / city].

Rules:
1. The SAME [entity] must NEVER appear in both training and test data.
2. Use GroupShuffleSplit or GroupKFold for splitting.
3. The group column is: [column name].
4. After splitting, verify: print the set intersection of group IDs
   in train vs test. It must be empty.
5. Report performance separately on:
   - Groups seen during training (memorization check)
   - Groups NOT seen during training (generalization check)
   These should be similar. Large gap = memorizing, not learning.
```

### Catching preprocessing leakage
```
For all preprocessing, enforce this order:
1. Split data FIRST (before any fit_transform)
2. All scalers, imputers, encoders:
   - fit() on training data ONLY
   - transform() applied separately to train and test
3. Build a sklearn Pipeline object that enforces this automatically.
4. Show the pipeline steps explicitly so I can verify no step
   uses test data during fitting.
```

---

## Anti-patterns

- Never use `fit_transform` on the full dataset before splitting
- Never use random split on time-series data
- Never use random split when the same entity must stay in one set
- Never celebrate high accuracy without asking if leakage could explain it
- Never compute aggregates (mean, std, target encodings) on the full dataset before splitting
- Never look at the test set during feature selection or model selection
- Never include a feature that is derived from or directly related to the target

---

## The principle

Data leakage does not make your model fail loudly. It makes your model succeed deceptively.

A leaky model looks exactly like a great model — during development. The failure comes in production, when the information that made the model "accurate" simply doesn't exist anymore.

The agent will never tell you that your 98% accuracy is fake. Only you can catch this by asking — for every single feature — "Would I actually have this value at the moment of prediction?"

If the answer is no for even one important feature, your model is predicting the past, not the future.
