# FastAPI

> Modern async Python framework for typed, documented REST APIs.
> Category: Backend. Typical effort: about 4 study days.

## Path operations

- **Path operation** — function bound to an HTTP method and path.
- **Path parameter** — value taken from the URL.
- **Query parameter** — optional value after the question mark.

Practice: Create GET and POST endpoints.

## Pydantic and validation

- **Pydantic model** — typed schema that validates request data.
- **response_model** — filters and documents the response shape.
- **HTTPException** — raises an error with a status code.

Practice: Validate a create-user payload.

## Dependencies and async

- **Depends** — injects shared logic such as a database session.
- **async def** — declares a coroutine handler.
- **Uvicorn** — ASGI server that runs the app.

Practice: Add a dependency that provides a DB session.

## Mini project

Build a FastAPI service with Pydantic models, dependency injection, a database and auto-generated docs.
