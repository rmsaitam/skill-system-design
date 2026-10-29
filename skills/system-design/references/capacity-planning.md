# Capacity Planning

Use back-of-the-envelope calculations to make the design defensible, not to produce false precision. State every input, show the formula, present a range when the input is uncertain, and label assumptions.

## Core formulas

### Traffic

```text
average QPS = daily active users * actions per user per day / 86,400
peak QPS   = average QPS * peak factor
read QPS   = peak QPS * read ratio
write QPS  = peak QPS * write ratio
```

- A peak factor of 2 to 10 is common for consumer traffic. Validate it with real data when possible.
- Batch, scheduled, and event-driven workloads need their own arrival model.
- Do not design for average traffic. Design for peak and for failover capacity.

### Storage

```text
records per day   = writes per day * records per write
raw bytes per day = records per day * average record size
stored bytes      = raw bytes per day * retention days * replication factor
index overhead    = stored bytes * index factor (typically 1.2 to 2.0)
```

Include indexes, write-ahead logs, backups, and replicas. A number that only counts raw rows is misleading.

### Bandwidth

```text
egress bits per second = QPS * average response bytes * 8
ingress bits per second = QPS * average request bytes * 8
```

Separate the dominant direction. For read-heavy systems, egress usually dominates cost and capacity.

### Cache

```text
working set = total objects * hot fraction * average object size
cache memory = working set * (1 + overhead factor)
required hit ratio = 1 - (backend capacity / peak QPS)
```

- A cache that cannot hold the working set will thrash.
- A cache with a 99% hit ratio still sends 1% of peak traffic to the backend. Size the backend for that residual load plus failover.
- Jitter TTLs to avoid synchronized expiry.

### Nodes and concurrency

```text
nodes = peak QPS / per-node capacity * headroom factor
headroom factor = 1.5 for normal growth, 2.0 for N+1 failover, 3.0 for conservative design
concurrency = throughput * latency (Little's Law: L = lambda * W)
```

- Per-node capacity must be measured, not guessed. Use a load test or a vendor limit marked as an assumption.
- If one node can fail without violating the SLO, the remaining nodes must absorb its load.

### Queues

```text
arrival rate lambda = events per second
service rate mu     = consumers * events per second per consumer
utilization         = lambda / mu
queue depth         = lambda * wait time (Little's Law)
drain time          = backlog / (mu - lambda)
```

- Keep utilization below 80% for latency-sensitive queues. Near 100%, queue depth grows without bound.
- Size the dead-letter queue and replay procedure, not only the happy path.

### Availability

```text
serial availability   = A1 * A2 * ... * An
parallel availability = 1 - (1 - A1) * (1 - A2) * ... * (1 - An)
error budget          = 1 - SLO
monthly budget minutes = 30 * 24 * 60 * (1 - SLO)
```

- Redundancy only improves availability when failover is automatic and tested.
- A dependency with 99.9% availability caps a serial path below 99.9%.
- A 99.95% monthly SLO gives about 21.6 minutes of error budget.

### Latency budget

```text
p99 path latency <= sum of serial dependency p99 latencies
parallel calls     <= max of parallel dependency p99 latencies
```

- Summing p99 values is conservative. Use measured traces when available.
- Keep a budget per hop: edge, application, cache, database, and external calls.
- Tail latency is dominated by queueing, retries, and garbage collection.

### Cost order of magnitude

```text
monthly cost = compute + storage + egress + managed services + observability + backup
```

- Use current public prices or the user's contract. Cite the source or label the number as an assumption.
- Identify the dominant cost driver and the sensitivity to traffic growth.
- A cost estimate without a range is not useful for early design.

## Worked example: URL shortener

| Input | Value | Source |
| --- | --- | --- |
| Monthly active users | 10,000,000 | Product assumption |
| Redirects per user per day | 30 | Product assumption |
| Peak factor | 5 | Assumption to validate |
| Average response size | 2 KB | Measured from a prototype |

```text
average QPS = 10,000,000 * 30 / 86,400 = 3,472
peak QPS    = 3,472 * 5 = 17,361
```

With 2,000 QPS per node and N+1 headroom:

```text
nodes = 17,361 / 2,000 * 2 = 18 nodes
```

The design should still work if the peak factor is 10 instead of 5. In that case the node count doubles to 36. Record the sensitivity.

## Review questions

- Is the peak factor based on data or an assumption?
- Does the design survive the loss of one node, one zone, or one dependency?
- Which resource saturates first: CPU, memory, disk, network, connections, or locks?
- What is the residual load on the backend when the cache hit ratio drops?
- How long does it take to drain a queue after a consumer outage?
- What is the cost per 1,000 requests, and how does it change at 10 times the traffic?
- Which estimate would force a redesign if it were wrong by an order of magnitude?
