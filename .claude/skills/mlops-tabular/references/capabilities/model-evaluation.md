# Model Evaluation: Online vs Offline

Model evaluation splits into two fundamentally different regimes: offline evaluation (before users see the model) and online evaluation (while users interact with it). Both are necessary. Offline evaluation filters out bad candidates cheaply. Online evaluation confirms real-world impact. Skipping either creates blind spots.

## Offline Evaluation

Offline evaluation uses historical or held-out data to estimate how a model will perform. It is fast, cheap, and repeatable, but it cannot capture live user behavior, system latency, or feedback loops.

### Core Techniques

- **Train/validation/test split**: The minimum. Hold out data the model never trains on. Test set is touched once, at the end, to get an unbiased estimate.
- **Cross-validation**: K-fold cross-validation averages performance across multiple splits, reducing variance in the estimate. Use 5 or 10 folds for tabular data. Stratified folds preserve class ratios for imbalanced problems.
- **Temporal splits**: For time-series or sequential data, always split by time. Future data must never leak into training. Use a cutoff date: train on everything before, validate on the window after, test on the window after that.
- **Slice-level evaluation**: Global metrics hide segment failures. Always break metrics down by important business slices (region, device, user cohort, time-of-day). A model with 95% overall accuracy that fails on a critical minority segment is not production-ready.

### Metrics by Problem Type

**Classification:**
- Precision, recall, F1 for each class. Never rely on accuracy alone for imbalanced problems.
- PR curve (precision-recall) is more informative than ROC for rare events.
- Log loss measures calibration quality -- important when scores drive downstream thresholds.
- Confusion matrix by slice reveals where the model systematically errs.

**Regression:**
- MAE (mean absolute error) for typical miss magnitude.
- RMSE when large errors are disproportionately costly.
- MAPE for percentage-based business interpretation.
- Quantile errors (p50, p90, p99 of absolute error) reveal tail behavior that averages hide.

**Ranking:**
- NDCG at K for user-visible top positions.
- MAP (mean average precision) for recall-oriented ranking.
- Always evaluate at the K that matches product display (top 5, top 10).

### Confidence Intervals and Statistical Rigor

**A single number without uncertainty is not evidence.** Always compute confidence intervals around offline metrics.

**Bootstrap procedure:**
1. Take the test set predictions and true labels.
2. Resample with replacement to create a bootstrap sample of the same size.
3. Compute the metric (precision, recall, AUC, etc.) on the bootstrap sample.
4. Repeat 1000+ times to build a distribution of the metric.
5. Report the 2.5th and 97.5th percentiles as the 95% confidence interval.

Example: "Precision = 0.82 (95% CI: 0.78-0.86)" is evidence. "Precision = 0.82" is a guess.

- For comparing two models, compute the distribution of metric differences across bootstrap samples. If the 95% interval includes zero, you cannot claim one model is better.
- Larger test sets yield tighter intervals. If the interval is too wide for a decision, get more evaluation data before proceeding.

### Slice-Level Evaluation

Global metrics hide segment failures. A model with 95% overall accuracy that fails on a critical minority segment is not production-ready.

**Always break metrics down by important business slices:**
- Geographic segments (region, country, city)
- Demographic segments (age group, income bracket)
- Product segments (product type, price tier)
- Temporal segments (weekday vs weekend, time of day, season)
- Data quality segments (complete vs imputed data)

A model should meet minimum performance thresholds on every critical slice, not just overall. If the model excels for urban high-income applicants but fails for rural low-income applicants, it is not ready for production -- even if the overall metrics look good.

## Online Evaluation

Online evaluation measures model impact on real users in production. It answers the question offline metrics cannot: does this model actually improve the product?

### A/B Testing

The gold standard for causal impact measurement. Split live traffic between control (current model) and treatment (new model), measure business outcomes.

**Design requirements:**
- Clean randomization unit (usually user-level, not request-level) to avoid contamination.
- Pre-defined primary metric (the north star: revenue, engagement, retention) and guardrail metrics (latency, error rate, safety).
- Pre-written stop/ship criteria before the test starts. Deciding after seeing results introduces bias.
- Sufficient exposure window. Most A/B tests need days to weeks depending on traffic volume and effect size.

**Statistical significance:**
- Set significance level (typically alpha = 0.05) and power (typically 0.80) before the test.
- Power analysis determines minimum sample size. Running an underpowered test wastes time -- it cannot detect real effects.
- Do not peek at results repeatedly and stop early when they look good. This inflates false positive rates. Use sequential testing methods if early stopping is needed.
- For multiple metrics, apply correction (Bonferroni or false discovery rate) to avoid false discoveries.

### Power Analysis

Before launching an A/B test, estimate required sample size:

- Define the minimum detectable effect (MDE): the smallest improvement worth shipping.
- Estimate baseline metric variance from historical data.
- Compute sample size for desired power (0.80) and significance (0.05).
- If required sample size exceeds available traffic within a reasonable window, either increase MDE tolerance or find a higher-variance proxy metric.

### Beyond A/B: Other Online Methods

- **Canary evaluation**: Route a small slice of traffic (1-5%) to the new model. Monitor for regressions before expanding. Not statistically powered for detecting improvements, but catches catastrophic failures fast.
- **Shadow testing**: Run the new model in parallel without serving its predictions. Compare outputs to production model and ground truth. Zero user risk. Use for high-stakes domains or when the new model changes output format.
- **Interleaving**: For ranking systems, mix results from both models in a single list and measure user preference. More statistically efficient than A/B for ranking.
- **Multi-armed bandit**: Dynamically allocate more traffic to the better-performing variant. Useful when you want to minimize regret during testing rather than maximize statistical clarity. Trade-off: harder to get clean causal estimates.

## Connecting Offline and Online

Offline and online metrics often disagree. A model that wins offline may lose online due to latency, feedback loops, or user behavior changes. Track the correlation between offline metrics and online outcomes over time. If they diverge, investigate whether your offline evaluation setup has data leakage, stale distributions, or missing features.

## When to Use This

- **Starting a new model project**: Set up offline evaluation with proper splits, slice metrics, and confidence intervals from day one.
- **Comparing model candidates**: Use offline evaluation to narrow candidates, then A/B test the top one or two against production.
- **Launching a model change**: Always run online evaluation (at minimum canary, ideally A/B) before full rollout.
- **Debugging a production regression**: Check both offline metrics on fresh data and online metrics by slice to isolate the problem.

## Red Flags to Watch For

- **No confidence intervals on offline metrics**: A single number without uncertainty is not evidence. Demand intervals.
- **Test set contamination**: If the test set was used for any tuning or selection, the estimate is biased. Keep test sets locked.
- **Peeking at A/B tests**: Checking results daily and stopping when significant inflates false positives dramatically.
- **Underpowered tests**: Running an A/B test without power analysis often wastes weeks with inconclusive results.
- **Global metrics only**: If you only report overall accuracy/MAE without slice breakdowns, you are hiding segment-level failures.
- **Offline-only evaluation for high-stakes launches**: No amount of offline testing substitutes for observing real user behavior.
- **Ignoring guardrail metrics**: Shipping a model that improves the primary metric but degrades latency or error rate will hurt users.
- **Same metric for training and evaluation**: If the model optimizes log loss but you evaluate on precision at a threshold, there is a disconnect. Align evaluation metrics with business objectives.
- **No temporal awareness**: Evaluating a time-sensitive model with random splits instead of temporal splits leaks future information and inflates scores.
