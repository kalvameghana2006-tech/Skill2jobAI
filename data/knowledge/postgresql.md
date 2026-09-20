# PostgreSQL

> Advanced open source relational database with rich types and extensions.
> Category: Databases. Typical effort: about 3 study days.

## Setup and data types

- **psql** — command line client for PostgreSQL.
- **SERIAL** — auto-incrementing integer column.
- **JSONB** — binary JSON column type that can be indexed.

Practice: Install PostgreSQL and create a database with three tables.

## Constraints and indexes

- **Foreign key** — enforces a valid link between tables.
- **Unique constraint** — prevents duplicate values.
- **GIN index** — index type suited to JSONB and full-text search.

Practice: Add constraints and compare EXPLAIN before and after an index.

## Transactions and views

- **BEGIN and COMMIT** — group statements into one atomic unit.
- **View** — saved query that behaves like a table.
- **Materialized view** — stores query results physically.

Practice: Create a view for monthly sales.

## Mini project

Model an e-commerce schema in PostgreSQL with constraints, indexes, a view and a transaction, documented with EXPLAIN output.
