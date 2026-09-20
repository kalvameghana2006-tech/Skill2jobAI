# Operating Systems

> Processes, threads, scheduling, memory management and file systems.
> Category: CS Fundamentals. Typical effort: about 8 study days.

## Processes and threads

- **Process** — running program with its own address space.
- **Thread** — unit of execution inside a process.
- **Context switch** — saving one task's state to run another.

Practice: Trace how fork creates a child process.

## CPU scheduling and deadlocks

- **Round robin** — scheduler giving each process a fixed time slice.
- **Deadlock** — processes waiting on each other forever.
- **Mutex** — lock that lets only one thread enter a critical section.

Practice: Simulate FCFS and round robin scheduling and compare waiting times.

## Memory management

- **Virtual memory** — gives each process its own large address space.
- **Paging** — splits memory into fixed size pages and frames.
- **Page fault** — access to a page not currently in RAM.

Practice: Work out page replacement with FIFO and LRU on a reference string.

## Mini project

Write a report with small programs demonstrating process creation, thread synchronization and a scheduling simulation.
