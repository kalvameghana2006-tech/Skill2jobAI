# Hibernate/JPA

> ORM layer mapping Java objects to relational tables.
> Category: Backend. Typical effort: about 4 study days.

## ORM concepts

- **ORM** — maps objects to relational tables.
- **@Entity** — marks a class persisted as a table.
- **@Id** — marks the primary key field.

Practice: Map a simple entity and persist it.

## Relationships and queries

- **@OneToMany** — one entity relates to many others.
- **JPQL** — object-oriented query language.
- **Lazy loading** — related data is fetched only when accessed.

Practice: Create a relationship and write a custom query.

## Mini project

Model a one-to-many relationship (Author-Books) with JPA entities, repositories and custom queries.
