# Trade-offs Baseline

Every important architecture decision is a trade-off. State what becomes easier, what becomes harder, and what the team accepts in exchange. A recommendation without an alternative is not a decision.

## CAP and PACELC

- **CAP**: during a network partition, choose consistency or availability. Partitions are unavoidable in distributed systems.
- **PACELC**: else, when there is no partition, choose latency or consistency.
- A single-node database does not escape the trade-off; it hides it inside the vendor.
- "CA" is not a useful label for a distributed system. State the partition behavior explicitly.

## Common trade-offs

### Consistency versus availability

- Strong consistency simplifies correctness but increases coordination, latency, and failure coupling.
- Eventual consistency improves availability and latency but pushes reconciliation into the product and operations.
- Ask which stale read is acceptable and for how long.

### Latency versus throughput

- Batching and pipelining increase throughput and usually increase tail latency.
- Caching reduces latency and backend load but introduces invalidation and staleness.
- Synchronous fan-out is simple but multiplies tail latency.

### Coupling versus autonomy

- A monolith is easier to reason about and transact across, but couples deployment and scaling.
- Microservices improve autonomy and isolation, at the cost of network failure, observability, and platform work.
- Shared databases create hidden coupling even when services look independent.

### Build versus buy

- Buy when the capability is undifferentiated, the vendor is mature, and exit cost is acceptable.
- Build when the capability is core, the constraints are unusual, or the vendor lock-in is unacceptable.
- Always estimate the total cost: integration, operations, on-call, and migration.

### Cost versus resilience

- Multi-region active-active is expensive and operationally demanding.
- A warm standby is often the pragmatic middle ground.
- Backups are not a disaster recovery strategy until a restore has been tested.

### Simplicity versus flexibility

- Every abstraction and every component has an operational cost.
- Design for the requirements you have, with a credible path to the next order of magnitude.
- Do not build for a scale you cannot justify.

## Decision heuristics

- Choose the option that meets the must-have SLOs with the least operational complexity.
- Prefer reversible decisions. Spend more analysis only on irreversible ones.
- Prefer managed services for undifferentiated infrastructure.
- Prefer a modular monolith until boundaries and scale are proven.
- Prefer asynchronous boundaries when the user does not need an immediate result.
- Prefer strong consistency for money, entitlements, and uniqueness; prefer eventual consistency for feeds, analytics, and caches.
- Measure before sharding, before adding a broker, and before splitting a service.
- If two options are close, choose the one the team can operate on call.

## Risk calibration

| Severity | Likelihood | Impact | Examples |
| --- | --- | --- | --- |
| High | Medium or High | High | Data loss, security breach, extended outage, unbounded cost, a must-have SLO that cannot be met |
| Medium | Medium | Medium | Degradation under peak, costly rework, an SLO met only with untested assumptions |
| Low | Low | Low or Medium | Local inefficiency, maintainability concern, missing hardening with limited impact |

Confidence:

- **Confirmed**: observed in code, data, a test, or a cited source.
- **Likely**: strong evidence, but not directly reproduced.
- **Assumption**: a belief that must be validated.

A High risk with `Assumption` confidence is a red flag. Either validate it or record a time-bound decision.

## ADR format

```markdown
### ADR-001: Short decision title

- Status: Accepted
- Context: Why the decision was needed and which forces apply.
- Decision: What was chosen.
- Alternatives: The options that were rejected.
- Consequences: What becomes easier, harder, or constrained.
```

Status values: `Proposed`, `Accepted`, `Deprecated`, `Superseded`.

Rules:

- One decision per ADR.
- Record the alternatives, not only the winner.
- Record the consequences, including the negative ones.
- Supersede instead of rewriting history.
- Link the ADR to the requirements it satisfies and the risks it introduces.

## Pre-mortem questions

- It is one year later and the system failed. What happened?
- Which component failed first, and how did the failure spread?
- Which dependency was unavailable, and what did users see?
- Which assumption was wrong, and what did it cost?
- Which bottleneck appeared at 10 times the traffic?
- Which operational task was forgotten?
- Which decision is hardest to reverse now?

## Traceability

Every FR and NFR should trace to at least one component or flow and at least one ADR or risk. A requirement without a design element is a gap. A design element without a requirement is a candidate for removal.
