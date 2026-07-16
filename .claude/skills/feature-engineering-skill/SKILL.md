# Feature Engineering Skill

## Settings
```
DOMAIN_EXPERTISE = 5         # How much domain knowledge can you access?
                             # 1-3: No domain expert — raw data only
                             # 4-7: Some domain knowledge — can research
                             # 8-10: Deep domain access — expert available or you are one

DATA_SIZE = 5                # Training data volume
                             # 1-3: <5K rows — features are the only lever, complexity won't help
                             # 4-7: 5K–500K rows — features + moderate complexity
                             # 8-10: >500K rows — model complexity can compensate for missing features

EXPLAINABILITY = 5           # Do features need to be explainable?
                             # 1-3: Black box fine — internal, no audits
                             # 4-7: Moderate — stakeholders want intuition
                             # 8-10: Full audit trail — regulated industry
```

---

## What this prevents

When a model underperforms, most people add model complexity. More layers, more trees, bigger network.

This is almost always wrong — especially with limited data.

The right move: better features. A simple linear regression with well-engineered features routinely outperforms a complex neural network with raw, messy features. Features encode knowledge that a model would need millions of rows to discover on its own.

The AI can add polynomial features mechanically. It cannot know that "distance to metro station" explains 40% of apartment prices in Mumbai. That comes from you.

---

## Core rule: domain features before model complexity

Ask these before any feature engineering:

**Q1. What do domain experts use to make this prediction manually?**
A doctor diagnoses using specific biomarker combinations. A real estate agent uses price-per-sqft and neighborhood tier. Encode what they know.

**Q2. What transformations make relationships more linear?**
Linear models need linear relationships. If income vs spending is curved, `log(income)` may straighten it.

**Q3. What interactions matter — where two features together tell a different story?**
- `area × floor_number`: penthouses command disproportionate premiums
- `rainfall × temperature`: hot+wet is completely different from hot+dry

**Q4. What time patterns hide in the data?**
Trends, seasonality, lags (last month predicts this month), rolling averages.

**Q5. What ratios give context that raw numbers don't?**
- `revenue_per_employee` beats raw revenue and headcount separately
- `price_per_sqft` beats raw price and area separately

---

## Feature transformation reference

| Raw feature | Problem | Transformation | Why |
|---|---|---|---|
| Income: Rs 20K to Rs 50M | Huge range | `log(income)` | Compresses range, linearizes |
| Date: "2024-03-15" | Model can't read dates | month, day_of_week, is_weekend, quarter | Reveals seasonal + cyclic patterns |
| Address: "Mumbai, Andheri" | Text | Lat/long, dist to landmark, area income | Numeric + spatially meaningful |
| Price: Rs 100 to Rs 10L | Right-skewed | `log(price)` | Normalizes, prevents dominance |
| Height + Weight | Correlated, redundant | BMI = weight/height² | Domain-informed combination |
| "Sold 50 units Monday" | No context | ratio vs city avg, ratio vs dow avg | Relative beats absolute |

---

## Domain feature frameworks by industry

Use these before inventing features from scratch — they encode decades of practitioner knowledge.

### E-commerce / Retail: RFM
- **Recency** — days since last purchase (lower = more engaged)
- **Frequency** — number of purchases in window (higher = more loyal)
- **Monetary** — total spend in window (higher = more valuable)

### Real Estate (India)
- Price per square foot
- Distance to nearest metro/transport hub
- Distance to nearest rated school
- Age bucket: pre-1990 / 1990–2010 / post-2010 (structural quality differs)
- Floor number relative to building height
- Facing direction (Vastu-relevant in Indian market)

### Healthcare / Clinical
- Charlson Comorbidity Index (weighted sum of conditions)
- Drug-drug interaction flags
- Days since last hospitalization
- Lab value trends (direction matters, not just absolute value)

### Finance / Banking
- Debt-to-income ratio
- Credit utilization rate
- Payment history streak (consecutive on-time payments)
- Moving averages: 20-day, 50-day, 200-day
- Month-end vs mid-month transaction patterns

### Marketing / Growth
- Customer lifetime value estimate
- Funnel stage (awareness / consideration / intent / purchase)
- Days since acquisition
- NPS bucket (promoter / passive / detractor)

---

## The features vs complexity decision

| Situation | Right lever | Wrong lever |
|---|---|---|
| <5K rows, poor accuracy | Better features | More complex model — not enough data to learn |
| Regulated industry | Features + simple model | Complex black box — not auditable |
| One segment performs badly | Domain features for that segment | More epochs |
| Model overfits | Regularization + feature selection | More features — will worsen it |
| >500K rows, complex patterns | Model complexity | Feature engineering — you have the data |
| Inference must be <1ms | Simple model + smart features | Neural network — too slow |

---

## Prompt templates

### Domain feature extraction
```
Before any mechanical features (polynomials, interactions),
here is the domain knowledge that matters for this problem:

Domain: [e.g., Indian real estate, e-commerce churn]

Features to create:
1. [Name]: [formula or description]
   Why: [business logic — what does this capture?]
2. [Name]: [...]
   Why: [...]

Features NOT to add polynomial terms to:
- [feature]: relationship is already linear
- [feature]: already a ratio, polynomials would be noise

After creating these, run a simple linear regression and report R².
Then we'll decide if more complexity is warranted.
```

### Feature importance audit
```
After training, run a feature importance analysis:

1. Tree models: show feature importances (bar chart + table)
2. Linear models: show coefficients AFTER standardizing features
   (raw coefficients are not comparable across different scales)
3. Show SHAP values if explainability is needed

Then:
- Flag the top 5 most important features: are these what domain
  knowledge would predict? A surprising #1 may be leaky or confounded.
- Flag features with near-zero importance: removal candidates
  (simpler model, faster inference, less overfitting)
- Flag highly correlated feature pairs: one is probably redundant
```

### Temporal feature engineering
```
This dataset has a time dimension. Create these features:

1. Lag features:
   - [target]_lag_1: value from previous period
   - [target]_lag_7: value from 7 periods ago
   - [target]_lag_30: value from 30 periods ago

2. Rolling window features (compute on TRAINING DATA ONLY):
   - rolling_mean_7: 7-period rolling average
   - rolling_std_7: 7-period rolling standard deviation
   - rolling_max_30: 30-period rolling maximum

3. Calendar features:
   - day_of_week, month, quarter, is_weekend, is_holiday
   - days_since_last_event (if discrete events exist)

IMPORTANT: All rolling and lag features must be computed without
looking at the test period. Historical windows only.
```

### Feature selection — cut the noise
```
We have [N] features. Before adding complexity, cut the noise:

1. Remove features with > [X]% missing values
2. Remove near-zero variance features (std < 0.01)
3. Remove features with correlation > 0.95 with another feature
   (keep the one more correlated with the target)
4. Run recursive feature elimination (RFE) with cross-validation
   to find the optimal feature count
5. Compare: all features vs top-K features on train and test RMSE

Goal: simplest model that doesn't sacrifice meaningful accuracy.
Fewer features = faster, more interpretable, less overfitting risk.
```

---

## Anti-patterns

- Never add polynomial features for every column without domain reasoning
- Never keep all features because "more data is better"
- Never fit scalers or encoders on the full dataset before splitting
- Never use raw dates or text as features without transformation
- Never add complexity to the model before exhausting domain feature ideas
- Never trust a surprising #1 feature without investigating if it's leaky
- Never add an interaction term without a business reason for why they interact

---

## The principle

The algorithm you choose matters far less than the features you give it.

Features encode knowledge. Model complexity tries to discover knowledge from data. If you already know what matters — from research, from experts, from domain literature — encode it directly as a feature. The model then has a head start.

A senior data scientist's edge is not knowing more algorithms. It is knowing which features to create before the model sees the data.
