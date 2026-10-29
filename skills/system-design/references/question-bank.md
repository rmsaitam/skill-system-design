# Question Bank

Use this bank to run the System Design interview. Ask at most five questions per round. Prefer structured multiple-choice questions when the host supports them. Otherwise ask numbered questions and wait for the answers.

Do not read the entire bank to the user. Select the next questions that reduce the most architectural uncertainty. Cover every category before writing `SYSTEM-DESIGN.md`. When a category does not apply, record why in the artifact instead of skipping it silently.

## Round 1: Problem, users, and scope

### Problem and outcome

- What system or capability is being designed?
- Describe it in one sentence.
- Which concrete problem does it solve, and for whom?
- What happens if the team does nothing?
- What is the smallest useful version of this system?

### Users and journeys

- Who are the primary, secondary, and operator users?
- What are the top three user journeys?
- Which journey dominates traffic?
- Which journey is the most critical for the business?
- What is explicitly out of scope for this design?

### Success

- Which measurable outcome proves the design works?
- What is the business-critical quality attribute: latency, availability, consistency, throughput, durability, or cost?
- What must not get worse?

## Round 2: Scale and performance

### Traffic

- How many daily active users, devices, or clients?
- How many actions per user per day?
- What is the read/write ratio?
- What is the peak-to-average factor, or the busiest hour?
- How fast is the user base expected to grow per year?
- Are traffic patterns spiky, seasonal, or batch-driven?

### Payload and data

- What is the average and maximum request and response size?
- How many records are created per day?
- How large is each record?
- How long is data retained?
- What is the total data volume today and in one, three, and five years?

### Latency and throughput

- What are the p50, p95, and p99 latency targets?
- Which operations are interactive and which can be asynchronous?
- What is the throughput target per endpoint or event type?
- What is the acceptable tail latency during peak or failure?

## Round 3: Availability, consistency, and recovery

### Availability

- What is the availability target: 99.9, 99.95, 99.99, or higher?
- What is the cost of one minute of downtime?
- Are there maintenance windows?
- Does the system need multi-region or multi-zone deployment?

### Consistency

- Which data must be strongly consistent?
- Which data can be eventually consistent?
- What happens if a user reads stale data?
- Are read-your-writes or monotonic reads required?
- Are there invariants that must never be violated?

### Recovery

- What are the RTO and RPO?
- How often must backups run, and where are they stored?
- Has a restore been tested?
- What is the disaster recovery strategy: backup and restore, pilot light, warm standby, or active-active?

## Round 4: Data, integrations, and security

### Data model

- Which entities, relationships, and invariants exist?
- What is the source of truth for each important record?
- Which access patterns dominate?
- Are there hot keys, large objects, or unbounded collections?
- What must be exportable or deletable?
- Is there personal, financial, health, or otherwise sensitive data?

### Integrations

- Which external services, APIs, webhooks, or files are involved?
- What happens when an integration is unavailable?
- Are there rate limits, costs, or contractual constraints?
- Which events must be idempotent and replayable?
- Is there an existing message broker or event platform?

### Security and compliance

- Which threats matter most: account takeover, injection, abuse, data exfiltration, insider risk, or denial of service?
- Who authenticates, and how?
- Which roles and permissions exist?
- How are tenants isolated?
- Where do secrets live, and how are they rotated?
- Which regulations, contracts, or data residency rules apply?
- What must be logged, and what must never be logged?

## Round 5: Architecture constraints and operations

### Stack and platform

- Is there an existing stack, cloud, or platform that must be used?
- Is the deployment on-premises, cloud, hybrid, or edge?
- Are containers, Kubernetes, serverless, or virtual machines mandated?
- Which languages, frameworks, databases, and brokers are already supported?
- Are there licensing or vendor constraints?

### Team and delivery

- How many engineers will build and operate the system?
- Which team owns each domain?
- What is the release cadence?
- Is there a deadline or a fixed launch date?
- What is the budget for infrastructure per month?
- Is the team willing to operate the added complexity?

### Operations

- Who is on call?
- Which observability stack already exists?
- Which SLOs and dashboards are mandatory?
- What is the rollback and feature-flag strategy?
- Which failure drills or chaos experiments are acceptable?

## Round 6: Trade-offs and risks

- What is the biggest technical risk?
- What is the biggest product or adoption risk?
- Which assumption, if wrong, would force a redesign?
- Which component is most likely to become the bottleneck?
- What would make the team stop or reshape the design?
- Which decision is hardest to reverse, and why?

## Decision rules

- Prefer measurable answers over adjectives. Replace "fast" with a percentile and a target. Replace "high availability" with an availability target and a recovery objective. Replace "many users" with a volume, ratio, and growth assumption.
- When the user does not know, propose two or three concrete options with trade-offs and ask the user to choose.
- When the user delegates the decision, record it as an assumption and ask for approval at Gate 3.
- Do not ask about technology before the problem, users, scale, and constraints are clear.
- Do not ask more than five questions at once. Group related questions.
- Do not repeat a question that the repository or a previous answer already answers.
- Do not infer a requirement from silence. Mark it as an assumption or an open decision.
- Stop when the remaining questions would not change the architecture, capacity model, risk register, or definition of done.

## Minimum coverage before writing the design

Record an answer or an explicit non-applicability note for:

- problem, users, and product promise;
- must-have and out-of-scope scope;
- traffic, peak factor, read/write ratio, payload, and growth;
- latency percentiles and throughput targets;
- availability target, RTO, and RPO;
- consistency requirements and invariants;
- data entities, access patterns, retention, and sensitivity;
- external integrations and failure behavior;
- authentication, authorization, tenancy, secrets, and compliance;
- stack, cloud, deployment, and vendor constraints;
- team size, budget, and deadline;
- observability, on-call, rollback, and failure drills;
- top technical and product risks;
- the decisions that are hardest to reverse.
