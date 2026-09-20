# DBMS

> Relational model, normalization, ER modelling, ACID transactions and indexing.
> Category: CS Fundamentals. Typical effort: about 6 study days.

## Relational model and ER design

- **Entity** — real world object stored as a table.
- **Relationship** — association between entities.
- **Candidate key** — minimal set of columns that uniquely identifies a row.

Practice: Draw an ER diagram for a library.

## Normalization

- **1NF** — every column holds atomic values.
- **2NF** — no partial dependency on part of a composite key.
- **3NF** — no transitive dependency between non-key columns.

Practice: Normalize a messy orders table up to 3NF.

## Transactions and indexing

- **ACID** — atomicity, consistency, isolation and durability guarantees.
- **Isolation level** — controls how concurrent transactions see each other.
- **B-tree index** — balanced tree structure speeding up lookups.

Practice: Explain a bank transfer as a transaction.

## Mini project

Design an ER diagram and normalized schema for a hospital or library system and demonstrate two transactions with ACID reasoning.
