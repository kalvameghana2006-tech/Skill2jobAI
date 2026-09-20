# Microservices

> Splitting applications into independently deployable services that communicate over APIs or messages.
> Category: Backend. Typical effort: about 8 study days.

## Monolith vs microservices

- **Monolith** — single deployable unit.
- **Microservice** — small independently deployable service around one capability.
- **Bounded context** — boundary within which a model is consistent.

Practice: Draw the services for an e-commerce app.

## Communication and gateways

- **API gateway** — single entry point routing to services.
- **Service discovery** — finding service instances dynamically.
- **Circuit breaker** — stops calling a failing service to avoid cascading failures.

Practice: Add a gateway in front of two services.

## Mini project

Split a sample monolith into two or three services with their own data stores, communicating over REST, with a Docker Compose file.
