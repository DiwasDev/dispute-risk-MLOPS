# Incident Response and Alerting

Shipping a model is the beginning of a feedback loop, not the end. Without monitoring, alerts, and incident response processes, models quietly degrade while users suffer. The goal is observability that supports calm, fast decisions rather than panic.

## The Monitoring Ladder

Organize monitoring in layers, read top-down for impact and bottom-up for root cause:

1. **Business outcomes** (top): Revenue, safety, waste reduced, user retention. Does the change help users?
2. **Product metrics**: Minutes watched, complaint rate, conversion rate. How is the experience changing?
3. **Model metrics**: Precision, recall, MAE, calibration. Is the model performing as expected?
4. **Data and feature health** (base): Input distributions, feature statistics, prediction distributions. What changed underneath?

When something breaks, start at the top (what is the user impact?) and drill down (what caused it?). When investigating proactively, start at the bottom (what shifted?) and look up (is it affecting users?).

## Alert Design

### Principles

Good alerts wake the right person once with enough context to act. Bad alerts train people to ignore them.

- **Tie alerts to clear symptoms**: "Feature X median shifted 3 standard deviations from baseline" is actionable. "Something might be wrong" is not.
- **Route to owners who can fix the cause**: Schema errors go to the data producer. Drift spikes go to the feature author. Latency issues go to the serving owner. Business metric shifts go to the product owner.
- **Include dashboard and runbook links**: Every alert should link to the relevant dashboard and the runbook entry for that alert type.
- **Throttle repeats**: Alert once, then suppress duplicates for a cooldown window. Repeated identical alerts get muted and ignored.

### Severity Classification

**Critical (page immediately):**
- Model serving is down or returning errors above threshold.
- Golden input tests failing (training-serving parity broken).
- Business metric dropped beyond catastrophic threshold.
- Data pipeline completely stopped (no new inputs arriving).

**High (respond within hours):**
- Prediction distribution collapsed or shifted significantly.
- Feature drift beyond warning bounds on multiple features.
- Latency p99 breached SLA for sustained period.
- Guardrail metric degraded beyond threshold.

**Medium (respond within one business day):**
- Single feature drift beyond bounds.
- Minor increase in unknown/default category rates.
- Slow upward trend in error rate.
- Model staleness approaching retraining deadline.

**Low (review in weekly triage):**
- Small persistent shifts in input distributions.
- Slight calibration drift.
- Non-critical slice performance dip.
- Infrastructure cost increase without performance change.

### Alert Tuning

Alerts degrade over time. Review and tune them regularly:

- Track alert-to-action ratio. If fewer than half of alerts lead to an action, thresholds are too sensitive.
- Remove alerts that have never fired or always fire.
- Adjust thresholds after seasonal patterns are understood.
- Add new alerts when incidents reveal unmonitored failure modes.
- Review alert routing quarterly to match current team ownership.

## What to Monitor

### Prediction Distributions

The fastest signal before ground truth arrives. Track the shape of model output distributions:

- Collapse to the middle indicates uncertainty or feature breakage.
- Extreme jumps suggest leakage or input shifts.
- Slice-level drift (e.g., predictions shifting for one region but not others) reveals localized issues.
- Compare histograms against the previous week. Plot by slice.

### Feature Health

Track statistics for key features in production:

- Mean, standard deviation, missingness rate, sparsity, valid range.
- Feature shifts reveal silent failures beyond raw input changes.
- Example: a tokenizer update that shrinks vocabulary coverage, or a geohash precision change.

### Raw Input Health

The first gate before anything else:

- Confirm required fields are present.
- Verify numeric ranges and units.
- Monitor time field sanity and timezones.
- Track unknown category rates.
- Detect upstream product or third-party API changes early.

### Accuracy When Labels Are Delayed

Ground truth often arrives days or weeks after predictions. Strategies:

- Use proxy metrics that correlate with quality: manual review overturn rate, skip rate, recalibration error.
- Reconcile with actual ground truth on a longer schedule.
- Write policy to balance overreaction to proxies vs ignoring real smoke signals.
- Show both operational windows (short, proxy-based) and truth windows (long, label-based) on dashboards.

### Latency, Throughput, and Stability

- Track p50, p95, p99 response times.
- Measure queue depths and concurrent request counts.
- Monitor error and retry rates.
- Distinguish algorithmic issues (model too slow) from infrastructure issues (node overloaded).

## Slices Over Averages

Averages hide segment-level suffering. Always analyze metrics by key slices:

- Region, device type, network quality, time of day, user cohort.
- Catch patterns like degraded performance on old Android devices in the morning, or failures after rain in one region.
- Per-slice dashboards should be the default view, not a drill-down.

## Incident Response Playbooks

### Purpose

Runbooks make incidents boring and predictable. They list what to check, who decides, and how to act so that the on-call person does not need to invent a process during a crisis.

### First Hour Triage

1. **Confirm system health**: Is the serving infrastructure up? Are requests being processed?
2. **Check drift panels and risky slices**: Has input, feature, or prediction distribution changed?
3. **Verify parity with golden examples**: Run golden inputs through the serving path. Do outputs match expected values?
4. **Annotate changes**: Mark timeline with recent deploys, config changes, upstream data changes.
5. **Decide action**: Continue monitoring, adjust thresholds, or roll back.

### Escalation

- If the issue is confirmed and impacting users, escalate to the model owner and product owner within 30 minutes.
- If rollback is needed, the on-call has authority to execute without waiting for approval.
- If root cause is unclear after one hour, pull in the data producer and feature author.

### Response Actions (In Order of Severity)

**Rollback**: Promote the last stable model version. This is the fastest way to stop user harm. Always prefer rollback over debugging in production.

**Threshold adjustment**: If the model is fundamentally sound but calibration has shifted, adjust decision thresholds within pre-approved bands. Document the change and schedule follow-up.

**Recalibration**: Apply calibration correction using recent data. Less disruptive than retraining but requires monitoring to confirm the fix holds.

**Retraining**: Options include patch retrain (recent data only), full refresh, or rolling window update. Keep the previous model warm and ready. Verify the fix with shadow testing or canary before promoting.

### Post-Incident: Root Cause Analysis

Every significant incident gets a written RCA. The goal is learning, not blame.

**RCA structure:**
- **Timeline**: What happened, when, in what order. Include detection time, response time, and resolution time.
- **Impact**: What users were affected, for how long, and what was the business cost.
- **Root cause**: The actual underlying cause, not just the trigger. "Data pipeline delivered mixed units" not "model accuracy dropped."
- **Detection gap**: How long between the issue starting and the alert firing? Why?
- **Contributing factors**: What made the issue worse or harder to detect?
- **Action items**: Concrete, assignable tasks to prevent recurrence. Each must have an owner and deadline.

### Postmortems

Postmortems are the team ritual built on RCAs. Run them within one week of the incident.

**Key principles:**
- Blameless: Focus on systems and processes, not individuals.
- Honest: Acknowledge what was missed and why.
- Actionable: Every postmortem produces specific, tracked follow-up items.
- Shared: Publish postmortems where the whole team can read and learn from them.

**Common action items from ML postmortems:**
- Add monitoring for the failure mode that was undetected.
- Tighten schema validation on the input that caused the issue.
- Add the scenario to golden input test suite.
- Update the runbook with the new triage path.
- Adjust alert thresholds based on what was learned.

## Prevention: Designing for Resilience

### Shift-Resistant Features

- Prefer causal features over brittle proxies.
- Handle unseen categories gracefully (safe "unknown" bucket, not crash).
- Avoid relying on fast-changing IDs unless continuously updated.
- Include exploration policy for new data regions to avoid blind spots.

### Data Contracts

- Agree on schemas, units, timezones, and valid ranges with data producers.
- Require version changes for breaking updates.
- Annotate dashboards when upstream changes occur.
- Contracts make otherwise hidden changes visible and debuggable.

### Feedback Loop Awareness

Product decisions bias the data you observe. Recommenders reinforce popular items. Risk models block borderline cases and hide their outcomes. This is not a theoretical concern -- it is the most dangerous form of silent failure in production ML.

**The self-fulfilling prophecy pattern:** A lending model rejects applicants from certain neighborhoods. Because those applicants are rejected, there is no outcome data (would they have repaid?). The next training cycle sees zero positive outcomes from those neighborhoods, reinforcing the rejection bias. The model's predictions literally shape the training data, creating a discriminatory cycle that looks correct by the model's own metrics.

**Guardrails:**
- Allocate traffic to exploration policies to preserve learning -- reserve a percentage of decisions for random or rule-based processing.
- Log counterfactual predictions to enable offline evaluation of alternative policies.
- Run periodic backtests simulating different policies to detect echo chambers.
- Monitor decision diversity over time -- if the model's decisions are becoming increasingly concentrated, investigate.
- Audit across demographic slices periodically, even when overall metrics look healthy.

## When to Use This

- **Before first production launch**: Set up the monitoring ladder, write runbooks, define alert routing and severity levels.
- **After any incident**: Run RCA, write postmortem, update runbooks and alerts.
- **During weekly triage**: Review low-severity alerts, tune thresholds, verify ownership routing is current.
- **When onboarding new team members**: Walk them through runbooks, alert routing, and escalation paths.

## Red Flags to Watch For

- **No runbook exists**: If the on-call has to figure out what to do during an incident, response will be slow and inconsistent.
- **Alerts without owners**: Unrouted alerts get ignored. Every alert must reach someone who can fix the root cause.
- **Alert fatigue**: If the team mutes or ignores alerts, thresholds are wrong or alerts are poorly designed. Fix them.
- **No postmortem culture**: Repeated incidents without RCAs mean the same failures will recur.
- **Monitoring only global averages**: Slice-level issues hide under healthy-looking averages.
- **No golden input tests**: Training-serving parity breaks silently. Golden inputs catch it on every deploy.
- **Rollback takes more than five minutes**: If rollback is slow or manual, incidents last longer than they should.
- **Blame-oriented incident reviews**: Blame drives hiding, not learning. Blameless postmortems are non-negotiable.
