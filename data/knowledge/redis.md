# Redis

> In memory key value store used for caching, sessions and queues.
> Category: Databases. Typical effort: about 3 study days.

## Redis basics

- **Key-value store** — data addressed by unique keys.
- **TTL** — time after which a key expires automatically.
- **In-memory** — data kept in RAM for very fast reads.

Practice: Set, get and expire keys from redis-cli.

## Caching patterns

- **Cache-aside** — app checks the cache first then loads from the database.
- **Cache invalidation** — removing or updating stale cached data.
- **Data types** — strings, hashes, lists, sets and sorted sets.

Practice: Cache a slow database query and measure the speed-up.

## Mini project

Add Redis caching to an API (cache-aside with TTL) and measure latency before and after, with a short write-up.
