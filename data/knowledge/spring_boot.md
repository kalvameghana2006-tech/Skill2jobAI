# Spring Boot

> Opinionated Java framework for building production-ready REST services with auto-configuration.
> Category: Backend. Typical effort: about 10 study days.

## Spring Boot foundations

- **Auto-configuration** — Spring Boot sets sensible defaults from the libraries on the classpath.
- **Starter** — one dependency that pulls in a whole feature set.
- **Spring Initializr** — web tool that generates a project skeleton.

Practice: Generate a project with Spring Initializr and run a hello endpoint.

## Controllers and request mapping

- **@RestController** — marks a class whose methods return JSON responses.
- **@GetMapping** — maps an HTTP GET request to a method.
- **@RequestBody** — binds the JSON request body to a Java object.

Practice: Create GET and POST endpoints for a Student or Product resource.

## Dependency injection and layers

- **Bean** — object managed by the Spring container.
- **@Service** — marks business logic classes.
- **Dependency injection** — Spring supplies collaborators instead of you calling new.

Practice: Split your code into controller, service and repository layers.

## Persistence with Spring Data JPA

- **@Entity** — maps a Java class to a database table.
- **JpaRepository** — gives CRUD methods without writing SQL.
- **application.properties** — holds datasource and server settings.

Practice: Connect your API to MySQL or H2 and persist real data.

## Validation, exceptions and tests

- **@Valid** — triggers bean validation on incoming data.
- **@ControllerAdvice** — centralizes exception handling for all controllers.
- **MockMvc** — tests controllers without starting a server.

Practice: Add validation, a global error handler and two controller tests.

## Mini project

Build a Spring Boot REST service with a MySQL or H2 database, layered controller/service/repository code and unit tests.
