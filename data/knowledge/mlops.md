# MLOps

> Packaging, deploying, versioning and monitoring ML models in production.
> Category: Data & ML. Typical effort: about 8 study days.

## ML lifecycle

- **Experiment tracking** — recording parameters and metrics of each run.
- **Model registry** — versioned store of trained models.
- **Reproducibility** — ability to recreate a result from code and data.

Practice: Track two runs with MLflow.

## Serving and monitoring

- **Model serving** — exposing a model through an API.
- **Data drift** — input data changing from what the model saw in training.
- **Canary release** — rolling out to a small share of traffic first.

Practice: Serve a model with FastAPI in Docker.

## Mini project

Package an ML model in a Docker container behind an API with MLflow tracking and a CI workflow that runs tests.
