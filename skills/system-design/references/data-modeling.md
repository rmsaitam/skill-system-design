# Data Modeling

Start from access patterns and invariants, not from a preferred database. The storage choice must follow the requirements and be justified in `SYSTEM-DESIGN.md`.

## Step 1: Model the domain

- List entities, attributes, relationships, and invariants.
- Identify the aggregate boundaries and the transactional boundary.
- Define the source of truth for every important record.
- Distinguish master data from derived data.
- Identify personal, financial, health, and tenant data.

## Step 2: List access patterns

For each important query or write, record:

- frequency and peak rate;
- key and filters;
- sort order and pagination;
- expected result size;
- consistency requirement;
- latency target.

Design indexes for the top access patterns, not for every column.

## Step 3: Choose SQL or NoSQL

| Criterion | SQL | NoSQL |
| --- | --- | --- |
| Transactions across entities | Strong fit | Limited or aggregate-scoped |
| Ad hoc queries and joins | Strong fit | Weak or not supported |
| Schema evolution | Migrations, explicit | Flexible, but application-enforced |
| Horizontal write scale | Harder, sharding required | Native in many engines |
| Access patterns | Flexible | Usually fixed and known |
| Consistency | Strong by default | Tunable, often eventual |
| Operational maturity | High | Varies by engine |
| Best for | Integrity, reporting, evolving queries | Scale, known access patterns, sparse or nested data |

Engine hints:

- **PostgreSQL or MySQL**: transactional integrity, relationships, moderate to high scale, reporting.
- **Document store**: aggregate-oriented data with flexible shape and known access patterns.
- **Wide-column**: very high write throughput and known query keys.
- **Key-value**: low-latency lookups, caches, sessions, counters.
- **Search engine**: text search and faceted queries, as derived data.
- **Time-series**: metrics and events with time-based retention.
- **Graph**: highly connected data with traversal-heavy queries.

Do not choose a database for novelty. Do not choose a relational database and then avoid its constraints.

## Step 4: Indexing

- Index for equality, range, and sort order used by the top queries.
- Column order in a composite index matters: equality first, then range, then sort.
- A covering index avoids table lookups but increases write amplification and storage.
- Partial indexes reduce size for filtered queries.
- Review unused and duplicate indexes.
- Measure the write cost of every index at peak.

## Step 5: Partitioning and sharding

- Partition when a table or index no longer fits the operational envelope.
- Choose a high-cardinality key that spreads load and matches the dominant access pattern.
- Avoid keys that create hot partitions: timestamps, tenant IDs with one huge tenant, or sequential IDs.
- Plan resharding before the first shard is full.
- Keep cross-shard transactions out of the critical path.
- Document the rebalancing procedure and its impact.

## Step 6: Replication and consistency

| Topology | Benefit | Trade-off |
| --- | --- | --- |
| Single primary, async replica | Simple read scaling | Replica lag and possible stale reads |
| Single primary, sync standby | Durability and failover | Higher write latency |
| Multi-primary | Local writes in multiple regions | Conflict resolution and complexity |
| Quorum | Tunable consistency and availability | Operational and latency cost |

Consistency models:

- **Strong / linearizable**: reads see the latest committed write. Highest coordination cost.
- **Causal**: preserves cause and effect. Good default for user-facing collaboration.
- **Read-your-writes**: the user sees their own write. Usually implemented with session stickiness or a token.
- **Eventual**: replicas converge. Acceptable for analytics, feeds, and caches when the user impact is understood.

State the user-visible consequence of stale reads. "Eventually consistent" alone is not a design decision.

## Step 7: Retention and lifecycle

- Define retention per entity and per tenant.
- Separate hot, warm, and cold storage.
- Define archival and restore procedures.
- Define deletion and export requirements, including legal holds.
- Ensure backups follow the same retention and privacy rules.
- Avoid storing raw personal data when a derived value is sufficient.

## Step 8: Multi-tenancy

| Model | Isolation | Cost | Use when |
| --- | --- | --- | --- |
| Shared tables with tenant ID | Logical | Low | Many small tenants and strong query scoping |
| Schema per tenant | Medium | Medium | Moderate tenant count and isolation needs |
| Database per tenant | High | High | Strong isolation, compliance, or noisy-neighbor concerns |

Enforce tenant scoping in the data access layer and test it. A missing `WHERE tenant_id = ?` is a security incident.

## Step 9: Schema evolution

- Prefer expand-and-contract migrations.
- Make reads backward compatible during the transition.
- Never run a destructive migration before the old code is fully drained.
- Test migrations against a production-sized dataset.
- Define the rollback path and the point of no return.
- Keep migrations idempotent where the platform allows it.

## Review questions

- What is the source of truth, and what is derived?
- Which invariants must be transactional?
- Which access pattern drives the primary key?
- What happens when the hot partition is 100 times larger than the average?
- How stale can a read be before it becomes a user-visible bug?
- What is the resharding plan, and how long does it take?
- How is tenant isolation enforced and tested?
- How is data deleted, and how are backups handled?
