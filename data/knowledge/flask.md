# Flask

> Lightweight Python micro-framework for web apps and APIs.
> Category: Backend. Typical effort: about 4 study days.

## Routing and requests

- **Route** — maps a URL to a Python function.
- **request** — object holding data sent by the client.
- **jsonify** — returns a JSON response.

Practice: Create GET and POST routes.

## Structure and data

- **Blueprint** — groups related routes into a module.
- **SQLAlchemy** — ORM for talking to databases from Python.
- **Application factory** — function that creates and configures the app.

Practice: Store notes in SQLite with SQLAlchemy.

## Errors and testing

- **Error handler** — custom response for an exception or status code.
- **Test client** — simulates requests without running a server.
- **Environment config** — separates settings from code.

Practice: Write three tests with the Flask test client.

## Mini project

Build a Flask API with blueprints, SQLite storage and pytest tests, and document the endpoints.
