# Big Data

> Distributed data processing with Spark and Hadoop.
> Category: Data & ML. Typical effort: about 12 study days.

## Distributed processing

- **Cluster** — group of machines working together.
- **MapReduce** — split, process and combine model for big data.
- **HDFS** — distributed file system for large files.

Practice: Explain how word count runs on a cluster.

## Spark essentials

- **DataFrame** — distributed table with a schema.
- **Transformation** — lazy operation that defines a new dataset.
- **Action** — operation that triggers computation.

Practice: Load a CSV into Spark and aggregate it.

## Performance

- **Partition** — slice of data processed in parallel.
- **Shuffle** — expensive movement of data between nodes.
- **Caching** — keeps data in memory for reuse.

Practice: Compare runtimes with different partition counts.

## Mini project

Analyze a multi-million row dataset with PySpark, using DataFrames, joins and partitioning, and report timings.
