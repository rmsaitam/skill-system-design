# System Design

[![skills.sh](https://skills.sh/b/rmsaitam/skill-system-design)](https://skills.sh/rmsaitam/skill-system-design)

System Design is a principal-level architecture plugin for AI coding agents. It runs a staged design engagement, challenges missing requirements, estimates capacity, compares architecture options, and produces one traceable, validated artifact:

- `SYSTEM-DESIGN.md`: context, functional and non-functional requirements, SLOs, capacity planning, high-level design, data model, components, flows, trade-offs, risks, security, observability, resilience, ADRs, assumptions, interview answers, and traceability.

The design is expressed with Mermaid or ASCII diagrams and grounded in real patterns: CAP, PACELC, CQRS, event sourcing, saga, outbox, idempotency, backpressure, bulkhead, and circuit breaker. Every decision includes an alternative and a trade-off. Risks use three severities: **High**, **Medium**, and **Low**.

Repository: https://github.com/rmsaitam/skill-system-design

## Supported agents

| Agent | Manifest |
| --- | --- |
| Claude Code | `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` |
| Codex | `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json` |
| Cursor | `.cursor-plugin/plugin.json` and `.cursor-plugin/marketplace.json` |
| GitHub Copilot CLI | `.github/plugin/marketplace.json` with the root `plugin.json` |
| Antigravity | root `plugin.json` |

All agents use the shared skill at `skills/system-design/SKILL.md` and the commands in `commands/`.

## Install

### skills.sh

```bash
# Install into the current project after choosing the agents interactively
npx skills add rmsaitam/skill-system-design

# Install globally into the user home config for every project, skipping prompts
npx skills add rmsaitam/skill-system-design -g -y

# List the skill without installing it
npx skills add rmsaitam/skill-system-design --list
```

### Claude Code

From a published marketplace:

```text
/plugin marketplace add rmsaitam/skill-system-design
/plugin install system-design@system-design
```

From a local checkout:

```text
/plugin marketplace add /absolute/path/to/skill-system-design
/plugin install system-design@system-design
```

### Codex

```bash
codex plugin marketplace add rmsaitam/skill-system-design
codex plugin install system-design@system-design
```

### GitHub Copilot CLI

```bash
copilot plugin marketplace add rmsaitam/skill-system-design
copilot plugin install system-design@system-design
```

### Cursor

Install the plugin from a marketplace that lists this repository, or point Cursor at a local plugin directory containing this repository. Cursor reads `.cursor-plugin/plugin.json`, the shared `skills/` directory, and `commands/`.

### Antigravity

Install the repository root as a plugin. Antigravity reads the root `plugin.json` directly.

Command syntax varies by agent version. When a command is unavailable, use the agent's plugin marketplace UI and select the `system-design` plugin.

## Usage

Start a design:

```text
/system-design Design a multi-tenant URL shortener for 10 million monthly active users
```

The skill follows ten gates:

1. Inspect the workspace and reuse known architecture facts.
2. Interview the user in rounds of at most five questions.
3. Present two or three architecture options and wait for approval.
4. Establish measurable requirements and capacity estimates.
5. Draw the high-level design, components, and flows.
6. Model the data and justify the storage choice.
7. Expose trade-offs, bottlenecks, single points of failure, and risks.
8. Cover security, observability, and resilience.
9. Write and validate `SYSTEM-DESIGN.md`.
10. Report the result and propose the next step.

Critique an existing architecture:

```text
/system-design-critique Review docs/ARCHITECTURE.md for bottlenecks and failure modes
```

Validate an existing artifact:

```text
/system-design-validate
/system-design-validate docs/SYSTEM-DESIGN.md
```

## Artifact contract

### SYSTEM-DESIGN.md

The file starts with:

```html
<!-- system-design:artifact type=design version=1 -->
```

It must contain section markers for `context`, `requirements`, `nfr`, `slo`, `capacity`, `architecture`, `data`, `components`, `flows`, `tradeoffs`, `risks`, `security`, `observability`, `resilience`, `decisions`, `assumptions`, `qa`, `traceability`, and `dod`.

The counts marker must match the parsed items:

```html
<!-- system-design:counts fr=3 nfr=4 slo=3 adr=3 risk=4 -->
```

Stable ID families:

| Family | Meaning |
| --- | --- |
| `FR-001` | Functional requirement |
| `NFR-001` | Non-functional requirement |
| `SLO-001` | Service level objective |
| `CAP-001` | Capacity estimate |
| `COMP-001` | Component |
| `FLOW-001` | Primary or failure flow |
| `ADR-001` | Architecture decision record |
| `RISK-001` | Architecture or delivery risk |
| `THREAT-001` | Threat model entry |
| `Q-001` | Interview question |

The design requires:

- measurable targets and a measurement method for every NFR and SLO;
- inputs, formula, result, and assumption for every capacity estimate;
- a Mermaid or ASCII diagram in the architecture section;
- a SQL versus NoSQL comparison and a storage rationale;
- at least three ADRs with alternatives and consequences;
- a risk register with likelihood, impact, severity, confidence, mitigation, and owner;
- a threat model, security controls, observability signals, and resilience mechanisms;
- every FR and NFR mapped to a component or flow and to an ADR or risk;
- at least six answered questions;
- no placeholders and no secrets.

## Validation

Run the design validator:

```bash
python3 skills/system-design/scripts/validate_design.py SYSTEM-DESIGN.md --min-questions 6
```

Options:

```text
--min-questions 6     Minimum answered interview questions.
--min-adrs 3          Minimum architecture decision records.
--strict              Treat warnings as failures.
--json                Emit a machine-readable report.
--allow-no-diagram    Do not require a Mermaid or ASCII diagram.
```

The validator uses only the Python standard library. It checks markers, metadata, required sections, ID families and ordering, NFR and SLO measurability, capacity completeness, diagram presence, storage rationale, component and flow completeness, ADR fields, risk calibration, security and observability coverage, traceability, counts, placeholders, and unredacted secret patterns.

If Python is unavailable, use `skills/system-design/references/validation-checklist.md`.

## Design guidance

The skill ships with focused references:

| Reference | Purpose |
| --- | --- |
| `question-bank.md` | Architecture interview in rounds, with decision rules. |
| `design-template.md` | Complete `SYSTEM-DESIGN.md` structure and a valid example. |
| `capacity-planning.md` | QPS, storage, bandwidth, cache, nodes, queues, availability, and cost formulas. |
| `architecture-patterns.md` | Styles, components, messaging, caching, scaling, multi-region, and anti-patterns. |
| `data-modeling.md` | SQL versus NoSQL, indexing, partitioning, replication, consistency, and multi-tenancy. |
| `tradeoffs-baseline.md` | CAP, PACELC, risk calibration, heuristics, and ADR format. |
| `security-observability-checklist.md` | Threat model, controls, SLIs, SLOs, and resilience. |
| `validation-checklist.md` | Manual fallback for the validator. |

## Development

Prerequisites:

- Python 3.10 or newer.
- `uv` for the test environment.

The published plugin has no Python runtime dependencies. Its validators use only the standard library. For development:

```bash
uv sync --extra dev
source .venv/bin/activate
pytest -q
```

Run the tests and the coverage gate:

```bash
make coverage
```

Validate the plugin structure:

```bash
make validate
```

Run everything:

```bash
make check
```

The test suite requires at least 80 percent branch coverage over both validator scripts.

## Repository layout

```text
.
├── plugin.json
├── .claude-plugin/
├── .codex-plugin/
├── .cursor-plugin/
├── .agents/plugins/
├── .github/
├── agents/openai.yaml
├── assets/
├── commands/
├── skills/system-design/
│   ├── SKILL.md
│   ├── references/
│   └── scripts/validate_design.py
├── scripts/validate_plugin.py
└── tests/
```

## Method and limits

- The default is an interactive design process, not a one-shot answer.
- Confirmed facts are separated from assumptions and open questions.
- Vendor benchmarks, prices, and limits are cited or marked as assumptions.
- The artifact never contains secrets, credentials, customer data, or personal data.
- The plugin does not modify application code, repositories, or infrastructure.
- The plugin contains instructions, Markdown commands, and Python validators. It does not include MCP servers, hooks, network calls, telemetry, or credentials.

## License

MIT. See `LICENSE`.
