# CI/CD

> Automating build, test and deployment with pipelines such as GitHub Actions and Jenkins.
> Category: DevOps & Cloud. Typical effort: about 5 study days.

## CI/CD concepts

- **Continuous integration** — merging and testing code frequently.
- **Continuous delivery** — keeping software always ready to release.
- **Pipeline** — automated sequence of build and test stages.

Practice: Sketch the pipeline stages for one of your own projects.

## First workflow

- **Workflow** — YAML file describing an automated process.
- **Job** — group of steps that run on one runner.
- **Trigger** — event such as push that starts a workflow.

Practice: Write a workflow that runs your tests on every push.

## Artifacts, secrets and deployment

- **Artifact** — file produced by a build and kept for later steps.
- **Secret** — encrypted variable such as an API key.
- **Deployment stage** — pipeline step that releases the build.

Practice: Store a secret and deploy to a test environment.

## Mini project

Create a GitHub Actions workflow that builds, tests and (optionally) containerizes a sample project on every push and pull request.
