# SOLID Principles and Design Patterns for ML

SOLID principles were conceived for statically-typed object-oriented languages, but the underlying ideas -- managing dependencies, isolating change, and designing for extension -- apply directly to ML systems in Python. ML pipelines are composed of interchangeable components (models, preprocessors, validators, monitors) that benefit enormously from principled interface design. Design patterns provide tested solutions for structuring these components. This reference adapts SOLID and the most relevant Gang of Four patterns specifically for ML code review.

## SOLID Principles in ML Context

### Single Responsibility Principle (SRP)

One class should have one reason to change. In ML projects, the most common SRP violation is the monolithic pipeline class that handles data loading, preprocessing, training, evaluation, and artifact management. When the preprocessing logic changes, the entire class must be modified and retested.

**Correct separation**: A `DataLoader` class loads and validates data. A `FeatureEngineer` class transforms features. A `ModelTrainer` class fits the model. An `Evaluator` class computes metrics. Each class changes for exactly one reason: its specific responsibility changes.

**ML-specific SRP test**: If you need to modify training hyperparameters, should the data loading code be affected? If you need to change a feature transformation, should the evaluation code need retesting? If the answer is yes, the responsibilities are entangled.

### Open/Closed Principle (OCP)

Software entities should be open for extension but closed for modification. In ML, this means adding a new model type, preprocessor, or evaluation metric should not require modifying existing code.

**Application**: Define a model interface (Protocol class or abstract base class). Adding XGBoost support should mean writing a new class that implements the interface, not modifying the existing RandomForest training code. The pipeline orchestrator accepts any object matching the interface.

**Extension via composition**: Instead of modifying a training function to support a new hyperparameter search strategy, accept a search strategy object. `GridSearchStrategy`, `RandomSearchStrategy`, and `BayesianSearchStrategy` all implement the same interface. The training function is closed to modification but open to new strategies.

### Liskov Substitution Principle (LSP)

Subtypes must be substitutable for their base types. In ML, any model implementation that satisfies the model interface must be usable interchangeably without breaking the pipeline.

**Practical test**: If `XGBoostModel` and `RandomForestModel` both implement `ModelInterface`, replacing one with the other in the pipeline should not cause errors. Both must accept the same input format, return the same output format, and support the same lifecycle methods (fit, predict, save, load).

**Common LSP violation in ML**: A model class that requires additional preprocessing not handled by the standard pipeline. If `NeuralNetModel` requires tensor conversion but `TreeModel` does not, and this conversion is handled inside the model class, the pipeline cannot substitute them freely. Solution: make the required preprocessing explicit in the interface or handle it uniformly.

### Interface Segregation Principle (ISP)

Clients should not be forced to depend on methods they do not use. In ML pipelines, this means a preprocessing step should not be forced to implement methods it does not need.

**Common ISP violation**: A `PipelineStep` base class that requires `fit`, `transform`, `evaluate`, and `save` methods. A static feature selection step does not need `fit`. A data loading step does not need `transform`. Split into focused interfaces: `Fittable`, `Transformable`, `Evaluatable`.

**ML-specific application**: Not every model needs `predict_proba`. Not every preprocessor needs `inverse_transform`. Define minimal interfaces and compose them.

### Dependency Inversion Principle (DIP)

High-level modules should not depend on low-level modules. Both should depend on abstractions. In ML, the pipeline orchestrator should depend on a `ModelInterface`, not on `XGBoostClassifier` directly.

**Before DIP**: `train_pipeline` imports and instantiates `XGBClassifier` directly. Changing the model requires modifying `train_pipeline`.

**After DIP**: `train_pipeline` accepts a `ModelInterface` parameter. The concrete model is injected by configuration or a factory. The pipeline code never mentions a specific model library.

**Why this matters for ML**: Model libraries change frequently. XGBoost gets replaced by LightGBM, which gets replaced by CatBoost. A pipeline that depends on abstractions survives these changes with zero modification to orchestration code.

## Design Patterns for ML

### Strategy Pattern (Model Selection)

The most natural pattern for ML: encapsulate different algorithms behind a common interface and swap them at runtime.

**Use case**: Model selection. Define a `ModelStrategy` protocol with `fit(X, y)`, `predict(X)`, `save(path)`, `load(path)`. Implement `XGBoostStrategy`, `RandomForestStrategy`, `LogisticRegressionStrategy`. The training pipeline accepts any strategy. Configuration determines which strategy is used.

**Use case**: Feature selection. `CorrelationSelector`, `MutualInformationSelector`, `BorutaSelector` all implement `FeatureSelector` with `fit(X, y)` and `transform(X)`.

### Factory Pattern (Pipeline Construction)

Factories create complex objects without exposing construction logic. In ML, pipelines are complex objects assembled from many components.

**Use case**: A `PipelineFactory` reads a configuration file and constructs the appropriate data loader, preprocessor, model, and evaluator. Changing the configuration changes the pipeline without modifying construction code.

**Use case**: A `ModelFactory` that maps string names to model classes. `ModelFactory.create("xgboost", params)` returns a configured XGBoost model. This centralizes model construction and makes it configuration-driven.

### Template Method (Training Loops)

Define the skeleton of an algorithm in a base class, letting subclasses override specific steps without changing the structure.

**Use case**: A `BaseTrainer` defines the training loop: load data, preprocess, fit model, evaluate, log metrics, save artifacts. Subclasses override specific steps. `TabularTrainer` overrides preprocessing with pandas operations. `TextTrainer` overrides preprocessing with tokenization. The overall flow remains consistent.

**Benefit for code review**: Reviewers know where to look. The template defines the invariant structure; review focuses on the overridden steps.

### Observer Pattern (Monitoring Callbacks)

Decouples event producers from event consumers. Components emit events (training started, epoch completed, metric computed) and observers react without the component knowing who is listening.

**Use case**: Training callbacks. A `MetricsLogger` observes training progress and logs to MLflow. A `EarlyStopMonitor` observes validation loss and triggers early stopping. A `SlackNotifier` observes training completion and sends a message. Adding a new callback requires no modification to the training code.

**Use case**: Data validation events. A pipeline emits events when data quality checks fail. Observers can log, alert, or halt the pipeline independently.

## When to Use This

- When reviewing code that introduces new model types or pipeline components -- verify interface compliance.
- When a codebase has grown rigid and changes in one area cascade through unrelated code.
- When the team struggles to add new features or swap components without breaking existing functionality.
- When reviewing pipeline orchestration code for proper dependency management.
- When a God class has emerged and needs decomposition into principled components.

## Red Flags to Watch For

- Pipeline code that imports specific model libraries (XGBoost, LightGBM) directly instead of depending on an interface.
- A single class with more than 5 public methods spanning different concerns (data, model, evaluation, serving).
- Adding a new model type requires modifying existing training or evaluation code.
- Steps forced to implement no-op methods because the base class interface is too broad.
- Factory or Strategy patterns introduced prematurely when only one concrete implementation exists -- wait for the second use case.
- Configuration dictionaries passed through 4+ function calls -- a sign of missing abstractions.
- Inheritance hierarchies deeper than 2 levels -- prefer composition in Python.
