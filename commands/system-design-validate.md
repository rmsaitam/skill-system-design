---
description: Validate SYSTEM-DESIGN.md against the System Design artifact contract
argument-hint: Optional path to SYSTEM-DESIGN.md
---

# Validate System Design

Load and follow the `system-design` skill for the artifact contract.

Host arguments: `$ARGUMENTS`

Use the host arguments as the artifact path when provided. Otherwise default to `SYSTEM-DESIGN.md` in the current directory.

Resolve the validator script relative to the installed `system-design` skill and run:

```bash
python3 scripts/validate_design.py SYSTEM-DESIGN.md --min-questions 6
```

Use the actual path supplied by the user. Add `--strict` when the user wants warnings treated as errors. Add `--json` when a machine-readable report is useful. Add `--min-adrs 3` when the design must carry at least three decisions.

Report errors first, then warnings, then the requirement, ADR, and risk counts, the capacity summary, and the highest-severity risks. Do not edit the artifact unless the user asks. If asked to fix it, preserve the markers and re-run validation until it passes.
