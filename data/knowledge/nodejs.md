# Node.js

> JavaScript runtime for building fast server side applications and APIs.
> Category: Backend. Typical effort: about 8 study days.

## Node runtime basics

- **Event loop** — lets Node handle many operations without blocking.
- **npm** — package manager for JavaScript libraries.
- **CommonJS/ESM** — module systems for sharing code between files.

Practice: Run scripts, read files and install a package.

## Building a server

- **http module** — built-in server API.
- **Route** — URL and method pair handled by a function.
- **Request/Response** — objects representing incoming and outgoing HTTP data.

Practice: Create a server with three routes.

## Express and middleware

- **Middleware** — function that runs between request and response.
- **express.json()** — parses JSON request bodies.
- **Router** — groups related routes.

Practice: Refactor into routers and add logging middleware.

## Databases and async code

- **Mongoose** — ODM that models MongoDB documents.
- **async/await** — sequential-looking asynchronous code.
- **Environment variables** — keep secrets out of source code.

Practice: Persist data in MongoDB and read config from .env.

## Mini project

Build a Node.js + Express REST API with MongoDB or a JSON store, request validation, error middleware and environment-based config.
