# Problem Framing Skill

## Settings
```
PROBLEM_COMPLEXITY = 5       # How ambiguous is the business ask?
                             # 1-3: Clear metric, clear target variable
                             # 4-7: Multiple possible framings worth considering
                             # 8-10: Business goal vague — needs deep questioning first

STAKEHOLDER_LEVEL = 5        # Who are you building for?
                             # 1-3: Non-technical (executive, ops manager)
                             # 4-7: Semi-technical (PM, analyst)
                             # 8-10: Technical (engineer, data scientist)

DEPLOYMENT_CONTEXT = 5       # Where does this end up?
                             # 1-3: Research / exploration notebook
                             # 4-7: Internal dashboard or tool
                             # 8-10: Customer-facing production system
```

---

## What this prevents

When a student says "predict churn," the AI builds a binary classifier. Immediately. No questions asked.

But maybe the sales team doesn't need yes/no. They need a ranked list of who to call first this week. That's a ranking problem — different model, different loss function, different evaluation metric, completely different business outcome.

The AI solved the wrong problem perfectly. This skill prevents that.

---

## Core rule: NEVER touch data before answering these 4 questions

**Q1. What decision will be made using this prediction?**
Not "what are we predicting" — what action does someone take based on the output?
- "Send a discount coupon" → need a probability, not just yes/no
- "Call the customer" → need a ranked list, not a classifier
- "Set inventory levels" → need a number with confidence interval

**Q2. What output format does the decision-maker actually need?**
- A single number (regression)
- A yes/no (binary classification)
- A probability 0–1 (probabilistic classification)
- A ranked list (ranking)
- A time estimate (survival analysis / time-to-event)
- A category from many options (multi-class classification)

**Q3. What counts as success — in the stakeholder's language?**
Not "accuracy > 0.85." Yes: "Sales team closes 20% more at-risk accounts."

**Q4. Is there a simpler non-ML baseline we should compare against?**
Would a simple rule (IF purchase_gap > 60 days THEN at_risk) get 80% of the way?

---

## The framing decision tree

```
Business question received
         │
         ▼
What action does the output trigger?
         │
    ┌────┴────────────────┐
    │                     │
Rank/sort            Threshold or quantity decision
(who first?)              │
    │              ┌──────┴──────┐
Ranking        Does timing    How much / when?
model           matter?            │
               │       │     Is relationship linear?
             Yes:      No:        │            │
           Survival  Binary   Regression  Tree/Network
           analysis  classifier
```

---

## Common reframings to surface

| Student says | Default AI builds | What to ask first |
|---|---|---|
| "Predict churn" | Binary classifier | "Do they need a flag or a ranked call list?" |
| "Predict revenue" | Exact number regression | "Do they need exact or just 'above quota or not'?" |
| "Set the price" | Regression on price | "Are you setting a price or modeling demand at each price?" |
| "Detect fraud" | Binary classifier | "Is a false positive (blocking legit user) worse than a miss?" |
| "Recommend products" | Classifier | "Ranking items for a user, or picking the single best one?" |
| "Forecast demand" | Regression | "Exact units, or just 'more vs less than usual'?" |

---

## Prompt templates

### Before any project
```
Before we write any code, let's frame this correctly.

Business goal: [what the organization wants to achieve]

Answer these:
1. What decision will be made from this prediction?
2. What output format does the decision-maker need?
   (number / yes-no / probability / ranked list / time-to-event)
3. What does success look like in plain language for the stakeholder?
4. What is the simplest non-ML baseline we should define and beat?

Based on my answers, recommend the best problem framing and explain
why it beats the obvious default.
```

### When you have a framing in mind
```
I'm considering framing this as [classification / regression / ranking].

Context:
- Goal: [...]
- Decision-maker needs: [...]
- They will act by: [...]

Evaluate:
1. Is this the right ML type?
2. What am I giving up with this framing?
3. What alternative framings should I consider?
4. What changes downstream if I pick a different framing?
   (loss function, evaluation metric, model choice)
```

### Translating a vague ask
```
My stakeholder said: "[exact quote]"

Translate into a precise ML problem:
1. What are 2–3 possible ML framings for this ask?
2. For each: target variable, feature set, output format
3. Which framing is most actionable given the decision-maker is [role]?
4. What one clarifying question should I ask before starting?
```

---

## Anti-patterns

- Never start with "let me load the data" before framing is confirmed
- Never default to binary classification for every business problem
- Never choose the model before choosing the framing
- Never evaluate with a metric before knowing the business success criterion
- Never build a regression when the stakeholder only needs "above threshold or below"
- Never assume the training label is obvious — confirm what the target variable actually measures

---

## The principle

The model will solve exactly the problem you give it. If you give it the wrong problem framed the wrong way, it will solve the wrong problem perfectly.

Problem framing is the highest-leverage decision in any ML project. It happens before you touch data or code. The framing determines the model, the loss function, the evaluation metric, and ultimately whether the project creates business value.
