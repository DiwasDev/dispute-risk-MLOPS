# Problem Statement: Consumer Complaint Dispute Risk Prediction

## One-Sentence Formulation
Given complaint intake data (product, issue, company, submission channel, and other fields known at the moment of submission), predict whether a consumer will dispute the eventual resolution, for the complaint routing system, at complaint intake time (before any resolution work begins), to optimize early identification of high-risk complaints for senior-agent review.

## Business Context
Financial institutions receive thousands of consumer complaints every month, but manually performing an in-depth review for every complaint is neither practical nor cost-effective. Routing high-risk complaints to senior-agent review — instead of manually reviewing every single complaint — targets the cost imbalance directly: catching a likely dispute early is far more valuable than the extra time a senior review costs. Manual review of 100% of complaints isn't realistic or worth the labor cost, so most complaints should stay on the standard workflow, keeping senior-agent hours or in-depth review focused only where they're likely to matter. Left uncaught, disputes escalate: the customer disagrees with the resolution, may become upset or challenge it further, and in the real-world CFPB process this can mean formal escalation — reputational and operational costs that are much higher than the cost of a routine review.

**Cost of errors**: A false positive means a complaint gets an unnecessary manual/senior review — extra labor cost, but the customer still gets served correctly. A false negative means a complaint that would have been disputed gets no extra attention — the customer becomes angry, disputes the resolution, and may churn. Because a lost or upset customer costs far more than an extra review, false negatives are treated as worse than false positives, which is why recall is weighted above precision in the metric choice below.

## ML Formulation
- **Problem type**: Binary classification
- **Target variable**: `Consumer disputed?` (Yes/No) — ~21% positive rate (76,172 disputed / 358,810 total)
- **Primary metric**: PR-AUC — imbalanced target, threshold-independent comparison across models
- **Guardrail metrics**: Recall at a fixed precision / top-K% flagged (matches assumed senior-queue capacity); F2-score (weights recall over precision, matching the stated cost asymmetry)
- **Current baseline**: None known yet — first EDA task is to check whether dispute rate varies meaningfully by `Product` or `Company` (possible simple-rule baseline). Absent that, the first trained model (e.g. logistic regression) is the baseline.

## Metric Ladder
- **Business outcome**: Fewer disputes reaching CFPB/escalation; better use of senior-agent time (simulated, not measured against a real business)
- **Product metric**: % of eventual disputes caught in the high-risk queue at a given queue capacity
- **Model metric**: PR-AUC (comparison), Recall@precision / F2 (operating threshold)
- **Data quality metric**: null rates (especially `Consumer complaint narrative`, which is ~84% null in places, and tag ~86% null), schema validity, category drift over time

## Data Summary
- **Rows**: ~358,810 labeled complaints (Dec 2011 – Sep 2016)
- **Features (intake-time only)**: `Product`, `Sub-product`, `Issue`, `Sub-issue`, `Consumer complaint narrative`, `Company`, `State`, `ZIP code`, `Tags`, `Consumer consent provided?`, `Submitted via`, `Date received`
- **Excluded (leakage)**: `Company public response`, `Company response to consumer`, `Timely response?`, `Date sent to company`
- **Known issues**: ~21% class imbalance; heavy nulls in narrative text; high-cardinality `Company` field; queue-capacity constraint is assumed, not real

## Constraints
- **Latency**: Real-time — complaint submitted → FastAPI endpoint scores it immediately at intake, target under ~1 second per prediction, so the routing decision (standard vs. senior queue) can happen before any agent picks up the complaint
- **Interpretability**: Not a hard requirement, but useful for the portfolio narrative (why a complaint was flagged) — SHAP or similar, deferred to later phase
- **Regulatory**: None real (simulated scenario only); narrative may reference CFPB context for realism

## Framework
- **Orchestration**: ZenML + MLflow + FastAPI + Azure Container Apps

## Success Criteria
Problem framing is done when: time-based holdout split is implemented on `Date received`; leakage-free feature set is finalized; PR-AUC baseline is established; and an EDA pass confirms/rejects a simple Product/Company-based rule as a naive baseline to beat.