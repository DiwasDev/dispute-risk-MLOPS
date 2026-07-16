# Model Hypothesis Skill

## Settings
```
DATA_SIZE = 5                # How much training data do you have?
                             # 1-3: <5K rows — simple hypothesis essential
                             # 4-7: 5K–500K rows — moderate complexity justified
                             # 8-10: >500K rows — complex hypotheses viable

EXPLAINABILITY = 5           # Does the model need to be explained?
                             # 1-3: Black box fine (ads, recommendations)
                             # 4-7: Intuition needed (internal tools, PMs)
                             # 8-10: Full audit trail (finance, healthcare, legal)

ALGORITHM_FAMILIARITY = 5    # How well does the student know this algorithm?
                             # 1-3: First encounter — build from first principles
                             # 4-7: Seen it before — focus on trade-offs
                             # 8-10: Expert — focus on failure modes and edge cases
```

---

## What this prevents

When a student encounters a new algorithm — XGBoost, SVM, a transformer — they either:
(a) Use it as a black box without understanding what it assumes about the data, or
(b) Feel lost because they don't know where to start understanding it.

This skill gives them a universal framework that works for every algorithm ever invented, from linear regression (1805) to GPT-4 (2023).

---

## The universal ML architecture

Every ML algorithm ever invented follows the same three-step structure:

```
HYPOTHESIS → LOSS FUNCTION → OPTIMIZATION
```

**Step 1 — HYPOTHESIS:** What mathematical shape does this model assume the world follows?
**Step 2 — LOSS FUNCTION:** How does it measure how wrong it currently is?
**Step 3 — OPTIMIZATION:** How does it find the parameters that make it least wrong?

If you understand these three things for any algorithm, you understand that algorithm at its core.

---

## The hypothesis is a bet

Choosing a model is choosing what you believe about the world.

| Hypothesis | The bet | What you give up |
|---|---|---|
| Linear (straight line) | The relationship is approximately linear | Can't capture curves or complex interactions |
| Polynomial (curve) | The relationship has curvature of degree N | Risk of overfitting, harder to interpret |
| Decision tree (splits) | Data separates into meaningful regions | Sharp boundaries, unstable with small data |
| Random forest (many trees) | No single tree is reliable; ensemble is | Slower, harder to interpret individual decisions |
| Neural network (any shape) | Given enough data, any pattern can be learned | Needs massive data, black box, expensive to train |
| Linear + kernel (SVM) | Data is separable in a higher-dimensional space | Slow on large data, kernel choice matters |

**The question is never "which is most powerful?"**

The question is: which hypothesis matches my situation?
- 500 rows? Linear regression will likely beat a neural network. Not enough data.
- 5 million rows with complex patterns? Neural network wins.
- Explain to a bank regulator why a loan was denied? Linear regression — you can point to coefficients.
- Real-time prediction under 1ms? Simple model — complex models are slower.

---

## The algorithm interrogation template

Use this for every new algorithm you encounter, for the rest of your career:

**1. HUMAN PROBLEM:** What real-world prediction or decision does this solve?

**2. HYPOTHESIS:** What mathematical structure does it assume about the data?

**3. LOSS FUNCTION:** How does it measure badness? Is this right for my problem?

**4. OPTIMIZATION:** How does it find the best parameters? What are the failure modes?

**5. ASSUMPTIONS:** What must be true about the data for this to work? How do I check?

**6. OVERFITTING RISK:** When does it overfit? What regularization exists?

**7. PRODUCTION GAPS:** What breaks between notebook and production?
(Data drift, leakage, latency, explainability, retraining cost)

Question 7 separates people who build models from people who deploy systems.

---

## Applied to common algorithms

| Algorithm | Hypothesis | Loss | Optimization |
|---|---|---|---|
| Linear Regression | Data follows a straight line | MSE | Normal equation or gradient descent |
| Logistic Regression | Log-odds are linearly related to features | Cross-entropy | Gradient descent |
| Decision Tree | Data splits cleanly by feature thresholds | Gini impurity or entropy | Greedy recursive splitting |
| Random Forest | Average of many de-correlated trees reduces variance | Aggregated Gini / entropy | Train N trees independently |
| XGBoost | Each new tree corrects residuals of the previous ensemble | Custom differentiable loss | Gradient boosting |
| SVM | A maximum-margin hyperplane separates classes | Hinge loss | Quadratic programming |
| K-Means | Points belong to the cluster whose center is nearest | Within-cluster sum of squares | Iterative centroid update |
| Neural Network | Layers of weighted connections approximate any function | Cross-entropy or MSE | Backpropagation + gradient descent |

---

## The model complexity ladder

Start simple. Add complexity only when you can justify it.

```
Mean predictor (can you even beat this?)
        ↓
Simple rule / business heuristic
        ↓
Linear Regression / Logistic Regression
        ↓
Ridge / Lasso (regularized linear)
        ↓
Decision Tree
        ↓
Random Forest / Gradient Boosting (XGBoost, LightGBM)
        ↓
Neural Network (only with large data and non-linear patterns)
```

Every step up the ladder costs you: interpretability, training speed, data requirements, and debugging difficulty. Justify each step.

---

## Prompt templates

### Interrogating a new algorithm
```
I'm learning [algorithm name]. Walk me through it using the 7-question framework:

1. What real-world problem is this designed to solve?
2. What is the hypothesis — what shape does it assume the data follows?
3. What is the loss function? Is MSE/cross-entropy the default, and why?
4. How does it optimize — closed form, gradient descent, or something else?
   What are the failure modes of that optimization?
5. What assumptions must hold in the data?
   How do I check if they're violated?
6. When does this algorithm overfit? What regularization is built in or available?
7. What typically breaks when this goes from notebook to production?

Then: for my specific problem [describe it], is this a good hypothesis?
What would a simpler alternative look like?
```

### Choosing between hypotheses
```
I'm deciding between these models for [describe problem]:
- [Model A]
- [Model B]
- [Model C]

My constraints:
- Training data size: [N rows]
- Explainability required: [yes/no — reason]
- Inference speed required: [latency target]
- Deployment environment: [cloud / edge / browser]

For each model, tell me:
1. What hypothesis it makes about my data
2. Whether that hypothesis is likely true given what I know
3. The main risk of using it here
4. Which I should start with and why

Then build a simple baseline with [simplest option] first.
```

### Explaining coefficients to stakeholders
```
The model is trained. Now explain what it learned — but not in ML terms.

For a linear model:
1. List the top 5 features by standardized coefficient magnitude
2. For each: "When [feature] increases by [1 unit], [target] changes by [amount],
   all else equal"
3. Translate that into a plain English business insight
4. Flag any coefficient that seems counterintuitive — it may indicate
   multicollinearity or a lurking confounding variable

For a tree model:
1. Show feature importances (bar chart + table)
2. Show one example decision path from root to leaf
3. Translate that path into: "This customer was predicted to churn because..."
```

---

## Anti-patterns

- Never use a complex model without being able to state its hypothesis
- Never choose an algorithm before knowing the data size, explainability needs, and latency constraints
- Never skip the baseline — if you can't beat the mean predictor, nothing else matters
- Never interpret raw coefficients from a model with features on different scales
- Never assume "more parameters = better" — the hypothesis must match the data
- Never use a neural network as the first attempt on a new problem with limited data

---

## The principle

Every model is a hypothesis about how the world works. Choosing a model is not a technical decision — it is an epistemological one. You are saying: "I believe the world follows this mathematical structure, and I am willing to be wrong about it."

The best practitioners hold their hypothesis lightly. They start simple, check if the hypothesis fits the data, and only add complexity when the evidence demands it.

The hypothesis, loss, and optimization trinity is the master key. If you understand these three for any algorithm, you understand that algorithm at its core. If you cannot state all three, you don't understand it yet.
