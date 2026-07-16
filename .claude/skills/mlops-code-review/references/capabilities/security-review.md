# Security Review for ML Systems

ML systems introduce security risks that do not exist in traditional software. They consume untrusted data at scale, serialize complex objects that can execute arbitrary code, and expose prediction endpoints that reveal information about training data. A security-aware code review catches these risks before they reach production. This reference covers the most critical security concerns for ML code, drawn from OWASP Top 10 for ML, OWASP Python Security, and CWE.

## Input Validation for ML Endpoints

ML endpoints accept feature vectors from external sources. Without validation, these endpoints are vulnerable to malformed inputs, adversarial inputs, and injection attacks.

**Schema validation**: Every prediction endpoint must validate input schema before passing data to the model. Verify column names, data types, and array shapes. Use Pydantic models or JSON Schema to define and enforce the expected input format. Reject requests that do not match the schema with clear error messages that do not reveal model internals.

**Range checks**: Validate that numerical features fall within expected ranges. A model trained on ages 18-90 should reject age=-5 or age=999. Define bounds based on training data distribution and reject or clip out-of-range values. Log anomalous inputs for monitoring.

**Adversarial input detection**: ML models are vulnerable to adversarial examples -- inputs crafted to produce incorrect predictions. For tabular models, this manifests as feature values at extreme but technically valid ranges. Monitor for inputs that cluster near decision boundaries or exhibit statistical properties unlike training data.

**Cardinality validation**: For categorical features, validate that values belong to the known vocabulary. Unknown categories should be handled explicitly (mapped to UNKNOWN bucket or rejected), never silently passed through.

## Secrets Management

Hardcoded secrets in ML code are especially common because data scientists often prototype with direct database connections, API keys for cloud services, and credentials for experiment tracking platforms.

**Never hardcode credentials**: No API keys, database passwords, cloud tokens, or service account keys in source code, configuration files, or notebooks. Use environment variables for simple cases and a secret manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager) for production.

**Review targets**: Search for patterns indicating hardcoded secrets: strings matching API key formats, variables named `password`, `secret`, `token`, `api_key`, `credentials` with string literal assignments, connection strings with embedded credentials.

**Notebook risk**: Jupyter notebooks frequently contain embedded credentials in cell outputs or markdown cells. Review notebooks for secrets in outputs, not just code cells. Use pre-commit hooks with secret detection (detect-secrets, gitleaks) to prevent commits.

**Model registry credentials**: Experiment tracking and model registry connections often use tokens. Ensure these are injected via environment variables, not stored in configuration files committed to git.

## Dependency Security

ML projects have deep dependency trees. A vulnerability in any dependency is a vulnerability in the system.

**Audit dependencies**: Run `pip-audit` or `safety check` regularly and in CI. These tools check installed packages against known vulnerability databases. Block deployments with unresolved critical vulnerabilities.

**Pin versions**: Unpinned dependencies change silently. A `requirements.txt` with `pandas>=1.0` can install any version. Use exact pins (`pandas==2.1.4`) and lockfiles for reproducible, auditable environments.

**Known risky packages**: Some packages have had significant vulnerabilities. Keep PyYAML updated (older versions allow arbitrary code execution via `yaml.load` without `Loader`). Use `yaml.safe_load` always. Audit any package that deserializes data.

**Supply chain attacks**: Verify package names carefully. Typosquatting (e.g., `scikit-leam` instead of `scikit-learn`) is a real attack vector. Use a private package index for internal packages.

## Serialization and Deserialization Risks

This is the single most critical security concern specific to ML systems.

**Pickle and joblib are arbitrary code execution vectors**: `pickle.load()` and `joblib.load()` execute arbitrary Python code embedded in the serialized file. Loading an untrusted pickle file is equivalent to running `exec()` on untrusted input. A malicious model file can install backdoors, exfiltrate data, or compromise the host.

**Review rules for deserialization**:
- Never load pickle/joblib files from untrusted sources (user uploads, unverified URLs, shared storage without integrity checks).
- Prefer safe serialization formats: ONNX for model export, JSON/YAML for configuration, Parquet for data.
- If pickle is necessary, verify file integrity with cryptographic hashes before loading. Store the hash alongside the model artifact in the model registry.
- Use `safetensors` for neural network weights instead of `torch.save`/`torch.load`.

**sklearn pipelines**: scikit-learn pipelines are serialized with pickle/joblib. This is standard practice but requires treating model artifacts as trusted code, not just data. Artifact storage must have access controls equivalent to code repositories.

## SQL Injection in Data Queries

ML pipelines frequently construct SQL queries to fetch training or serving data. String concatenation with user-provided or configuration-provided values creates injection risks.

**Parameterized queries always**: Never construct SQL by string formatting. Use parameterized queries or ORM query builders. Review any `f"SELECT ... WHERE {variable}"` pattern as a potential injection.

**Configuration-driven queries**: Even when query parameters come from configuration files (not user input), use parameterized queries. Configuration files can be modified, and the habit of parameterization prevents vulnerabilities when the data source changes.

## Model Extraction and Privacy Attacks

Prediction endpoints can leak information about training data and model internals.

**Model extraction**: An attacker queries the prediction endpoint systematically to build a copy of the model. Mitigation: rate limiting, monitoring for unusual query patterns (grid-like inputs, high volume from single source), returning confidence scores with limited precision.

**Membership inference**: An attacker determines whether a specific data point was in the training set by analyzing prediction confidence. Mitigation: calibrate prediction confidence, avoid returning raw probabilities with excessive precision, consider differential privacy during training for sensitive data.

**Data poisoning detection**: Training data from external sources can be manipulated to influence model behavior. Review data pipelines for integrity checks: row counts, schema validation, distribution statistics compared against historical baselines. Flag sudden changes in data characteristics.

## Secure Model Serving

**Authentication**: Every prediction endpoint must require authentication. No anonymous access to model predictions. Use API keys, OAuth tokens, or service-to-service authentication.

**Rate limiting**: Protect against denial-of-service and model extraction. Implement per-client rate limits. Log and alert on unusual request patterns.

**Input sanitization**: Beyond schema validation, sanitize string inputs to prevent log injection. A feature value of `\n[ERROR] fake log entry` should not appear as a real log line.

**Response filtering**: Do not return internal model details (feature importances, tree structures, weight values) in production responses unless explicitly required and access-controlled.

**HTTPS only**: All model endpoints must use TLS. Feature vectors and predictions are sensitive data.

## Logging Sensitive Data

ML systems process data that may contain PII. Logging must be reviewed for data leakage.

**Do not log feature values**: Feature vectors may contain PII (age, income, location). Log prediction metadata (request ID, timestamp, model version, latency) but not input features or raw predictions. If feature logging is needed for monitoring, aggregate statistics rather than individual values.

**Error messages**: Exception handlers that log the full input on failure will log PII. Sanitize error logs to remove feature values. Log the schema and shape, not the content.

**Experiment tracking**: MLflow, W&B, and similar tools log parameters, metrics, and artifacts. Ensure training data samples, feature distributions, or individual predictions logged during experiments do not contain PII.

## When to Use This

- During code review of any ML endpoint or serving infrastructure.
- When reviewing data pipeline code that connects to databases or external APIs.
- When reviewing model serialization and deserialization code.
- When a new dependency is added to the ML project.
- When reviewing notebook code before productionization.
- Before deploying a model to a public-facing endpoint.

## Red Flags to Watch For

- `pickle.load()` or `joblib.load()` on files from untrusted or unverified sources.
- Hardcoded strings matching API key or password patterns anywhere in the codebase.
- SQL queries constructed with f-strings or string concatenation.
- `yaml.load()` without `Loader=SafeLoader` -- allows arbitrary code execution.
- Prediction endpoints without authentication or rate limiting.
- Feature values logged in plain text in error handlers or monitoring code.
- No dependency vulnerability scanning in the CI pipeline.
- Model artifacts stored in world-readable locations without integrity verification.
- Unpinned dependencies in requirements files.
- `eval()` or `exec()` on any user-provided or configuration-provided string.
