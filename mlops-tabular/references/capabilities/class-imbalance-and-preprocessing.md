# Class Imbalance and Preprocessing for Tabular ML

Preprocessing and class imbalance handling are foundational decisions that affect every downstream step in a tabular ML pipeline. Get preprocessing wrong and the model trains on garbage. Handle imbalance incorrectly and the model ignores the minority class or overfits to synthetic examples. Both topics require understanding when to intervene and when to leave the data alone.

## When Class Imbalance Matters and When It Does Not

Class imbalance is not automatically a problem. The decision to address it depends on the problem context, the model type, and the evaluation metric.

### When Imbalance Is a Real Problem

- The minority class is the class you care about most (fraud cases, disease diagnoses, equipment failures) and the model needs high recall on that class.
- The model outputs are used with a fixed threshold (e.g., predict positive if probability > 0.5) rather than a tuned threshold. Default thresholds on imbalanced data almost always favor the majority class.
- The model type is sensitive to class proportions: logistic regression and neural networks can be biased toward the majority class without intervention. Naive Bayes directly uses class priors.
- The imbalance is severe (minority class below 5% of training data) and the dataset is small (fewer than a few thousand minority examples in absolute terms).

### When Imbalance Is Not a Problem

- Tree-based models (random forests, gradient boosting) handle moderate imbalance (up to roughly 10:1) well without intervention, especially with enough data. They split on information gain, which naturally seeks minority-class signal.
- You are using ranking metrics (AUC-ROC, AUC-PR) rather than threshold-dependent metrics. AUC-ROC evaluates across all thresholds and is less affected by class proportions.
- You have sufficient absolute count of minority examples. Even at 1% prevalence, 10,000 minority examples in a million-row dataset is plenty for most models to learn from.
- The business use case weights both classes roughly equally. Not every problem requires high recall on the minority class.

### The Decision Framework

Before applying any resampling technique, ask:
1. What is the minority class ratio? Below 5% with fewer than 1,000 minority examples warrants intervention.
2. What metric am I optimizing? If it is precision-recall based, imbalance handling may help. If it is AUC-ROC, it likely does not.
3. What model am I using? Tree-based ensembles are more robust than linear models.
4. Have I tried threshold tuning first? Adjusting the classification threshold is simpler than modifying the training distribution and often sufficient.

## Techniques for Handling Class Imbalance

### Threshold Tuning

The simplest and most underused approach. Train the model on the original data distribution, then select the classification threshold that optimizes the desired metric (F1, precision at target recall, etc.) on the validation set. This avoids modifying the training distribution entirely and works well when the model produces calibrated probabilities.

Use threshold tuning as the first approach. If it yields acceptable performance, stop here. It has no risk of overfitting to synthetic data and preserves the natural class prior.

### Class Weights

Most sklearn classifiers accept a class_weight parameter. Setting class_weight="balanced" re-weights the loss function so that minority class errors are penalized proportionally to their rarity. This has the same effect as oversampling the minority class but without creating duplicate rows.

Advantages: no change to the dataset, no synthetic data, works within the standard training loop. Supported by logistic regression, SVM, random forest, and gradient boosting classifiers.

Limitations: the "balanced" setting may over-correct. For fine-grained control, pass a dictionary mapping class labels to specific weights derived from the cost of each error type.

### SMOTE (Synthetic Minority Over-sampling Technique)

SMOTE generates synthetic minority class examples by interpolating between existing minority samples in feature space. It selects a minority example, finds its k nearest minority neighbors, and creates new examples along the line segments connecting them.

When to use SMOTE: the minority class has very few examples (hundreds), features are continuous and meaningful in interpolated space, and simpler methods (threshold tuning, class weights) are insufficient.

When not to use SMOTE: features include high-cardinality categoricals (interpolation between categories is nonsensical), the dataset is already large (thousands of minority examples), or the model is tree-based and handles imbalance natively.

Critical implementation rule: SMOTE must be applied only to the training set, never to validation or test sets. Applying SMOTE before the train/test split creates synthetic examples that leak information between splits, inflating performance estimates.

The standard pattern is: split data first, then apply SMOTE to training data only, then train the model. In a pipeline, this means the SMOTE step receives already-split training features and labels and returns resampled training features and labels. The test set remains untouched.

Check the imbalance ratio before applying SMOTE. If the minority class is already above 30% of the dataset, SMOTE adds unnecessary synthetic noise. Use a threshold (e.g., only apply if minority ratio is below 0.3) and log whether SMOTE was triggered and how many synthetic samples were created.

### Undersampling

Randomly remove majority class examples to match the minority class count. Simple and fast but throws away data, which can hurt performance when the dataset is small.

Use undersampling when: the dataset is very large and training time is a constraint, or the majority class has much redundancy.

Avoid undersampling when: the dataset is small or the majority class contains important subgroups that random removal would lose.

## Preprocessing for Tabular Data

### Scaling

Scaling brings numeric features to comparable ranges. It is required for distance-based models (KNN, SVM, logistic regression with regularization) and neural networks. It is unnecessary for tree-based models (random forest, gradient boosting, XGBoost) because they split on feature rank, not magnitude.

**StandardScaler**: Subtracts the mean and divides by standard deviation: `z = (x - mean) / std`. Produces features with zero mean and unit variance. Use as the default for linear models and neural networks. Sensitive to outliers because the mean and standard deviation are affected by extreme values.

**MinMaxScaler**: Scales features to a fixed range (typically 0 to 1): `x_scaled = (x - x_min) / (x_max - x_min)`. Use when features have known bounds or when the algorithm requires bounded inputs. More sensitive to outliers than StandardScaler because a single extreme value compresses all other values into a narrow range.

**RobustScaler**: Uses median and interquartile range instead of mean and standard deviation: `x_scaled = (x - median) / IQR`. More robust to outliers. Use when the data contains significant outliers that should not dominate the scaling.

**Why scaling matters -- a concrete example:** Consider two features: income (range 30K-70K) and age (range 25-45). Without scaling, income values are ~1,500x larger than age values. In distance-based calculations (KNN, SVM, logistic regression with regularization), income dominates by a factor of approximately 4,000,000x (because distances are squared). After StandardScaler, both features scale to approximately -1.41 to +1.41, equalizing their influence.

Critical implementation rule: fit the scaler on training data only, then transform both training and test data using the fitted scaler. Fitting on the full dataset before splitting leaks test set statistics into the training process. Store the fitted scaler as a pipeline artifact so it can be applied identically during inference.

### Encoding Categorical Features

**One-hot encoding**: Creates a binary column for each category value. Use for nominal categoricals with low to moderate cardinality (fewer than 20-30 unique values). Produces sparse, interpretable features. High-cardinality categoricals produce an impractical number of columns.

**Ordinal encoding**: Maps categories to integers (0, 1, 2, ...). Use for ordinal categoricals where the order matters (e.g., low/medium/high, education levels). Do not use for nominal categoricals -- the implied ordering misleads models that assume numeric relationships.

**Target encoding**: Replaces each category with the mean of the target variable for that category (e.g., if city "Mumbai" has 60% default rate, it becomes 0.60). Effective for high-cardinality categoricals. Must be computed on training data only with smoothing or cross-validation to prevent target leakage. Regularize by blending category means with the global mean, weighted by category frequency -- this prevents overfitting on categories with very few examples (a category with 2 observations and 100% default rate should not get an encoding of 1.0).

**Handling unknown categories at serving time:** During training, randomly reassign approximately 5% of training examples to an "UNKNOWN" category. This teaches the model a reasonable behavior for categories it has never seen, rather than crashing or defaulting to an arbitrary value at serving time.

### Missing Value Imputation

- **Numeric features**: Median imputation is the safest default (robust to outliers and skew). Mean imputation is acceptable for normally distributed features. For tree-based models, some implementations (XGBoost, LightGBM) handle missing values natively without imputation.
- **Categorical features**: Impute with the most frequent value or create an explicit "missing" category. The latter is preferable when missingness itself carries signal.
- **Add missing indicators**: Create a binary column that flags whether the original value was missing. This preserves the information that the value was absent, which can be predictive.

## The sklearn.Pipeline Pattern

Bundling preprocessing with the model into a single sklearn Pipeline is essential for production ML. The pipeline ensures that the exact same transformations applied during training are applied during inference, in the same order, with the same fitted parameters.

A preprocessing pipeline typically uses ColumnTransformer to apply different transformations to different column types: scaling for numeric columns, encoding for categorical columns, imputation for columns with missing values. The ColumnTransformer feeds into the model as the final step.

Benefits of this pattern: a single object to serialize, version, and deploy. No risk of preprocessing mismatch between training and serving. Easy to add or remove preprocessing steps. Compatible with cross-validation (the pipeline is fit inside each fold, preventing leakage).

## When to Use PCA

PCA (Principal Component Analysis) reduces dimensionality by projecting features onto the directions of maximum variance. It is useful in specific situations but should not be applied by default.

Use PCA when: the feature count is very high relative to the sample count (hundreds of features, thousands of rows), many features are correlated (PCA consolidates correlated information), or the model is sensitive to high dimensionality (logistic regression, KNN).

Do not use PCA when: the features are already few and uncorrelated, interpretability matters (PCA components are linear combinations of original features and not interpretable), or the model is tree-based (trees handle high dimensionality and correlated features natively).

When applying PCA: standardize features first (PCA is sensitive to scale). Choose the number of components by examining cumulative explained variance -- keep enough components to explain 90-95% of variance. Fit PCA on training data only, transform both training and test data. Log the explained variance ratio so the trade-off between dimensionality reduction and information loss is visible.

## When to Use This

- When building a training pipeline for tabular classification and deciding whether to address class imbalance.
- When designing the preprocessing stage of a pipeline and choosing which transformations to apply to which feature types.
- When debugging a model that performs well on the majority class but poorly on the minority class.
- When transitioning from a notebook prototype to a production pipeline and needing to formalize preprocessing into reproducible steps.
- When reviewing an existing pipeline for preprocessing leakage or misapplied transformations.

## Red Flags to Watch For

- **SMOTE applied before train/test split**: This is the most common preprocessing leakage error. Synthetic examples generated from the full dataset contaminate the test set evaluation.
- **Scaler fit on full dataset**: Fitting StandardScaler or any transformer on data that includes the test set leaks test set statistics into training. Always fit on training data only.
- **One-hot encoding high-cardinality features**: Encoding a feature with 10,000 unique values into 10,000 binary columns is computationally expensive and adds noise. Use target encoding or embeddings instead.
- **Applying SMOTE to already-balanced data**: If the minority class is 40% of the dataset, SMOTE adds unnecessary synthetic noise. Check the imbalance ratio before resampling.
- **Ignoring class imbalance entirely**: Training on severely imbalanced data with default settings and evaluating on accuracy produces a model that appears good but predicts the majority class almost exclusively.
- **Scaling features for tree-based models**: StandardScaler on features that feed into a random forest or gradient boosting model adds preprocessing complexity without any benefit. Trees are scale-invariant.
- **PCA on a small feature set**: Applying PCA to 10 features makes little sense and sacrifices interpretability for no dimensionality gain.
- **Missing value imputation without indicators**: Imputing missing values without flagging which values were imputed destroys potentially useful signal about data completeness.
- **Different preprocessing at training and serving time**: If the training pipeline uses one set of transformations and the serving pipeline uses another (or uses hardcoded values instead of the fitted transformer), predictions will be silently wrong. Always serialize and reuse the fitted pipeline.
- **No logging of preprocessing decisions**: If the pipeline applies SMOTE, PCA, or conditional transformations, log whether they were triggered and what the before/after data shapes look like. Silent conditional preprocessing makes debugging impossible.
