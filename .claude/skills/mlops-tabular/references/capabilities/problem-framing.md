# Problem Framing: From Business Question to ML Formulation

Translating a business problem into an ML problem is the highest-leverage decision in any ML project. A well-framed problem makes everything downstream -- data collection, metric selection, model choice, deployment -- fall into place. A poorly framed problem wastes months of engineering on a system nobody needs or one that optimizes the wrong thing. Your power as an ML practitioner is saying no with reasons, not saying yes to everything.

## The Six-Word Test for ML Readiness

Before writing any code, apply this filter. ML is appropriate when all six conditions hold:

1. **Learn**: The system must improve from examples, not from hand-written rules.
2. **Complex**: The relationships between inputs and outputs are not obvious or easily codified.
3. **Patterns**: Non-random structure exists in the data. If the signal is pure noise, no model can help.
4. **Existing data**: Signals and labels are accessible. If you have no historical examples, you cannot train a supervised model.
5. **Predictions**: Estimates are needed at decision time. If the answer is already known or not needed in advance, ML adds no value.
6. **Unseen data**: Training and serving share the same world. If the production distribution will be fundamentally different from training data, the model will fail silently.

If any of these six words does not apply, stop and reconsider. A rules-based system, a heuristic, or even a manual process may be the right answer. Not every problem needs ML, and recognizing that early saves enormous cost.

## Decision Framework: ML vs Heuristic vs Not Now

Three paths exist for every problem:

- **ML solution**: Use when patterns are genuinely complex, labeled data exists, and the prediction has clear business value. Examples: fraud scoring with hundreds of behavioral features, demand forecasting across thousands of SKUs with seasonal patterns.
- **Heuristic or rules-based system**: Use when the logic is expressible in a handful of rules, the domain expert can articulate the decision process, or data is too scarce for ML. A heuristic that ships today beats a model that ships in three months. Many fraud detection systems start with rules and add ML later.
- **Not now**: Use when labels do not exist yet, the data infrastructure is not ready, or the business metric is unclear. Building ML on a shaky data foundation is a common failure mode. Invest in data collection and labeling pipelines first.

Evaluate each option on three axes: value gain (how much the business metric improves), operational fit (can the team maintain it), and risk profile (what happens when the system is wrong).

## The Problem Statement Template

Every ML problem should be expressible in one sentence:

> "Given **[input X]**, predict **[target Y]**, for **[user/system Z]**, at **[decision time T]**, to optimize **[business outcome B]**."

If you cannot fill in all five blanks, the problem is not well-defined yet. Each blank forces clarity:
- **Input X**: what data is available at prediction time (not what exists in your warehouse -- what is available at the moment of decision)
- **Target Y**: the specific quantity or category being predicted
- **User/System Z**: who or what consumes the prediction and takes action on it
- **Decision Time T**: when the prediction is needed relative to the action
- **Business Outcome B**: the measurable business metric that improves if the model works

Example: "Given a loan application's financial features, predict whether the applicant will default within 12 months, for the automated underwriting system, at application submission time, to reduce default losses while maintaining approval volume."

## The Metric Ladder

Design a metric ladder from business to model. Each level must connect to the one above:

1. **Business outcome** (north star) -- revenue, retention, cost saved, safety. This is what the stakeholder actually cares about.
2. **Product success metric** -- click-through rate, resolution time, conversion, approval rate. Directly measurable in the product.
3. **Model evaluation metric** -- precision, recall, AUC, RMSE. What you optimize offline.
4. **Data quality metric** -- schema validity, null rates, distribution stability, feature freshness. The foundation everything else rests on.

Pick one primary success metric, two or three guardrail metrics, and hard constraints that must never be violated. The metric ladder ensures that improving a model metric actually moves the business needle.

## Problem Type Selection

For tabular data, most problems fall into three categories:

### Binary Classification

The target has two possible values: yes/no, fraud/legitimate, churn/retain, approved/denied. This is the most common ML problem type in enterprise settings.

Choose binary classification when: the business decision is a threshold decision (approve or reject, flag or pass), there is a natural binary outcome in historical data, and the cost of errors differs by direction (false positive vs false negative).

### Multiclass Classification

The target has more than two discrete categories: product category, risk tier (low/medium/high/critical), diagnosis type. Each observation belongs to exactly one class.

Choose multiclass classification when: outcomes are categorical with more than two values, classes are mutually exclusive, and the set of possible classes is known and stable. If the class set changes frequently or new classes appear without training examples, consider a different approach (e.g., embedding-based similarity).

### Regression

The target is a continuous numeric value: price, demand quantity, time-to-event, revenue forecast.

Choose regression when: the outcome is naturally continuous, the business cares about magnitude (not just direction), and the error metric relates to numeric distance. Be cautious about treating ordinal data (ratings 1-5) as regression -- it can work but violates continuity assumptions.

## Business Metric to ML Metric Mapping

The most critical framing decision is choosing the right primary metric. The ML metric must connect to the business metric the stakeholder actually cares about.

### For Classification

- **When false positives are expensive** (e.g., unnecessary medical procedures, customer friction from false fraud alerts): Optimize for precision. The business cost is wasted resources or damaged trust per false alarm.
- **When false negatives are expensive** (e.g., missed fraud, undetected disease, overlooked safety hazard): Optimize for recall. The business cost is the harm from missing a true positive.
- **When both matter but you must pick one**: Use F1 score (harmonic mean of precision and recall) as a starting point, then adjust the threshold based on the cost ratio.
- **When you need calibrated probabilities** (e.g., scores feed downstream risk tiers, pricing, or ranking): Optimize for log loss or Brier score. Accuracy at a fixed threshold is irrelevant if the scores themselves must be meaningful.
- **When classes are highly imbalanced**: Use precision-recall AUC rather than ROC AUC. ROC AUC can look excellent even when the model is useless on the minority class.

### For Regression

- **When over-prediction is costly** (e.g., over-ordering inventory leads to waste): Use asymmetric loss or evaluate on the magnitude of positive errors separately.
- **When under-prediction is costly** (e.g., under-staffing leads to lost revenue): Evaluate negative errors separately. Consider quantile regression targeting a high percentile.
- **When typical error matters most**: Use MAE (mean absolute error) for a robust median-like estimate.
- **When large errors are disproportionately harmful**: Use RMSE, which penalizes large deviations more heavily.
- **When percentage error matters** (e.g., forecasting across items of vastly different scale): Use MAPE or weighted MAPE.

### The Forcing Questions

Before committing to a metric, answer these questions explicitly:

1. **Who uses the predictions?** A human reviewing a dashboard has different needs than an automated system making instant decisions. Human consumers need calibrated scores; automated systems need optimized thresholds.
2. **What is the cost of each error type?** Quantify the asymmetry. If a false negative costs 100x a false positive, the metric and threshold must reflect that ratio.
3. **What data exists today?** Audit the available features and labels. Stale labels, proxy labels, and selection bias in the training data all distort metrics.
4. **What is the current baseline?** Before ML, how is this decision made today? A model must beat the current process (even if the current process is a human with a spreadsheet) to justify its operational complexity.
5. **Is the world stable enough for a static model?** If the relationship between features and target shifts frequently (concept drift), the project needs a retraining and monitoring plan from day one, not just a model.
6. **Can you observe ground truth?** If labels arrive weeks or months after prediction time, monitoring becomes much harder. Plan for proxy metrics and delayed evaluation.

## Observing Before Building

The strongest ML practitioners observe the problem and its constraints before jumping to solutions. This means:

- Talking to domain experts and end users of the predictions to understand the workflow the model will live inside.
- Examining sample predictions manually. Can a human make this prediction from the available features? If a domain expert cannot, the model likely cannot either.
- Mapping the full pipeline: where does data come from, what transformations happen before the model sees it, how do predictions reach the end user, and what happens when a prediction is wrong.
- Building the smallest thing that can work first. A logistic regression or decision tree baseline trained in an afternoon often reveals 80% of the signal. If the baseline is good enough, ship it and iterate.

## When to Use This

- At the start of any new ML project, before writing any training code. Frame the problem first.
- When a stakeholder requests "an AI solution" without specifying what they want predicted or why. Use the forcing questions to extract specifics.
- When an existing model is underperforming and the team suspects the metric is misaligned with business goals.
- When deciding whether to invest in ML infrastructure for a new use case vs. shipping a heuristic.
- When reviewing a project proposal to assess feasibility and expected ROI.

## Red Flags to Watch For

- **No clear business metric**: If the stakeholder cannot articulate what success looks like in business terms (revenue, cost savings, error reduction), the project has no anchor. Stop and define success before building.
- **Labels do not exist**: Supervised ML requires labeled data. If there is no historical outcome data and no plan to generate labels, ML is premature.
- **"We need AI" without a problem statement**: This is a technology-first approach. Redirect to the business problem first.
- **Cost of errors is unexplored**: If nobody has discussed what happens when the model is wrong, the deployment will surprise everyone. Especially dangerous in domains like healthcare, finance, and safety.
- **Accuracy as the only metric**: For imbalanced problems, accuracy is meaningless. A model that predicts the majority class every time achieves high accuracy while being useless.
- **No baseline comparison**: If the team cannot state how the problem is solved today and what performance the current approach achieves, there is no way to measure whether ML adds value.
- **Training data is not representative of production**: If the data used to train the model comes from a different time period, population, or process than what the model will see in production, performance estimates are unreliable.
- **Stakeholder expects perfection**: ML is probabilistic. If the use case cannot tolerate any errors, ML may not be appropriate. Clarify error tolerance early.
- **The world changes faster than you can retrain**: If concept drift is rapid and continuous (e.g., adversarial fraud patterns, viral social trends), a static model degrades quickly. Plan for monitoring and retraining cadence from the start.
