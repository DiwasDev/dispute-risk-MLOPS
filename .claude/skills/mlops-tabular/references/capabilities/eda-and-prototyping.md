# EDA and Prototyping for Tabular Data

Exploratory data analysis and rapid prototyping form the foundation of any tabular ML project. EDA reveals the structure, quality, and quirks of the data before any model is trained. Prototyping establishes a baseline quickly, proving whether the problem is solvable and setting a performance floor. Skipping EDA leads to models trained on misunderstood data. Skipping prototyping leads to over-engineered solutions for problems that might not need complexity.

## What EDA Must Cover

Every tabular EDA should systematically examine six areas. Missing any one of them creates blind spots that surface later as model failures or production bugs.

### Target Distribution

The target variable is the single most important column in the dataset. Before looking at any feature, understand the target:

- For classification: compute class frequencies and ratios. Determine if classes are balanced, mildly imbalanced (3:1), or severely imbalanced (100:1 or worse). The degree of imbalance dictates metric choice, resampling strategy, and threshold tuning decisions downstream.
- For regression: plot the distribution. Check for skewness, multimodality, outlier values, and natural bounds (e.g., prices cannot be negative). A heavily skewed target often benefits from log transformation during modeling.
- Check for missing target values. Rows with missing targets are useless for supervised learning and may indicate data pipeline issues.

### Feature Types and Distributions

Categorize every feature as numeric (continuous or discrete), categorical (nominal or ordinal), datetime, or text. This classification drives preprocessing choices:

- Numeric features: examine distributions, range, standard deviation, and percentiles (p1, p25, p50, p75, p99). Look for features with near-zero variance (they carry no information) and features with extreme outliers that could dominate distance-based methods.
- Categorical features: check cardinality (number of unique values). High-cardinality categoricals (thousands of unique values) need special encoding. Low-cardinality categoricals with dominant classes may not add predictive value. Look for categories that appear in training but not test (or vice versa).
- Datetime features: rarely used raw. Extract components (hour, day of week, month, days since event) as numeric features. Check for time-based leakage.

### Correlations and Relationships

Examine how features relate to each other and to the target:

- Compute pairwise correlations for numeric features. Highly correlated feature pairs (correlation above 0.95) indicate redundancy. Consider dropping one or using dimensionality reduction.
- For categorical features vs. numeric target: compare target distributions across categories using group-by aggregations.
- For categorical features vs. categorical target: compute cross-tabulations and look for categories that are strongly associated with specific outcomes.
- Scatter matrices or pair plots on a sampled subset of features help visualize non-linear relationships that correlation coefficients miss.

### Missing Values

Missing data is a first-class concern in tabular ML:

- Compute missing percentages per column. Features with more than 50-70% missing values rarely add predictive value and may introduce noise through imputation.
- Determine if missingness is random (MCAR), depends on observed values (MAR), or depends on the missing value itself (MNAR). MNAR is the hardest case -- the fact that a value is missing is itself informative (e.g., income is missing because respondents with high income decline to answer).
- Visualize missing patterns with matrix plots (tools like missingno). Correlated missingness across columns often indicates a systematic data collection issue.
- Check if missingness correlates with the target. If so, creating a binary "is_missing" indicator feature can capture that signal.

### Outliers

Outliers affect models differently. Tree-based models are robust to them; linear models and distance-based methods are not.

- Use percentile analysis (values beyond p1 or p99) rather than arbitrary thresholds.
- Distinguish between data errors (a human age of 999 is clearly wrong) and genuine extreme values (a legitimate high-value transaction). Data errors should be corrected or removed. Genuine extremes should be handled through winsorization or robust modeling techniques.
- Check if outlier rows cluster together. Systematic outlier groups may indicate a distinct subpopulation that needs separate treatment.

### Class Balance (for Classification)

Class imbalance deserves special attention because it affects model training, metric selection, and threshold tuning:

- Mild imbalance (majority class 60-80%): usually not a problem. Standard training works.
- Moderate imbalance (majority class 80-95%): consider stratified splitting, class-weighted training, or adjusted thresholds.
- Severe imbalance (majority class above 95%): standard accuracy is meaningless. Must use precision-recall metrics. May need resampling techniques (SMOTE, undersampling) or specialized loss functions.

## Rapid Prototyping in Notebooks

The goal of prototyping is speed, not perfection. A prototype answers the question: "Is there signal in this data for this prediction task?"

### The Baseline Model

Always start with the simplest reasonable model:

- For classification: logistic regression or a shallow decision tree. These are fast, interpretable, and establish whether basic linear or simple non-linear relationships exist between features and target.
- For regression: linear regression or a shallow gradient boosted tree. Same reasoning -- establish a floor.

The baseline should be trained in under an hour of human effort, including minimal preprocessing (drop columns with too many missing values, simple imputation for the rest, one-hot encode low-cardinality categoricals, drop high-cardinality categoricals). Do not optimize hyperparameters at this stage.

### What the Baseline Tells You

- If the baseline performs near random chance: the features may not contain signal for this target variable. Revisit problem framing and feature availability before investing more effort.
- If the baseline performs well (e.g., above 80% of the likely achievable performance): the problem is solvable. More sophisticated models will likely improve incrementally, not dramatically. Consider whether the baseline is good enough to ship.
- If the baseline shows high variance across cross-validation folds: the dataset may be too small or the signal too noisy for reliable modeling.

### Iterating in the Notebook

After the baseline, iterate on one dimension at a time:

1. Try a more powerful model (random forest, gradient boosting) with default hyperparameters. If improvement is marginal, the gains will come from better features, not better models.
2. Add feature engineering: interaction terms, polynomial features, domain-specific transformations, binning continuous variables.
3. Try different preprocessing: scaling for linear models, different imputation strategies, target encoding for high-cardinality categoricals.
4. Tune hyperparameters only after feature and model selection are settled. Use random search or Bayesian optimization, not grid search.

### Automated EDA Tools

Libraries like ydata-profiling (formerly pandas-profiling) can generate comprehensive EDA reports from a single function call. These are useful as a starting point but do not replace manual investigation. Automated tools show you what is in the data; they do not tell you what matters for your specific prediction task. Use them to get a quick overview, then drill into the areas that matter most for your problem.

## The Notebook-to-Production Transition

Notebooks are excellent for exploration and terrible for production. The transition is where most ML projects stall.

### What Stays in Notebooks

- One-off exploratory analysis that will not be repeated.
- Visualizations and summary statistics for stakeholder communication.
- Quick experiments comparing modeling approaches.

### What Must Move Out

- Data loading and preprocessing logic: this must be deterministic, testable, and version-controlled.
- Feature engineering: must be identical at training and serving time. Implement once in a shared module, not separately in a notebook and a serving pipeline.
- Model training and evaluation: must be reproducible with fixed random seeds, logged parameters, and tracked metrics.
- Any code that will run on a schedule or in response to new data.

### The Transition Pattern

1. Extract functions from notebook cells into Python modules with proper signatures, type hints, and docstrings.
2. Replace hardcoded paths and parameters with configuration objects or YAML files.
3. Add unit tests for preprocessing and feature engineering logic.
4. Wrap the training flow in a pipeline framework (e.g., ZenML, Kedro) that handles orchestration, caching, and artifact tracking.
5. Delete the notebook or archive it. A notebook that co-exists with production code inevitably drifts and becomes a source of confusion.

## When to Stop Exploring and Start Building

EDA and prototyping can become a trap. Diminishing returns set in fast, and indefinite exploration delays value delivery. Apply these decision rules:

- **Stop exploring when** the baseline model performs within 80% of your target metric and you have identified the top predictive features.
- **Stop exploring when** additional feature engineering yields less than 1-2% improvement in cross-validated performance.
- **Stop exploring when** you understand the data well enough to write a one-paragraph summary of its key characteristics, quality issues, and predictive signals.
- **Keep exploring if** the model performs near random chance and you have not yet exhausted available data sources or feature ideas.
- **Keep exploring if** you have discovered a data quality issue (leakage, label errors, systematic missingness) that invalidates current results.

## When to Use This

- At the start of any new tabular ML project, before committing to a model architecture or pipeline design.
- When handed a new dataset and asked to assess its suitability for a prediction task.
- When an existing model is underperforming and the team needs to revisit data assumptions.
- When onboarding to a project to understand what the data looks like and how it was originally explored.

## Red Flags to Watch For

- **No EDA at all**: Jumping straight to model training without understanding the data is the most common cause of wasted effort. The model may be learning artifacts, not signal.
- **EDA without examining the target**: Analyzing features in isolation without understanding the target distribution leads to blind modeling.
- **Ignoring class imbalance**: Training a model on severely imbalanced data with default settings and evaluating on accuracy produces misleadingly high scores.
- **Data leakage in the prototype**: Features that are derived from or correlated with the target in ways that would not be available at prediction time. Common examples: using future information, including the target under a different name, or using aggregates computed on the full dataset including the test set.
- **Over-engineering the prototype**: Spending weeks on hyperparameter tuning and complex feature engineering before establishing that the basic signal exists. Prototype first, optimize later.
- **Notebook as production code**: If the notebook is being run on a schedule or called by other systems, it needs to be refactored into proper modules.
- **No reproducibility**: If the notebook cannot be re-run from top to bottom and produce the same results, the analysis is not trustworthy. Pin random seeds, pin library versions, and use deterministic data loading.
- **Exploring without a stopping criterion**: Endless EDA without a clear decision point delays the project. Set a time box (one to two days for initial EDA, one week maximum for prototyping) and commit to a direction.
