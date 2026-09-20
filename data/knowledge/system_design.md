# System Design

> Designing scalable services: load balancing, caching, databases, queues and trade-offs.
> Category: CS Fundamentals. Typical effort: about 15 study days.

## Building blocks

- **Load balancer** — spreads requests across servers.
- **Cache** — fast storage for frequently read data.
- **CDN** — edge servers serving static content near users.

Practice: Draw the components of a simple web app.

## Scaling and trade-offs

- **Sharding** — splitting a database across machines.
- **CAP theorem** — a distributed system cannot guarantee consistency, availability and partition tolerance together.
- **Replication** — copying data to several nodes for availability.

Practice: Design a URL shortener end to end.

## Mini project

Write a design document for a URL shortener or chat app: requirements, API, data model, capacity estimate, scaling and trade-offs.
