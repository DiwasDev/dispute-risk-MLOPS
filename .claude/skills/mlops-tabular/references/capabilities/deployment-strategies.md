# Deployment Strategies

Deployment patterns determine how safely and quickly you ship model changes to production. The right pattern manages user risk, engineer stress, and iteration velocity. A great model behind a reckless deployment is worse than a decent model behind a safe one.

## Batch vs Online Serving

Before choosing a deployment pattern, decide the serving mode.

### Batch Serving

Precompute predictions on a schedule and store them for later lookup. Examples: overnight video recommendations, weekly demand forecasts, nightly risk scores.

**Choose batch when:**
- Inputs are known well before the decision point.
- Staleness of hours or days is acceptable.
- Workload is heavy and predictable.
- Simplicity and cost matter more than freshness.

### Online Serving

Compute predictions on demand per request. Examples: real-time fraud scoring, personalized search ranking, live ETA estimation.

**Choose online when:**
- Inputs arrive at decision time (context-sensitive, personalized).
- Delays are unacceptable (sub-second requirements).
- The feature space changes too fast for precomputation.

### Hybrid Approach

Many production systems combine both. Batch precomputes heavy features or baseline predictions; online applies lightweight adjustments using live signals. This balances latency, cost, and freshness.

## Deployment Patterns

### Shadow Testing

Run the new model in parallel with production without affecting users. Log its predictions alongside the live model's predictions and compare against ground truth when available.

**When to use:**
- High-risk domains where a bad prediction causes real harm (finance, healthcare, safety).
- New model architectures or feature sets that are fundamentally different.
- When labels arrive late and you need time to collect comparison data.

**How it works:**
- Every request goes to both old and new models.
- Only the old model's prediction is served to users -- zero user risk.
- New model predictions are logged for offline analysis.
- Compare prediction distributions, disagreement rates, and eventual accuracy on labeled data.
- Shadow testing answers: "Would this model have performed better if we had deployed it?" without exposing users to any risk.

**Duration:** Typically one to four weeks depending on label delay and traffic volume.

### Canary Deployments

Route a small percentage of live traffic (typically 1-5%) to the new model while the rest continues using the current model. Monitor outcomes on the canary slice before expanding.

**When to use:**
- Standard model updates where you have reasonable offline confidence.
- When you want to catch catastrophic failures before they hit all users.
- As the step between shadow testing and full rollout.

**How it works:**
- Deploy new model alongside current model.
- Route a small, representative traffic slice to the new model.
- Monitor business metrics, guardrails (latency, error rate), and prediction distributions on the canary slice.
- If healthy, gradually ramp up following a conservative progression: **1% → 5% → 10% → 25% → 50% → 100%**.
- Each ramp step needs enough time to observe outcomes (hours to days depending on label delay).
- If unhealthy at any stage, roll back immediately.

**Key decisions:**
- Canary slice selection: should be representative, not biased toward easy traffic.
- Ramp schedule: each step needs enough time to observe outcomes (hours to days depending on label delay).
- Stop criteria: pre-define what triggers rollback (error rate spike, latency breach, business metric drop beyond threshold).

### Blue-Green Deployments

Maintain two identical serving environments. Blue is live; green hosts the new model. When ready, flip the traffic router from blue to green. Rollback is instant by flipping back.

**When to use:**
- When you need zero-downtime deployments.
- When instant rollback capability is critical.
- For infrastructure changes alongside model changes.

**How it works:**
- Green environment is fully provisioned and tested before any traffic switch.
- Health checks and golden input tests pass on green before the flip.
- Traffic router switches all traffic atomically.
- Blue remains warm for immediate rollback.

**Trade-off:** Requires double infrastructure during the transition. Simpler operationally than canary but without gradual risk reduction.

### A/B Testing Deployments

Split traffic between control (current model) and treatment (new model) with statistical rigor to measure causal impact on business metrics.

**When to use:**
- When you need statistical evidence that the new model improves outcomes.
- For product-facing changes where business impact justification is required.
- When offline metrics and online outcomes historically diverge.

**How it works:**
- Randomize users (not requests) into control and treatment groups.
- Run for the duration determined by power analysis.
- Measure primary metric and guardrails.
- Ship if statistically significant improvement with no guardrail violations.

**Distinction from canary:** Canary is about safety (catch failures fast). A/B testing is about measurement (prove improvement). Often used sequentially: canary first to confirm safety, then A/B test to measure impact.

### Multi-Armed Bandit

Dynamically allocate traffic to the better-performing model variant, reducing exposure to worse variants over time.

**When to use:**
- When minimizing regret (lost revenue during testing) matters more than clean statistical measurement.
- For content recommendations or ad ranking where many variants compete.
- When you are comfortable with weaker causal claims.

**Trade-off:** Faster convergence to the better variant but harder to get rigorous confidence intervals. Not a replacement for A/B testing when you need defensible causal evidence.

## Traffic Management

### Routing Decisions

- Route by user ID hash for consistency (same user always sees same variant).
- Avoid routing by request or session, which creates inconsistent user experiences.
- Ensure canary/treatment slices are demographically representative.
- Exclude bot traffic and internal traffic from experiment populations.

### Warmup and Cold Start

- New model deployments start with cold caches and uninitialized state.
- Warm up by replaying recent traffic before routing live users.
- Cache features and results aggressively; use stale-while-revalidate for freshness.
- Monitor p95 and p99 latency during the first minutes after deployment.

### Training-Serving Parity

- The serving path must use identical feature transformations as training.
- Save all transformers (encoders, scalers, tokenizers) as versioned artifacts alongside the model.
- Run golden input tests (fixed examples with known expected outputs) on every deploy.
- Block promotion if golden input outputs change unexpectedly.

## Rollback Strategies

Rollback is a feature, not an emergency procedure. Design for it from day one.

### Principles

- Every deployment must have a known rollback path before it starts.
- Rollback should be a single action: promote the last stable model version.
- Rollback includes an explanation entry in the change log.
- After rollback, the investigation begins -- not before.
- Keep the previous model warm and ready at all times.

### Rollback Triggers

- Business metric drops beyond pre-defined threshold.
- Guardrail metric breaches (latency, error rate, safety).
- Prediction distribution collapses or shifts dramatically.
- Golden input test failures.
- Data validation failures on incoming traffic.

### Rollback Speed

- Blue-green: instant (flip router back).
- Canary: fast (stop routing to canary, all traffic returns to stable).
- Full deployment: minutes (redeploy previous artifact version from registry).
- Target: rollback should complete in under five minutes for any pattern.

## Observability During Rollout

Every deployment must be observable in real time:

- Business outcome trends (revenue, engagement, waste, complaints).
- Error rate and latency guardrails.
- Input and feature health (drift panels).
- Prediction distribution shape (histograms vs baseline).
- Slice-level views (region, device, user segment).
- Annotations on dashboards marking deploy times and config changes.

## Decision Framework: Choosing a Pattern

Ask these questions to pick the right deployment pattern:

1. **What decision does the model support?** High-stakes decisions need more caution (shadow first).
2. **When do inputs arrive?** Late inputs with cheap retry suggest online + aggressive canary. Early inputs with high risk suggest batch + blue-green + long shadow.
3. **What is the maximum acceptable latency?** This constrains batch vs online choice.
4. **What is the cost of a bad prediction?** Higher cost demands shadow testing and conservative canary ramps.
5. **Do you need statistical proof of improvement?** If yes, A/B test. If you just need safety, canary suffices.

## When to Use This

- **First production deployment**: Start with shadow testing, then canary, then full rollout.
- **Routine model updates**: Canary with pre-defined ramp schedule and automated rollback triggers.
- **Major model changes**: Shadow test for one to two weeks, canary at 1%, A/B test at scale, then promote.
- **High-stakes domains**: Always shadow test. Never go directly from offline evaluation to full traffic.

## Red Flags to Watch For

- **No rollback plan**: If you cannot roll back in under five minutes, you are not ready to deploy.
- **Skipping canary for speed**: "The offline metrics look great, let's just ship 100%" is how incidents happen.
- **Canary on unrepresentative traffic**: Routing only easy or low-stakes traffic to the canary defeats its purpose.
- **No golden input tests**: Without parity checks, training-serving skew goes undetected until users complain.
- **No pre-defined stop criteria**: Deciding rollback thresholds during an incident leads to slow, emotional decisions.
- **Ignoring latency during deployment**: A model that is more accurate but 3x slower will degrade user experience.
- **Double infrastructure costs without cleanup**: Blue-green requires decommissioning the old environment after stabilization.
- **Running A/B tests without power analysis**: Underpowered tests waste time and produce inconclusive results.
