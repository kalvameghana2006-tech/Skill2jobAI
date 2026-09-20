# SQL

> Standard language to query and manage relational databases using joins, aggregations and subqueries.
> Category: Databases. Typical effort: about 7 study days.

## Querying with SELECT

- **SELECT** — chooses which columns to return.
- **WHERE** — filters rows before grouping.
- **ORDER BY** — sorts the result set.

Practice: Answer ten questions on a sample database with SELECT and WHERE.

## Aggregation and grouping

- **GROUP BY** — collapses rows into groups for aggregates like COUNT and SUM.
- **HAVING** — filters groups after aggregation.
- **DISTINCT** — removes duplicate rows from the result.

Practice: Compute totals and averages per category and filter groups with HAVING.

## Joins

- **INNER JOIN** — keeps only rows that match in both tables.
- **LEFT JOIN** — keeps all rows from the left table plus matches.
- **Foreign key** — column referencing another table's primary key.

Practice: Join three tables to build a report and explain each join type.

## Subqueries and window functions

- **Subquery** — query nested inside another query.
- **Window function** — calculates across related rows without collapsing them.
- **CTE** — named temporary result defined with WITH.

Practice: Rank rows per group with ROW_NUMBER and reuse logic with a CTE.

## Design and performance

- **Primary key** — uniquely identifies each row.
- **Index** — structure that speeds up lookups on a column.
- **Normalization** — organizing tables to reduce redundancy.

Practice: Create tables with keys and compare a query plan before and after adding an index.

## Mini project

Design a small schema (students, courses, enrollments) and write 15 queries using joins, GROUP BY, subqueries and window functions, documented in a README.
