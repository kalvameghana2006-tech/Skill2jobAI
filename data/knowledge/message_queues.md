# Message Queues

> Asynchronous communication between services using brokers such as Kafka and RabbitMQ.
> Category: Backend. Typical effort: about 7 study days.

## Why queues

- **Message broker** — middleman that stores and routes messages.
- **Producer** — service that sends messages.
- **Consumer** — service that reads messages.

Practice: Explain synchronous versus asynchronous processing with an order example.

## Kafka and RabbitMQ concepts

- **Topic** — named stream of messages in Kafka.
- **Partition** — ordered slice of a topic that enables parallelism.
- **Consumer group** — consumers sharing the work of a topic.

Practice: Run a broker with Docker and send ten messages.

## Reliability

- **Acknowledgement** — consumer confirms a message was processed.
- **Dead-letter queue** — holds messages that keep failing.
- **Idempotent consumer** — handles duplicates safely.

Practice: Add retry logic and a dead-letter queue.

## Mini project

Build a producer and consumer pair using Kafka or RabbitMQ with retries and a dead-letter queue, documented with a diagram.
