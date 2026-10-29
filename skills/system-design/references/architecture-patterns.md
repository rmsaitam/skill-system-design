# Architecture Patterns

Use this reference to compare options. Always record the chosen option and the rejected alternatives in the ADRs.

## System styles

| Style | Use when | Avoid when |
| --- | --- | --- |
| Modular monolith | The domain is still evolving, the team is small, and transactional consistency matters | Independent scaling or deployment is already required per domain |
| Microservices | Domains have clear boundaries, independent scaling needs, and separate ownership | The team lacks platform maturity or the boundaries are guesses |
| Event-driven | Work is naturally asynchronous, spiky, or fan-out | The team cannot operate queues, retries, and idempotency |
| Serverless | Traffic is bursty, jobs are short, and operational overhead must be minimal | Long-running work, strict latency, or heavy stateful workloads |
| Batch | Work is periodic and throughput matters more than latency | Users need interactive responses |
| Edge or CDN-heavy | Content is cacheable and geographically distributed | Data is highly personalized or strongly consistent |

Prefer a modular monolith until scaling, ownership, or failure isolation justifies the operational cost of services.

## Core components

- **Load balancer**: L4 for raw throughput, L7 for routing, TLS, and header-aware policies.
- **API gateway**: authentication, rate limiting, routing, and request shaping. Avoid turning it into a business-logic layer.
- **BFF**: a backend for a specific client. Useful for aggregation, but it creates another deployable.
- **Service mesh**: mTLS, retries, and telemetry for many services. Justify it only at scale.
- **Cache**: Redis or a local cache. Define the key, TTL, invalidation, and stampede protection.
- **Queue or broker**: decouples producers and consumers. Define delivery guarantees, ordering, retention, and DLQ behavior.
- **Object storage**: large immutable blobs. Use pre-signed URLs instead of proxying bytes through the API.
- **Search index**: derived data for text and faceted queries. Rebuildable from the source of truth.

## Communication

### Synchronous

- Simple request/response and immediate consistency.
- Creates temporal coupling: if the dependency is slow, the caller is slow.
- Requires timeouts, retries, circuit breakers, and a fallback.

### Asynchronous

- Decouples availability and smooths spikes.
- Introduces eventual consistency, duplication, ordering, and replay concerns.
- Requires idempotent consumers, a dead-letter queue, and lag monitoring.

### Patterns

- **Outbox**: write the domain change and the event in one transaction, then publish from an outbox relay. Avoids dual-write inconsistency.
- **Saga**: coordinate a multi-service workflow with compensating actions. Use orchestration for visibility or choreography for loose coupling.
- **Idempotency key**: make retries safe for creates and payments.
- **Claim check**: put large payloads in object storage and send a reference in the message.
- **Backpressure**: bound queues and reject or slow producers before memory or latency collapses.
- **Dead-letter queue**: capture poison messages and make replay a documented operation.

## Data and scaling patterns

- **Read replica**: scale reads and isolate analytics. Accept replication lag.
- **Sharding**: scale writes and storage beyond one primary. Choose a high-cardinality key and plan for resharding.
- **Consistent hashing**: distribute keys with minimal movement when nodes change.
- **CQRS**: separate write and read models when their shapes or scaling needs differ. Accept projection lag and operational complexity.
- **Event sourcing**: keep an append-only event log as the source of truth. Use only when audit, replay, or temporal queries justify it.
- **Materialized view**: precompute expensive reads. Define refresh and staleness.
- **Rate limiting**: token bucket or sliding window at the edge and per tenant.
- **Bulkhead**: isolate pools so one dependency cannot exhaust all resources.

## Caching strategies

| Strategy | Behavior | Trade-off |
| --- | --- | --- |
| Cache-aside | Application reads cache, then database, then populates | Simple; stale data until TTL or invalidation |
| Read-through | Cache loads from the database | Cleaner application code; cache becomes a critical path |
| Write-through | Write cache and database together | Consistent cache; higher write latency |
| Write-behind | Write cache first and persist later | Fast writes; risk of data loss |
| Refresh-ahead | Refresh hot keys before expiry | Smooth latency; extra load and complexity |

Always define stampede protection: request coalescing, jittered TTLs, or a short lock.

## Multi-region and disaster recovery

| Strategy | RTO | RPO | Cost | Notes |
| --- | --- | --- | --- | --- |
| Backup and restore | Hours | Minutes to hours | Low | Test restores; backups are not a DR plan by themselves |
| Pilot light | 30 to 120 minutes | Minutes | Medium | Core data replicated; standby is minimal |
| Warm standby | 5 to 30 minutes | Seconds to minutes | High | Standby runs at reduced capacity |
| Active-active | Near zero | Near zero | Very high | Requires conflict resolution and global consistency design |

Define RTO and RPO before choosing the strategy. Active-active is not a default; it is a business decision.

## Anti-patterns

- Distributed monolith: many services deployed together with shared databases and synchronous chains.
- Shared database across services: hidden coupling and unclear ownership.
- Chatty synchronous calls: latency and failure multiply along the chain.
- Unbounded queues: they hide overload until memory or disk fails.
- Cache without invalidation: stale data becomes a correctness bug.
- Sharding before measuring: premature partitioning adds irreversible complexity.
- Event sourcing for simple CRUD: unnecessary operational and cognitive load.
- Metrics without SLOs: dashboards that nobody can act on.

## Selection checklist

- Which quality attribute dominates: latency, throughput, availability, consistency, cost, or delivery speed?
- Which failure is acceptable, and which is not?
- Can the team operate the added components on call?
- Which decision is hardest to reverse?
- What is the simplest option that meets the measurable targets?
