---
description: Critique an existing architecture for scalability, trade-offs, and failure modes
argument-hint: Architecture document, repository, or design notes to critique
---

# System Design Critique

Load and follow the `system-design` skill.

Host arguments: `$ARGUMENTS`

Use the host arguments as the architecture under review when present. Otherwise inspect the repository for architecture documents, manifests, schemas, and infrastructure files.

Read the existing design before judging it. Identify the stated requirements and quality attributes. If they are missing, ask for them instead of inventing them.

Produce a structured critique covering:

- requirement gaps and unmeasurable non-functional requirements;
- capacity assumptions and missing estimates;
- single points of failure, bottlenecks, and blast radius;
- consistency, availability, and CAP or PACELC trade-offs;
- data model, storage choice, indexing, partitioning, and replication;
- coupling, synchronous chains, and asynchronous failure handling;
- security, tenancy, secrets, and abuse controls;
- observability, SLOs, error budgets, and alerting;
- resilience, backup, restore, RTO, and RPO;
- over-engineering and unnecessary complexity.

For every issue, state the evidence, the impact, and a concrete recommendation with trade-offs. Label each finding as `High`, `Medium`, or `Low`, and label confidence as `Confirmed`, `Likely`, or `Assumption`.

Do not implement fixes, change code, or rewrite the system unless the user explicitly asks. Offer to update `SYSTEM-DESIGN.md` or to deepen one area next.
