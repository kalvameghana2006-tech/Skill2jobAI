# REST API

> Designing HTTP APIs with resources, verbs, status codes and JSON payloads.
> Category: Backend. Typical effort: about 4 study days.

## HTTP and REST basics

- **REST** — architectural style using resources addressed by URLs.
- **HTTP method** — verb such as GET or POST describing the action.
- **Stateless** — each request carries everything the server needs.

Practice: Use curl or Postman to call a public API and inspect headers and bodies.

## Methods and status codes

- **GET** — reads a resource without changing it.
- **POST** — creates a new resource.
- **201 Created** — returned after a resource is successfully created.
- **404 Not Found** — the requested resource does not exist.

Practice: Map CRUD operations to methods and pick the right status code for each case.

## Designing resources and JSON

- **Resource naming** — use nouns like /users/42 not verbs.
- **JSON** — text format used for request and response bodies.
- **Idempotent** — repeating the request leaves the same server state (PUT, DELETE).

Practice: Design the URL structure and JSON shapes for a small todo API.

## Build your first API

- **Controller** — code that receives requests and returns responses.
- **Request body** — data the client sends in POST or PUT.
- **Validation** — rejecting bad input with a 400 response.

Practice: Implement GET and POST endpoints in your framework of choice.

## Errors, pagination and versioning

- **Pagination** — returning large lists in pages using limit and offset.
- **API versioning** — keeping old clients working via /v1 style paths.
- **Error payload** — consistent JSON body describing what went wrong.

Practice: Add pagination, validation errors and a /v1 prefix.

## Mini project

Build a small REST service (users or todos) with GET, POST, PUT and DELETE endpoints, JSON validation and proper status codes.
