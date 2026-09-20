# Express.js

> Minimal Node.js web framework for routing, middleware and REST APIs.
> Category: Backend. Typical effort: about 3 study days.

## Routing and middleware

- **Route** — path and method handled by a callback.
- **Middleware** — function with access to req, res and next.
- **Router** — mounts groups of routes on a path.

Practice: Create a users router with GET and POST.

## Errors and structure

- **Error-handling middleware** — function with four arguments that handles errors.
- **req.params** — values captured from the URL.
- **Controller layer** — keeps route files thin.

Practice: Add validation and a 404 plus 500 handler.

## Mini project

Build an Express REST API with routers, validation and centralised error handling.
