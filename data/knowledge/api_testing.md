# API Testing

> Validating REST endpoints, status codes and payloads with Postman or REST Assured.
> Category: Testing & QA. Typical effort: about 3 study days.

## API testing basics

- **Endpoint** — URL exposing an operation.
- **Status code** — number summarising the outcome of a request.
- **Payload** — data sent or received in the body.

Practice: Call a public API in Postman and inspect the response.

## Assertions and automation

- **Assertion** — automated check on a response.
- **Environment variable** — value reused across requests such as a base URL.
- **Negative test** — intentionally invalid input to prove errors are handled.

Practice: Write assertions for status, body fields and response time.

## Mini project

Create a Postman collection (or REST Assured suite) with 15 requests covering status codes, schema checks, auth and negative cases, with environment variables.
