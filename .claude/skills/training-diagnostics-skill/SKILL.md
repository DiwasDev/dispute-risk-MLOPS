# Training Diagnostics Skill

## Settings
```
OPTIMIZER_CHOICE = 5         # How much optimizer tuning is needed?
                             # 1-3: Use Adam defaults and move on
                             # 4-7: Compare optimizers, tune learning rate
                             # 8-10: Full optimizer analysis, scheduler tuning, convergence guarantees

DATA_SCALE = 5               # Dataset size — determines which optimizer variant to use
                             # 1-3: <10K rows — Normal Equation or batch GD
                             # 4-7: 10K–1M rows — mini-batch GD
                             # 8-10: >1M rows — distributed SGD or adaptive optimizers

TRAINING_STABILITY = 5       # How stable is the training process?
                             # 1-3: Converges cleanly — document and move on
                             # 4-7: Some instability — tune LR, add diagnostics
                             # 8-10: Diverging or stuck — full diagnostic protocol
```

---

## What this prevents

Training a model is not just pressing "fit." Things go wrong constantly — loss explodes, training stalls, learning rate is off by 10×, features are on different scales. The AI will run training and return results without telling you any of this happened.

This skill teaches you to diagnose training before trusting the outputs.

---

## Two paths to finding the best parameters

### Path A: Closed-form (Normal Equation)
```
Best parameters = (XᵀX)⁻¹ Xᵀy
```
**When to use:** Small data (<10K rows), few features (<100), linear regression only.
**Advantage:** Exact answer, no iteration, no learning rate to tune.
**Limitation:** Inverting the matrix costs O(features³). 1,000 features = 1 billion operations. Breaks at scale.

### Path B: Gradient Descent
Start at a random point. Measure which direction is "downhill" (the gradient). Take a step. Repeat until flat.

**When to use:** Everything else. Large data, many features, any non-linear model, neural networks.

The same idea proposed by Cauchy in 1847 powers every neural network trained today.

---

## Gradient descent variants — which to use

| Variant | How it works | When to use |
|---|---|---|
| Batch GD | All data per step — exact gradient | Small datasets. Stable but slow. |
| SGD | One random point per step | Large data. Fast but noisy. |
| Mini-batch GD | Batch of 32–512 points | The practical default. 95% of real systems. |
| Adam | Adapts learning rate per-parameter based on gradient history | Deep learning default. Handles diverse feature scales. |
| AdaGrad | Decreases LR for frequent features | Sparse data, NLP |
| RMSProp | Running average of squared gradients | RNNs, non-stationary objectives |

**Start with Adam.** Only switch to SGD + momentum for production neural networks where you need more control, or when Adam is overfitting to early training noise.

---

## The learning rate — the most important hyperparameter

| Learning rate | What happens | What it looks like |
|---|---|---|
| Too large (e.g., 1.0) | Overshoots minimum. Loss oscillates or diverges to ∞ | Loss bounces wildly up and down |
| Too small (e.g., 0.000001) | Crawls. Millions of steps, barely moves | Loss decreases but almost invisibly slowly |
| Just right (e.g., 0.001) | Smooth convergence | Loss decreases steadily, levels off |

**Practical starting points:**
- Adam: `lr = 0.001`
- SGD: `lr = 0.01`
- Fine-tuning pretrained model: `lr = 0.0001`

If you have no idea: start at `0.001`, plot the loss curve, and adjust from there.

---

## The training diagnostic protocol

Run this whenever training behaves unexpectedly.

### Step 1: Plot the loss curve
Every training run should produce a loss-vs-epoch plot before you trust results.

What to look for:
- **Smooth decrease, levels off** → converged correctly
- **Wild oscillation** → learning rate too high → reduce by 10×
- **Flat from the start** → learning rate too small, or features not scaled → scale features, increase LR
- **Decreasing then exploding** → NaN in data or gradient explosion → check data, clip gradients
- **Training loss good, val loss bad** → overfitting → add regularization (see generalization-skill)
- **Both losses stuck high** → underfitting → bigger model, more features, more training

### Step 2: Check feature scales
The most common silent killer of gradient descent.

If features are on wildly different scales (age: 0–100, income: 0–10,000,000), gradients for the large-scale feature dominate. The optimizer spends all its time on that feature while barely touching others.

```python
# Check before training
df.describe()  # Compare min/max across all features

# Fix: StandardScaler (zero mean, unit variance)
from sklearn.preprocessing import StandardScaler
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)  # NEVER fit on test
```

### Step 3: Check for NaN/Inf
A single NaN in training data can silently corrupt the entire model.

```python
# Before training
assert not X_train.isnull().any().any(), "NaN in features"
assert not y_train.isnull().any(), "NaN in target"
assert not np.isinf(X_train.values).any(), "Inf in features"
```

### Step 4: Gradient clipping (for deep learning)
If loss is exploding or going to NaN in a neural network:
```python
# PyTorch
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

# Keras / TensorFlow
optimizer = Adam(clipnorm=1.0)
```

### Step 5: Learning rate schedules
Don't use a fixed learning rate for long training runs. Start high (fast learning), decay as you approach the minimum (fine-grained convergence).

```python
# Step decay: reduce LR by half every 10 epochs
scheduler = StepLR(optimizer, step_size=10, gamma=0.5)

# Cosine annealing: smooth decay
scheduler = CosineAnnealingLR(optimizer, T_max=100)

# ReduceLROnPlateau: reduce when validation loss stops improving
scheduler = ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
```

---

## Common training failure cheat sheet

| Symptom | Likely cause | Fix |
|---|---|---|
| Loss oscillates wildly | Learning rate too high | Reduce by 10× |
| Loss decreases extremely slowly | LR too small, or unscaled features | Increase LR, or standardize features |
| Loss stuck from epoch 1 | LR too small, dead neurons, wrong loss | Try 10× LR, check activation functions |
| Loss is NaN or Inf | NaN in data, exploding gradients | Check data, clip gradients |
| Loss goes to 0.000 | Data leakage or target in features | Audit features immediately |
| Training loss good, val loss high | Overfitting | Regularize, reduce complexity, more data |
| Both losses high and stuck | Underfitting | More capacity, more features, more epochs |
| Training fast at first, then stalls | LR too large for final convergence | Add LR decay / scheduler |
| Performance varies wildly each run | High variance in initialization | Fix random seed, increase batch size |

---

## Choosing between Normal Equation and Gradient Descent

| Situation | Use |
|---|---|
| Linear regression, <10K rows, <100 features | Normal Equation — exact, no tuning |
| Linear regression, large data or many features | Gradient Descent |
| Any non-linear model (trees, neural nets) | Gradient Descent (always) |
| Need exact reproducible solution | Normal Equation (if feasible) |
| Memory constrained (can't load all data at once) | Gradient Descent with mini-batches |

---

## Prompt templates

### Setting up training correctly
```
Set up training for this model with production-quality hygiene:

1. Check for NaN/Inf in all features and the target before training.
   Fail loudly if found — do NOT silently impute here.
2. Standardize all features AFTER the train-test split
   (fit scaler on train only, transform both).
3. Use Adam optimizer with lr = 0.001 as starting point.
4. Train for [N] epochs with early stopping:
   - patience = 10 epochs
   - monitor = validation loss
   - restore best weights
5. After training, plot:
   - Training loss vs epoch
   - Validation loss vs epoch (overlaid on same plot)
   Tell me what the curves look like and diagnose.
```

### Diagnosing a training failure
```
Training is not converging. Diagnose systematically:

1. Plot loss curve (train + val). Describe the shape.
   Oscillating? Flat? Exploding? Slowly decreasing?

2. Print min/max/mean for every feature. Flag any feature where
   max/min > 1000. These need scaling.

3. Check for NaN/Inf in data and in the loss at each epoch.

4. Try these in order and report results:
   a. Reduce learning rate by 10× (try 0.0001 if current is 0.001)
   b. Standardize all features
   c. Switch optimizer from [current] to Adam
   d. Add gradient clipping (max_norm=1.0)

Show me the loss curve before and after each fix.
```

### Learning rate search
```
Run a learning rate range test to find the best LR:

1. Train for 1 epoch with LR increasing from 1e-7 to 1.0 (log scale)
2. Plot: LR on x-axis (log scale), loss on y-axis
3. Identify: the LR just before loss starts increasing (that's the sweet spot)
4. Use: [sweet spot LR × 0.1] as the starting LR for full training

This is the Leslie Smith LR Range Test approach.
```

---

## Anti-patterns

- Never start training without plotting the loss curve
- Never train on unscaled features with gradient-based optimizers
- Never silently continue training when loss is NaN — stop and diagnose
- Never use the same fixed learning rate for the entire training run on deep models
- Never report test set metrics if you used the test set to tune the learning rate
- Never choose an optimizer without knowing what data size you have
- Never assume "more epochs = better" — use early stopping

---

## The principle

Optimization is not passive. It is not enough to call `.fit()` and trust the output.

The optimizer is walking downhill on a loss surface. If the surface is badly shaped (unscaled features), if the step size is wrong (learning rate), or if the terrain has cliffs (NaN values, gradient explosion), the walk fails — and it fails silently.

Gradient descent has been the engine of AI since 1847. Understanding it is not optional for anyone building systems that learn.
