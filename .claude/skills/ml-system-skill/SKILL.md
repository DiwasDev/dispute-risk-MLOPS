# ML System Skill

## Settings
```
PIPELINE_STAGE = 1           # Which stage are you entering right now?
                             # 1: Problem definition
                             # 2: Data exploration (EDA)
                             # 3: Data cleaning & preprocessing
                             # 4: Feature engineering
                             # 5: Model training & selection
                             # 6: Evaluation & diagnostics
                             # 7: Interpretation & communication

TEAM_SIZE = 3                # Solo or team?
                             # 1-3: Solo — minimal documentation
                             # 4-7: Small team — document decisions and assumptions
                             # 8-10: Large team — every stage needs handoff documentation

PRODUCTION_GRADE = 5         # Final destination?
                             # 1-3: Notebook / research
                             # 4-7: Internal tool or dashboard
                             # 8-10: Customer-facing, monitored, SLA-bound
```

---

## What this prevents

Most ML projects don't die from picking the wrong algorithm. They die from skipping a step, or from a non-obvious gotcha inside a step that nobody warned them about.

The pipeline is universal. The gotchas are where projects fail.

This skill treats each stage as a gate — you must pass it before moving on. It encodes the failure modes that don't appear in textbooks.

---

## The 7-stage pipeline

```
Stage 1: Problem Definition
         ↓  [gate check]
Stage 2: Data Exploration (EDA)
         ↓  [gate check]
Stage 3: Data Cleaning & Preprocessing
         ↓  [gate check]
Stage 4: Feature Engineering
         ↓  [gate check]
Stage 5: Model Training & Selection
         ↓  [gate check]
Stage 6: Evaluation & Diagnostics
         ↓  [gate check]
Stage 7: Interpretation & Communication
```

Never skip a stage. Never go back to Stage 1 after Stage 5 without documenting why.

---

## Stage 1: Problem Definition

**Goal:** Agree on exactly what you're building and what success means — before touching data.

**Gotcha:** Vague problem definition. You finish Stage 6, present results, and the stakeholder says "but that's not what I meant." Two weeks wasted.

**What to establish:**
- What decision will be made from this prediction? (→ see `problem-framing-skill`)
- What is the target variable, exactly? How is it defined? Edge cases?
- What features will be available at prediction time in production? (→ see `data-integrity-skill`)
- What does success look like in business terms? (→ see `evaluation-skill`)
- Is ML even the right tool? Would a simple IF-ELSE rule cover 80% of cases?

**Gate check before Stage 2:**
- [ ] Target variable defined precisely, including edge cases
- [ ] Business success metric agreed upon
- [ ] Features available at prediction time confirmed
- [ ] Decision on ML vs rule-based approach made and documented

---

## Stage 2: Data Exploration (EDA)

**Goal:** Understand the data deeply before modeling. No surprises in Stage 5.

**What the agent does by default:** Prints `.describe()` and `df.head()`. Declares EDA complete.

**What to actually do:**
1. Distribution of the target variable — normal, skewed, bimodal?
2. Distribution of every feature — flag anything suspicious
3. Missing values: how much is missing, and *why* is it missing?
4. Correlations with the target
5. Outliers: data errors or real edge cases?
6. If temporal: plot the target over time — trends, seasonality, anomalies?

**Gotcha 1:** Looking at averages instead of distributions. Means hide bimodality, outliers, and skew. Always plot histograms.

**Gotcha 2:** Ignoring the reason for missingness. "Missing" is sometimes informative. A blank income field on a credit application might mean the applicant chose not to disclose — which correlates with risk. Don't blindly impute.

**Gotcha 3:** Not checking for duplicates. Duplicated rows give some patterns disproportionate weight in training.

**Gate check before Stage 3:**
- [ ] Target distribution understood and documented
- [ ] Missing value strategy decided (not just "fill with mean")
- [ ] Outliers investigated — data errors identified
- [ ] No duplicates, or duplicates understood and handled

---

## Stage 3: Data Cleaning & Preprocessing

**Goal:** Get data into a form the model can learn from, without introducing leakage.

**What the agent does by default:** `df.fillna(df.mean())` on everything. Scales all features. Moves on.

**The cardinal rule:** Split data FIRST. All preprocessing must be fitted on training data only.

**Missing value strategies:**

| Reason missing | Strategy |
|---|---|
| Random missingness (sensor glitch, form skip) | Impute with median/mean |
| Missingness is informative | Create `is_missing` binary flag, then impute |
| Missing because event didn't happen | Fill with 0 or domain-appropriate default |
| Missing because data wasn't collected yet | Do not impute — may be temporal leakage |

**Gotcha 1:** Fitting scalers/imputers before splitting. Always: split first, then fit.

**Gotcha 2:** One-hot encoding a high-cardinality feature (500 cities → 500 sparse columns). Use frequency encoding or target encoding (after split, carefully).

**Gotcha 3:** Scaling tree models. Random Forest and XGBoost do not need feature scaling. Only linear models, SVMs, KNNs, and neural networks do.

**Gate check before Stage 4:**
- [ ] Train-test split completed BEFORE any fit_transform
- [ ] Missing value strategy documented, not just filled
- [ ] Categorical encoding appropriate for cardinality and model type
- [ ] Scaling applied only where needed

---

## Stage 4: Feature Engineering

**Goal:** Create domain-informed features. Give the model a head start. (→ see `feature-engineering-skill`)

**Gotcha:** Generating mechanical features (polynomial, all pairwise interactions) without domain justification. Adds noise and overfitting risk.

**Gate check before Stage 5:**
- [ ] Domain features created first, before mechanical ones
- [ ] Time-based features computed without future leakage
- [ ] Feature count is reasonable (not 500 features for 1K rows)
- [ ] All features confirmed available at prediction time

---

## Stage 5: Model Training & Selection

**Goal:** Find the model that generalizes best — not the one with the best training performance.

**The complexity ladder (start here, climb only with justification):**
```
Mean predictor (beat this or don't ship)
        ↓
Simple rule / business heuristic
        ↓
Linear Regression / Logistic Regression
        ↓
Ridge / Lasso / Elastic Net
        ↓
Decision Tree
        ↓
Random Forest / XGBoost / LightGBM
        ↓
Neural Network (only with large data + non-linear patterns)
```

**Gotcha 1:** Hyperparameter tuning on the test set. Every time you check test performance and adjust, the test set leaks into your model. Use a validation set or nested cross-validation for tuning.

**Gotcha 2:** Comparing models trained on different data. All models must be trained on identical folds for a fair comparison.

**Gotcha 3:** "More complex = better." A Random Forest that barely beats Linear Regression often isn't worth the interpretability cost in a real deployment.

**Gate check before Stage 6:**
- [ ] Baseline model results recorded
- [ ] Multiple candidates compared on held-out data
- [ ] Hyperparameters tuned using validation set (NOT test set)
- [ ] Selected model justified vs simpler alternatives

---

## Stage 6: Evaluation & Diagnostics

**Goal:** Verify the model works in ways that matter — technically and for the business.
(→ see `evaluation-skill` for business metrics, `generalization-skill` for diagnostics)

**Gotcha:** Reporting only RMSE. Skipping assumption checks. Skipping segment analysis.

**Gate check before Stage 7:**
- [ ] Technical metrics: RMSE, MAE, R²
- [ ] Business metrics: cost impact, % within tolerance, vs baseline
- [ ] Diagnostic suite: residuals, Q-Q, VIF, Cook's distance
- [ ] Segment performance: equally good across all subgroups?
- [ ] Leakage double-check: any suspiciously high performance?

---

## Stage 7: Interpretation & Communication

**Goal:** Turn model results into decisions and actions.

**What the agent does by default:** Prints feature importances. Declares the project complete.

**What to actually do:**
1. Answer: which features matter most — in domain language, not "feature 7"
2. Answer: what should the business actually DO differently based on this model?
3. Identify: where the model should NOT be used (segments, edge cases, data quality conditions)
4. Define: a monitoring plan — how will you know when the model is becoming stale?
5. Document: known limitations, honestly

**Gotcha 1:** "Highest coefficient = most important feature." Only true if all features are on the same scale. Standardize before comparing coefficients.

**Gotcha 2:** Confusing correlation with causation. The model found a pattern. It didn't prove one thing causes another.

**Gotcha 3:** No monitoring plan. Models become stale as data changes. Without monitoring, you won't know until something breaks in production.

---

## The master prompt sequence

### Prompt 1 — Stage 1 gate
```
Before we write any code:

1. Business goal: [...]
2. Target variable: [confirm what we're actually predicting, including edge cases]
3. Features available at prediction time: [list — exclude anything that wouldn't
   exist when the prediction is needed in production]
4. Business success means: [not RMSE — what the stakeholder cares about]
5. Simplest non-ML baseline: [mean predictor / rule / existing process]

Do not proceed to data loading until I confirm this framing.
```

### Prompt 2 — Stage 2 EDA
```
Load the data. Thorough EDA only — no modeling yet:

1. Distribution of the target (histogram + summary stats).
   Skewed? Bimodal? Flag if yes — may need log transform.
2. For each feature: missing % and distribution.
   Flag anything > 20% missing.
3. Top 10 features by correlation with target.
4. Duplicate row count.
5. If temporal: plot target over time. Flag anomalies or trend changes.

Do NOT proceed to modeling. I want to review EDA findings first.
```

### Prompt 3 — Stages 3–4 Preprocessing + Features
```
Split data FIRST before any preprocessing.
[Describe the correct split: random / temporal / group-based]

Then:
1. Fit all scalers, imputers, encoders on training data only
2. Apply to test data separately
3. Create these domain features: [list from feature-engineering-skill]
4. Build a sklearn Pipeline that enforces this order automatically
5. Show the pipeline's steps before training — I want to verify
   no step leaks test data into training
```

### Prompt 4 — Stage 5 Training
```
Train these models and compare using [5-fold CV / TimeSeriesSplit]:
1. Mean predictor (absolute baseline)
2. Linear Regression
3. Ridge (tune alpha: 0.01, 0.1, 1, 10, 100)
4. [Additional model if data size warrants]

Report for each: CV mean ± std, and test set score.
Selected model must beat the mean predictor by a meaningful margin
or we do not proceed to evaluation.
```

### Prompt 5 — Stage 6 Evaluation
```
Full evaluation for the selected model:

Technical: RMSE, MAE, R-squared on test set

Business:
1. % of predictions within ±[X]% of actual
2. Estimated cost of errors: [cost structure]
3. Comparison vs baseline [current process]

Diagnostics: residuals vs predicted, Q-Q, VIF, Cook's distance

Segment analysis: RMSE broken down by [key segment column]

Produce a 1-page summary table for a non-technical stakeholder.
```

### Prompt 6 — Stage 7 Interpretation
```
Final interpretation:

1. Top 5 most important features — in plain English, what do they mean
   for the business?
2. What should the business DO differently based on this model?
   (Concrete recommendations, not just "the model predicts X")
3. Where should we NOT use this model?
   (Which segments, conditions, or data quality scenarios)
4. Monitoring plan: what metric to track weekly to catch staleness?
   At what threshold should we retrain?
5. Known limitations: what does this model NOT account for?
```

---

## The gotcha summary

| Stage | Common gotcha | How to avoid |
|---|---|---|
| Problem definition | "We need ML" when rules work | Can IF-ELSE get 80%? |
| EDA | Looking at averages | Always plot distributions |
| Cleaning | Fitting scalers on full dataset | Split first, then fit |
| Features | Only mechanical transforms | Domain research > polynomial features |
| Training | Random split on time-series | Match split to production use |
| Evaluation | Only RMSE | Always include business metric + baseline |
| Interpretation | "Highest coefficient = most important" | Standardize features first |

---

## Anti-patterns

- Never load data before Stage 1 framing is confirmed
- Never skip the baseline — if you can't beat the mean, nothing else matters
- Never tune hyperparameters on the test set
- Never move to a more complex model without documenting why simpler wasn't sufficient
- Never present results without a segment breakdown
- Never ship a model without defining how you'll know when it goes stale
- Never skip Stage 7 because "the numbers are good" — translation into action is the entire point

---

## The principle

The pipeline is the same for every supervised learning problem. What separates a toy notebook from a production system is not the algorithm — it is the rigor applied at every gate.

An agent can execute any single stage. What it cannot do is manage the pipeline — deciding when to proceed, when to go back, and what the non-obvious failure modes are at each step.

That strategic judgment is yours. The agent brings the code. You bring the architecture.
