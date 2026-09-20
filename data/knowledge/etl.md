# ETL

> Extracting, transforming and loading data with pipelines and orchestration tools like Airflow.
> Category: Data & ML. Typical effort: about 5 study days.

## ETL concepts

- **Extract** — pull data from sources.
- **Transform** — clean and reshape data.
- **Load** — write data into the target store.

Practice: Sketch an ETL diagram for sales data.

## Building pipelines

- **Idempotent job** — safe to run twice with the same result.
- **Data validation** — checks that data meets expectations.
- **Airflow DAG** — workflow of tasks with dependencies.

Practice: Schedule a daily job that loads a CSV.

## Quality and scale

- **Incremental load** — processes only new or changed rows.
- **Schema evolution** — handling changes in source columns.
- **Data lineage** — tracking where data came from.

Practice: Add validation checks and a failure alert.

## Mini project

Build an ETL pipeline that extracts from an API and a CSV, cleans and loads into SQLite or PostgreSQL, scheduled with Airflow or cron.
