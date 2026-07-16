# Tooling References -- Contributor Guide

This directory contains framework-specific implementation guides for the mlops-tabular skill. Each subdirectory covers one orchestration/pipeline framework and provides the concrete patterns an AI agent needs to generate working code.

## Current Frameworks

- `zenml/` -- ZenML step/pipeline patterns, stack setup, Model Control Plane, enterprise patterns

## Adding a New Framework

To add support for a new framework (Prefect, Airflow, Kubeflow, etc.), create a new subdirectory and populate it with the following files:

### Required Files

1. **`step-and-pipeline-patterns.md`** -- How to define tasks/steps/operators and compose them into pipelines/flows/DAGs. Include decorator syntax, type annotations, data passing between tasks, caching behavior, and project structure conventions.

2. **`stack-setup.md`** -- How to configure the framework's infrastructure. Local setup, adding integrations (experiment tracking, data validation), cloud deployment targets, and common configuration patterns.

3. **`model-control-plane.md`** (or equivalent) -- How the framework handles model versioning, model registry, promotion between stages, rollback, and loading models by stage for inference. If the framework does not have a built-in model registry, document the recommended external registry (MLflow Model Registry, SageMaker Model Registry, etc.) and how to integrate it.

4. **`enterprise-patterns.md`** -- Governance, validation gates, environment-specific configs, multi-environment promotion, Docker/container management, and CI/CD integration patterns.

### File Format

Each file should:
- Start with a `# Title` heading
- Be 1000-2000 words
- Target an AI coding agent as the reader (not a human tutorial)
- Include concrete code snippets and patterns
- Include a "Decision Guidance" section at the end with opinionated recommendations
- Avoid duplicating capability-level content (what to do); focus on implementation (how to do it with this specific framework)

### Patterns to Cover

For each framework, ensure the references answer these questions:
- How do I define a reusable processing unit (step/task/operator)?
- How do I pass data between processing units without shared filesystems?
- How do I configure the pipeline differently per environment?
- How do I track experiments and log metrics?
- How do I version and promote models?
- How do I add governance (validation, alerting, compliance) without mixing it into ML code?
- How do I run this on cloud infrastructure?

### Naming Convention

Use the framework name in lowercase as the subdirectory name: `prefect/`, `airflow/`, `kubeflow/`, `dagster/`. Keep filenames consistent across frameworks so the skill can reference them generically.
