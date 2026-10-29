---
description: Design a system with a principal architect and produce SYSTEM-DESIGN.md
argument-hint: System idea, service, or architecture scope notes
---

# System Design

Load and follow the `system-design` skill.

Host arguments: `$ARGUMENTS`

Use the host arguments as the design brief when present. Otherwise use the repository in the current workspace. If the problem, users, scale, or constraints are unclear, ask before proposing an architecture.

Start with context and reconnaissance, then run the requirements interview in rounds of at most five questions. Cover functional requirements, non-functional requirements, scale, latency percentiles, consistency, availability, data, integrations, security, operations, team, budget, and compliance.

Do not write `SYSTEM-DESIGN.md` until the user approves the design plan. Do not implement application code, provision infrastructure, or change repositories. The deliverable is the design artifact and its decisions, not code.

After approval, produce the requirements baseline, capacity estimates, high-level design with Mermaid or ASCII, data model, components, flows, trade-offs, risks, security, observability, resilience, ADRs, and traceability.

Run the bundled validator, fix every error, and report the requirement counts, capacity summary, highest risks, assumptions, and validation result. End by asking which bottleneck or area to deepen next.
