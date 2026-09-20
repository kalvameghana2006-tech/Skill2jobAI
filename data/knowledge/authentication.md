# Authentication

> Securing APIs with sessions, JWT tokens, OAuth2 and role based access control.
> Category: Backend. Typical effort: about 4 study days.

## Auth concepts

- **Authentication** — proving who you are.
- **Authorization** — deciding what you may do.
- **Password hashing** — storing a one-way hash instead of the password.

Practice: Add registration with hashed passwords.

## Tokens and roles

- **JWT** — signed token carrying claims about the user.
- **Bearer token** — token sent in the Authorization header.
- **RBAC** — permissions granted through roles.

Practice: Protect an endpoint so only admins can call it.

## Mini project

Secure a REST API with JWT login, password hashing and role-based route protection.
