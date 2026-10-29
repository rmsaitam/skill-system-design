# Security, Observability, and Resilience Checklist

Use this checklist during Gate 8. Record the decisions in the corresponding sections of `SYSTEM-DESIGN.md`. This is an architecture review, not a full security audit. For evidence-based findings and CVSS scoring, use the `security-audit` skill.

## Threat model

### Assets

- User accounts, credentials, tokens, and API keys.
- Personal, financial, health, and tenant data.
- Administrative functions and configuration.
- Availability and integrity of the primary flow.
- Billing, quotas, and entitlements.

### Actors

- Unauthenticated internet users.
- Authenticated users and tenants.
- Administrators and support staff.
- Insiders and compromised accounts.
- Partners, integrations, and supply-chain actors.

### Trust boundaries

- Browser or client to edge.
- Edge to API.
- API to database, cache, and queue.
- Service to service.
- CI/CD to registry and production.
- Tenant to tenant.

### Attack paths

- Account takeover through credential stuffing or weak recovery.
- Injection through input, headers, templates, or queries.
- Abuse of expensive endpoints for cost or denial of service.
- Enumeration of identifiers and scraping.
- SSRF through user-supplied URLs.
- Cross-tenant access through a missing authorization check.
- Supply-chain compromise through a dependency or image.

Use STRIDE as a prompt: spoofing, tampering, repudiation, information disclosure, denial of service, and elevation of privilege.

## Security controls

### Identity and access

- Authentication mechanism and token lifetime.
- MFA for administrative and sensitive operations.
- Authorization model: RBAC, ABAC, or relationship-based.
- Least privilege per role, service, and tenant.
- Session revocation and key rotation.
- Service-to-service identity and mTLS where needed.

### Input and output

- Schema validation on every external input.
- Allowlist URL schemes and block private network ranges.
- Parameterized queries and safe ORM usage.
- Output encoding and safe templating.
- File upload limits, type checks, and isolated storage.
- Size, rate, and concurrency limits per endpoint.

### Data protection

- TLS in transit, including internal service calls where required.
- Encryption at rest for databases, object storage, queues, and backups.
- Key management and rotation.
- Data classification and minimization.
- PII boundaries and redaction in logs and traces.
- Retention and deletion, including backups.

### Secrets and supply chain

- Secrets injected at runtime, never committed or baked into images.
- Secret scanning in CI and history.
- Dependency and image scanning.
- Signed or verified artifacts where the platform supports it.
- Pinned base images and reproducible builds.

### Abuse and availability

- Rate limiting per IP, user, API key, and tenant.
- Quotas and cost limits.
- WAF or edge filtering for common attacks.
- Bot and scraping detection.
- Audit logs for sensitive actions.

### Relevant OWASP and CWE areas

- Broken access control and missing authorization.
- Authentication and session failures.
- Injection: SQL, NoSQL, command, template, and header.
- Cryptographic failures and weak randomness.
- Insecure design and business-logic abuse.
- Security misconfiguration and permissive CORS.
- Vulnerable and outdated components.
- Integrity failures and unsafe deserialization.
- Logging and monitoring failures.
- SSRF and unrestricted file upload.

## Observability

### SLIs and SLOs

- Define SLIs that reflect user experience, not only CPU.
- Request-based SLIs: availability, latency, error rate, and correctness.
- Event-based SLIs: freshness, lag, and processing success.
- Define SLO targets, windows, and error budgets.
- Alert on burn rate, not only on instantaneous thresholds.

### Signals

- **Logs**: structured JSON, correlation ID, tenant ID, route, status, latency, and error code. No secrets or personal data.
- **Metrics**: traffic, errors, latency percentiles, saturation, queue depth, consumer lag, cache hit ratio, replication lag, and connection pool usage.
- **Traces**: end-to-end context across synchronous calls, asynchronous publishes, and consumers.
- **Profiles**: CPU and memory profiles for hot paths when the platform supports them.

### Frameworks

- **RED**: rate, errors, duration for request-driven services.
- **USE**: utilization, saturation, errors for resources.
- **Golden signals**: latency, traffic, errors, saturation.

### Alerting and operations

- Every alert has an owner, a threshold, a runbook, and a severity.
- Page only for user-visible or SLO-threatening conditions.
- Separate symptoms from causes.
- Dashboard per SLO and per resource.
- Review error budget and incidents on a regular cadence.

## Resilience

### Dependency protection

- Explicit connect and read timeouts.
- Bounded retries with exponential backoff and jitter.
- Retries only for idempotent operations.
- Circuit breakers with a fallback.
- Bulkheads and separate pools per dependency.
- Load shedding and admission control.
- Graceful degradation with a documented user experience.

### Data protection

- Backups with encryption and cross-zone or cross-region copies.
- Restore drills with measured RTO and RPO.
- Point-in-time recovery where needed.
- Replication lag monitoring.
- Integrity checks and checksums.

### Failure handling

- Failover runbook and tested promotion.
- Split-brain prevention and fencing.
- Queue replay and dead-letter handling.
- Idempotency keys for retried writes.
- Chaos or game-day exercises for critical paths.

### Capacity and degradation

- Headroom for failover, deploys, and growth.
- Documented degradation modes: read-only, cached-only, or reduced features.
- Cost guardrails and traffic caps.

## Review questions

- Which trust boundary is weakest, and what crosses it?
- What can an unauthenticated attacker do, and at what cost?
- What happens when the cache, database, queue, or external dependency fails?
- Which alert fires first when the SLO is at risk?
- Has a restore been tested, and what was the measured RTO?
- Which failure mode causes data loss, and how is it prevented?
- Which control is compensating because the ideal fix is out of scope?
