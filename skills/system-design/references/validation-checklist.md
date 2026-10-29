# Validation Checklist

Use this checklist when Python is unavailable or when reviewing a design manually. The validator script is authoritative; this checklist mirrors its checks.

## Artifact and metadata

- [ ] The file starts with `<!-- system-design:artifact type=design version=1 -->`.
- [ ] Status is `Draft`, `In review`, `Approved`, or `Superseded`.
- [ ] Date uses `YYYY-MM-DD`.
- [ ] Owner and artifact language are present.
- [ ] The counts marker matches the number of FR, NFR, SLO, ADR, and risk items.

## Required sections

- [ ] `context`
- [ ] `requirements`
- [ ] `nfr`
- [ ] `slo`
- [ ] `capacity`
- [ ] `architecture`
- [ ] `data`
- [ ] `components`
- [ ] `flows`
- [ ] `tradeoffs`
- [ ] `risks`
- [ ] `security`
- [ ] `observability`
- [ ] `resilience`
- [ ] `decisions`
- [ ] `assumptions`
- [ ] `qa`
- [ ] `traceability`
- [ ] `dod`

No required section may be empty.

## Requirements

- [ ] Every FR uses `- **FR-001**:` format and has a unique sequential ID.
- [ ] Every NFR is a table row with ID, requirement, target, and measurement.
- [ ] Every NFR target contains a number, comparator, percentage, or percentile.
- [ ] Every SLO is a table row with ID, SLI, target, window, and error budget.
- [ ] At least one FR, one NFR, and one SLO exist.

## Capacity

- [ ] Every CAP row has ID, metric, inputs, formula, result, and assumption.
- [ ] Every result contains a number.
- [ ] Every formula shows the arithmetic.
- [ ] Peak traffic, storage, bandwidth, cache, nodes, and availability are covered.
- [ ] The dominant cost driver is stated.

## Architecture

- [ ] The architecture section contains a Mermaid or ASCII diagram.
- [ ] Trust boundaries are stated.
- [ ] Components and flows cover the primary path and critical failure paths.
- [ ] Component IDs and flow IDs are unique and sequential.

## Data

- [ ] SQL and NoSQL are both considered.
- [ ] The storage choice has a rationale.
- [ ] The source of truth is named for each important record.
- [ ] Indexing, partitioning, replication, consistency, retention, and migrations are covered.

## Decisions and risks

- [ ] At least three ADRs exist.
- [ ] Every ADR has status, context, decision, alternatives, and consequences.
- [ ] ADR status is `Proposed`, `Accepted`, `Deprecated`, or `Superseded`.
- [ ] Every risk has likelihood, impact, severity, confidence, mitigation, and owner.
- [ ] Likelihood, impact, and severity use `High`, `Medium`, or `Low`.
- [ ] Confidence uses `Confirmed`, `Likely`, or `Assumption`.
- [ ] Single points of failure, bottlenecks, cost, and operational risk are covered.

## Security, observability, and resilience

- [ ] The threat model covers assets, actors, trust boundaries, and attack paths.
- [ ] Authentication, authorization, tenant isolation, secrets, encryption, and rate limiting are covered.
- [ ] Logs, metrics, traces, and alerts are covered.
- [ ] SLIs, SLOs, windows, and error budgets are covered.
- [ ] Timeouts, retries, circuit breakers, bulkheads, backup, restore, and disaster recovery are covered.

## Traceability and finish

- [ ] Every FR and NFR appears in the traceability table.
- [ ] Every FR and NFR maps to at least one component or flow.
- [ ] Every FR and NFR maps to at least one ADR or risk.
- [ ] At least six questions are answered.
- [ ] Assumptions and open questions are explicit.
- [ ] No `TODO`, `TBD`, or `FIXME` placeholders remain.
- [ ] No secrets, credentials, customer data, or personal data are present.
- [ ] The validator passes with no errors.

## Validator command

```bash
python3 scripts/validate_design.py SYSTEM-DESIGN.md --min-questions 6
```

Use `--strict` to treat warnings as errors and `--json` for a machine-readable report. Use `--min-adrs 3` to require at least three decisions.
