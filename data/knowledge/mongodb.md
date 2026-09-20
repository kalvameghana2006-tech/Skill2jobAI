# MongoDB

> Document oriented NoSQL database storing JSON like documents.
> Category: Databases. Typical effort: about 4 study days.

## Document databases

- **Document** — JSON-like record stored in BSON.
- **Collection** — group of documents, similar to a table.
- **_id** — unique identifier every document has.

Practice: Insert and find documents in mongosh.

## CRUD and queries

- **insertOne** — adds a document.
- **find** — retrieves documents matching a filter.
- **$set** — update operator that changes specific fields.

Practice: Write queries with filters, projections and sorting.

## Modelling and indexes

- **Embedding** — nesting related data inside one document.
- **Referencing** — storing another document's id.
- **Index** — structure that speeds up queries on a field.

Practice: Model orders with items embedded and users referenced.

## Aggregation

- **Aggregation pipeline** — sequence of stages that transform documents.
- **$group** — stage that groups documents and computes totals.
- **$lookup** — stage that joins another collection.

Practice: Compute sales per category with $group.

## Mini project

Model a blog or e-commerce dataset in MongoDB with embedded and referenced documents, CRUD operations and an aggregation pipeline.
