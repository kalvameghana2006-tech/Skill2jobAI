# Kubernetes

> Orchestrating containers at scale with pods, deployments, services and autoscaling.
> Category: DevOps & Cloud. Typical effort: about 15 study days.

## Cluster concepts

- **Pod** — smallest deployable unit, one or more containers.
- **Node** — machine that runs pods.
- **Control plane** — components that manage the cluster state.

Practice: Start minikube and inspect nodes and system pods.

## Deployments and Services

- **Deployment** — manages replicas and rolling updates of pods.
- **Service** — stable network endpoint that load balances to pods.
- **kubectl apply** — creates or updates resources from YAML.

Practice: Deploy an app with 3 replicas and expose it with a Service.

## Configuration and storage

- **ConfigMap** — injects non-secret configuration.
- **Secret** — stores sensitive values such as passwords.
- **PersistentVolume** — storage that outlives pods.

Practice: Move settings to a ConfigMap and mount a volume.

## Operations

- **Readiness probe** — tells Kubernetes when a pod can receive traffic.
- **Rolling update** — replaces pods gradually with zero downtime.
- **HPA** — autoscaler that adds pods based on load.

Practice: Trigger a rolling update and roll it back.

## Mini project

Deploy a containerized app on a local cluster (minikube or kind) with a Deployment, Service, ConfigMap and readiness probe.
