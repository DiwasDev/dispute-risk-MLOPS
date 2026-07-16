# Reliability and SRE for ML Systems

## Core Principle

Reliability is not the absence of failure -- it is the ability to function correctly despite failures. ML systems are uniquely fragile because they fail silently: infrastructure stays healthy while predictions quietly degrade. SRE practices bring the rigor of reliability engineering to a domain where "the system is up" does not mean "the system is working."

## SLIs, SLOs, and SLAs

These three concepts form the foundation of reliability management. They are often confused but have distinct roles.

**SLI (Service Level Indicator)** is a quantitative measurement of service behavior. It is what you measure. Examples for ML systems:
- Prediction latency (p50, p95, p99).
- Prediction availability (fraction of requests that return a valid prediction, not an error).
- Model freshness (time since the serving model was last retrained).
- Feature freshness (time since feature values were last updated in the online store).
- Prediction quality (accuracy, precision, recall measured against ground truth when labels arrive).

**SLO (Service Level Objective)** is a target value for an SLI. It is what you aim for. Examples:
- p99 prediction latency < 200ms.
- Prediction availability > 99.9% over a 30-day window.
- Model freshness < 7 days.
- Feature freshness < 1 hour for real-time features.

SLOs should be achievable but ambitious. Set them based on user expectations and business requirements, not on what the system currently achieves. An SLO that is always met is too loose.

**SLA (Service Level Agreement)** is a contract with consequences. It is what you promise to external customers, with penalties (credits, refunds) if you fail. SLAs should always be looser than SLOs -- your internal target should be higher than what you promise externally. If your SLO is 99.9%, your SLA might be 99.5%.

## Error Budgets

An error budget is the allowed amount of unreliability over a time window. If your SLO is 99.9% availability over 30 days, your error budget is 0.1% of 30 days = approximately 43 minutes of downtime.

**How error budgets change engineering priorities:**
- **Budget is healthy (plenty remaining):** Ship features, deploy new models aggressively, run experiments. Velocity matters more than caution.
- **Budget is depleted (little remaining):** Freeze feature deployments, focus on reliability improvements, reduce deployment frequency, invest in automation and testing. Reliability matters more than velocity.
- **Budget is exhausted:** Stop all changes except reliability fixes. Investigate what consumed the budget. Implement structural fixes before resuming normal development.

Error budgets align incentives. Product teams want to move fast; reliability teams want stability. The error budget gives both a shared number to optimize around.

## Toil Reduction

Toil is manual, repetitive, automatable work that scales linearly with service growth. Common ML toil:
- Manually retraining models on a schedule.
- Manually checking prediction quality dashboards.
- Manually investigating drift alerts that are almost always false positives.
- Manually promoting models through staging to production.
- Manually provisioning GPU instances for training jobs.

**Target:** Toil should consume no more than 50% of an SRE team's time. The rest should go to engineering work that permanently reduces future toil.

**Reduction strategies:** Automate retraining with evaluation gates. Automate model promotion with quality checks. Self-tune drift alert thresholds based on historical false positive rates. Use infrastructure-as-code for provisioning.

## Incident Management

### Severity Levels

Define severity levels before incidents happen. During an incident is too late to debate whether it is critical.

- **SEV-1 (Critical):** Production predictions are wrong or unavailable for all users. Business impact is immediate and significant. Response: page on-call, assemble incident response team, communicate to stakeholders within 15 minutes.
- **SEV-2 (Major):** Predictions degraded for a subset of users or a specific model. Business impact is measurable but contained. Response: page on-call, investigate immediately, communicate within 1 hour.
- **SEV-3 (Minor):** Monitoring detects drift or quality degradation, but user impact is not yet visible. Response: investigate during business hours, track in incident system.
- **SEV-4 (Low):** Cosmetic issues, dashboard errors, non-critical pipeline delays. Response: add to backlog, fix in normal sprint cadence.

### On-Call

- Rotate on-call across the team. No one should be on-call more than one week per month.
- Provide a runbook for every alerting rule. The on-call engineer should not need tribal knowledge to respond.
- Track on-call burden metrics: pages per shift, time to acknowledge, false positive rate.
- If on-call burden is consistently high, the system needs reliability investment, not more resilient humans.

### Postmortems

After every SEV-1 and SEV-2 incident, write a blameless postmortem. The structure:
1. **Summary:** What happened, who was affected, how long.
2. **Timeline:** Detailed sequence of events with timestamps.
3. **Root cause:** Not "human error" -- the systemic reason the error was possible.
4. **Impact:** Quantified business and user impact.
5. **Action items:** Concrete, assigned, with deadlines. Each action item should prevent this specific failure class from recurring.

Review postmortems in a team meeting. The goal is learning, not blame.

## Chaos Engineering

Chaos engineering probes the system's resilience by injecting controlled failures in non-production (or carefully in production) environments.

**Principles:**
- Start with a hypothesis: "If the feature store becomes unavailable, prediction latency should increase but predictions should still be served using cached features."
- Inject the smallest failure that tests the hypothesis.
- Monitor the system during the experiment.
- Stop immediately if the blast radius exceeds expectations.

**ML-specific chaos experiments:**
- Kill the feature store. Do predictions fall back to cached features or default values?
- Inject stale model artifacts. Does the serving system detect the staleness?
- Corrupt incoming feature data. Does data validation catch it before the model?
- Slow down model inference. Does the auto-scaler respond in time?
- Drop prediction logging. Does the monitoring system detect the gap?

## Circuit Breakers and Bulkheads

**Circuit breakers** prevent a failing dependency from bringing down the caller. When calls to a service fail repeatedly, the circuit opens and subsequent calls fail immediately without attempting the call. After a timeout, the circuit half-opens and allows a test request through. If it succeeds, the circuit closes.

**For ML systems:** Put a circuit breaker between the prediction endpoint and the feature store. If the feature store is down, fail fast and return a degraded prediction (cached features, default values) instead of timing out on every request.

**Bulkheads** isolate failure domains. Dedicate separate thread pools or connection pools to different dependencies. If the feature store connection pool is exhausted, it does not affect connections to the model registry.

## Graceful Degradation Patterns

Design your ML system to degrade gracefully rather than fail completely:

- **Feature unavailable:** Use cached feature values. If no cache, use population-level defaults. Log the degradation.
- **Model unavailable:** Fall back to a simpler model (logistic regression backup for a complex ensemble). If no backup model, return a rule-based default.
- **Partial feature set:** Some features are available, others are not. Serve predictions using available features with a lower confidence flag.
- **High latency:** Shed load by returning cached predictions for repeat requests. Reduce batch size for batch predictions.

Always log when degraded mode is active. A system stuck in degraded mode without anyone noticing is a silent failure.

## Health Check Design

**Liveness probe:** "Is the process alive?" A simple HTTP 200 response. If this fails, the orchestrator (Kubernetes) restarts the container. Should not check dependencies -- a slow database should not cause a restart loop.

**Readiness probe:** "Can this instance serve traffic?" Checks that the model is loaded, the feature store connection is healthy, and warm-up is complete. If this fails, the load balancer stops routing traffic to this instance but does not restart it.

**Startup probe:** "Has the instance finished initializing?" Allows a longer timeout for model loading and cache warming. Prevents the liveness probe from killing a container that is still loading a large model.

**ML-specific health checks:** Verify the loaded model version matches the expected version. Run a golden input through the model and verify the output matches the expected value.

## Disaster Recovery

**RPO (Recovery Point Objective):** How much data loss is acceptable. If your RPO is 1 hour, you need backups or replication that is no more than 1 hour old. For model registries: RPO should be near zero (synchronous replication). For prediction logs: RPO of hours is usually acceptable.

**RTO (Recovery Time Objective):** How quickly the system must be restored. If your RTO is 30 minutes, your recovery procedures must complete within that window. Practice recovery procedures regularly -- an untested recovery plan is not a plan.

## Multi-Region Patterns

- **Active-passive:** One region serves traffic, the other is a standby. Simple but wastes the standby's capacity. RTO depends on failover time (minutes to hours).
- **Active-active:** Both regions serve traffic. Complex because you must handle data consistency across regions. Near-zero RTO but requires careful conflict resolution.
- **For ML serving:** Active-passive is usually sufficient. Model artifacts are replicated to the standby region. Failover switches DNS to the standby's load balancer. Feature stores need cross-region replication with acceptable staleness.

## When to Use This

- Defining reliability targets for a new ML system before launch.
- An ML system is experiencing frequent incidents and needs structured reliability improvement.
- Setting up on-call and incident management for an ML platform team.
- Planning disaster recovery for production ML serving infrastructure.
- Justifying reliability investment to leadership with error budget data.

## Red Flags to Watch For

- No SLOs defined for ML-specific indicators like model freshness or prediction quality.
- Error budgets exist on paper but do not actually influence deployment decisions.
- On-call engineers are paged for alerts that have no runbook and require deep tribal knowledge.
- Postmortems blame individuals instead of identifying systemic causes.
- No graceful degradation path when the feature store or model becomes unavailable -- the system fails completely.
- Health checks only verify that the container is alive, not that the model is loaded and serving correctly.
- Disaster recovery plan exists but has never been tested end-to-end.
- Circuit breakers are not configured on calls to external dependencies, allowing cascading failures.
