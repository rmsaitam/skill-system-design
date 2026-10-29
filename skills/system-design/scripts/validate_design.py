#!/usr/bin/env python3
"""Validate a SYSTEM-DESIGN.md artifact against the System Design contract."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

ARTIFACT_RE = re.compile(r"<!--\s*system-design:artifact\s+([^>]*?)-->")
SECTION_RE = re.compile(r"<!--\s*system-design:section\s+([^>]*?)-->")
COUNTS_RE = re.compile(r"<!--\s*system-design:counts\s+([^>]*?)-->")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
HEADING_RE = re.compile(r"^#{1,6}\s+")
PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|TBD|FIXME)\b|\[insert\b|<insert\b|\[placeholder\b|<placeholder\b|lorem ipsum",
    re.IGNORECASE,
)
SECRET_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|AKIA[0-9A-Z]{16}|"
    r"(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*(?!\[REDACTED\])[\"']?[^\s\"']{8,}",
    re.IGNORECASE,
)
FR_RE = re.compile(r"^\s*[-*]\s+\*\*(FR-\d{3})\*\*\s*:", re.MULTILINE)
ADR_HEADING_RE = re.compile(r"^###\s+(ADR-\d{3})\s*:\s*(.+?)\s*$", re.MULTILINE)
QUESTION_HEADING_RE = re.compile(r"^###\s+(Q-\d{3})\s*$", re.MULTILINE)

REQUIRED_SECTIONS = (
    "context",
    "requirements",
    "nfr",
    "slo",
    "capacity",
    "architecture",
    "data",
    "components",
    "flows",
    "tradeoffs",
    "risks",
    "security",
    "observability",
    "resilience",
    "decisions",
    "assumptions",
    "qa",
    "traceability",
    "dod",
)

REQUIRED_METADATA = ("Status", "Date", "Owner", "Artifact language")
ALLOWED_STATUS = ("draft", "in review", "approved", "superseded")
ALLOWED_ADR_STATUS = ("proposed", "accepted", "deprecated", "superseded")
ALLOWED_LEVELS = ("high", "medium", "low")
ALLOWED_CONFIDENCE = ("confirmed", "likely", "assumption")
ID_PREFIXES = ("FR", "NFR", "SLO", "CAP", "COMP", "FLOW", "ADR", "RISK", "THREAT", "Q")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
NUMBER_RE = re.compile(r"\d")
MEASURABLE_RE = re.compile(r"\d|p\d{2}|<=|>=|<|>|%", re.IGNORECASE)


class Issue:
    def __init__(self, level: str, code: str, message: str, location: str = "") -> None:
        self.level = level
        self.code = code
        self.message = message
        self.location = location

    def to_dict(self) -> dict[str, str]:
        return {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "location": self.location,
        }


@dataclass
class Report:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    def error(self, code: str, message: str, location: str = "") -> None:
        self.errors.append(Issue("error", code, message, location))

    def warning(self, code: str, message: str, location: str = "") -> None:
        self.warnings.append(Issue("warning", code, message, location))

    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "pass" if self.ok() else "fail",
            "stats": self.stats,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


def parse_attributes(raw: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_-]*)=(\"[^\"]*\"|'[^']*'|\S+)", raw):
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        attributes[match.group(1)] = value
    return attributes


def strip_comments(text: str) -> str:
    return HTML_COMMENT_RE.sub("", text)


def marker_positions(text: str, pattern: re.Pattern[str]) -> list[tuple[int, int, dict[str, str]]]:
    return [(match.start(), match.end(), parse_attributes(match.group(1))) for match in pattern.finditer(text)]


def section_bodies(text: str, report: Report | None = None) -> dict[str, str]:
    markers = marker_positions(text, SECTION_RE)
    bodies: dict[str, str] = {}
    for index, (start, end, attributes) in enumerate(markers):
        section_id = attributes.get("id", "")
        if report is not None and not section_id:
            report.error("section-missing-id", "A section marker is missing its id.", str(start))
            continue
        if section_id in bodies:
            if report is not None:
                report.error("duplicate-section", f"Duplicate section marker id={section_id}.", section_id)
            continue
        next_start = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        bodies[section_id] = text[end:next_start]
    return bodies


def content_lines(body: str) -> list[str]:
    cleaned = strip_comments(body)
    lines: list[str] = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if HEADING_RE.match(stripped):
            continue
        if stripped.startswith("<!--") or stripped.startswith("-->"):
            continue
        lines.append(stripped)
    return lines


def has_content(body: str) -> bool:
    return bool(content_lines(body))


def metadata_value(text: str, label: str) -> str:
    pattern = re.compile(rf"^-\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def parse_table(body: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells or all(not cell for cell in cells):
            continue
        if all(re.fullmatch(r":?-{2,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    return rows


def ids_from_table(rows: list[list[str]], prefix: str) -> list[str]:
    pattern = re.compile(rf"^{prefix}-\d{{3}}$")
    ids: list[str] = []
    for row in rows:
        if row and pattern.match(row[0]):
            ids.append(row[0])
    return ids


def id_number(identifier: str) -> int:
    return int(identifier.rsplit("-", 1)[1])


def check_sequence(ids: list[str], prefix: str, report: Report, location: str) -> None:
    if not ids:
        report.error("missing-ids", f"No {prefix} items were found in {location}.", location)
        return
    seen: set[str] = set()
    for identifier in ids:
        if identifier in seen:
            report.error("duplicate-id", f"Duplicate ID {identifier} in {location}.", location)
        seen.add(identifier)
    numbers = [id_number(identifier) for identifier in ids]
    expected = list(range(1, len(ids) + 1))
    if numbers != expected:
        report.error(
            "non-sequential-ids",
            f"{prefix} IDs must be sequential from {prefix}-001 in order; found {', '.join(ids)}.",
            location,
        )


def split_adrs(body: str) -> list[tuple[str, str, str]]:
    matches = list(ADR_HEADING_RE.finditer(body))
    records: list[tuple[str, str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        records.append((match.group(1), match.group(2), body[start:end]))
    return records


def field_value(body: str, label: str) -> str:
    pattern = re.compile(rf"^-\s*{re.escape(label)}\s*:\s*(.+?)\s*$", re.MULTILINE | re.IGNORECASE)
    match = pattern.search(body)
    return match.group(1).strip() if match else ""


def split_questions(body: str) -> list[tuple[str, str]]:
    matches = list(QUESTION_HEADING_RE.finditer(body))
    records: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        records.append((match.group(1), body[start:end]))
    return records


def has_diagram(text: str) -> bool:
    lowered = text.lower()
    if "```mermaid" in lowered:
        return True
    if any(token in lowered for token in ("flowchart", "sequencediagram", "statediagram", "c4context", "erdiagram")):
        return True
    if re.search(r"(-->|->|==>|\+--|\|--|\+->|<--)", text):
        return True
    return False


def check_placeholders(text: str, report: Report) -> None:
    for match in PLACEHOLDER_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        report.error("placeholder", f"Unresolved placeholder '{match.group(0)}' at line {line}.", f"line {line}")


def check_secrets(text: str, report: Report) -> None:
    for match in SECRET_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        report.error(
            "possible-secret",
            "A possible secret or credential is present; redact it as [REDACTED].",
            f"line {line}",
        )


def check_artifact_marker(text: str, report: Report) -> bool:
    match = ARTIFACT_RE.search(text)
    if not match:
        report.error(
            "missing-artifact-marker",
            "Missing <!-- system-design:artifact type=design version=1 --> marker.",
        )
        return False
    attributes = parse_attributes(match.group(1))
    if attributes.get("type") != "design":
        report.error("invalid-artifact-type", "Artifact type must be design.")
    if attributes.get("version") != "1":
        report.error("invalid-artifact-version", "Artifact version must be 1.")
    return True


def check_metadata(text: str, report: Report) -> None:
    sections = marker_positions(text, SECTION_RE)
    header = text[: sections[0][0]] if sections else text
    values = {label: metadata_value(header, label) for label in REQUIRED_METADATA}
    for label, value in values.items():
        if not value:
            report.error("missing-metadata", f"Missing metadata label '{label}'.", label)
    status = values.get("Status", "")
    if status and status.lower() not in ALLOWED_STATUS:
        report.error("invalid-status", f"Status '{status}' is not allowed.", "Status")
    date = values.get("Date", "")
    if date and not DATE_RE.match(date):
        report.error("invalid-date", f"Date '{date}' must use YYYY-MM-DD.", "Date")


def check_sections(bodies: dict[str, str], report: Report) -> None:
    for section_id in REQUIRED_SECTIONS:
        if section_id not in bodies:
            report.error("missing-section", f"Missing required section id={section_id}.", section_id)
            continue
        if not has_content(bodies[section_id]):
            report.error("empty-section", f"Section id={section_id} has no content.", section_id)


def check_requirements(bodies: dict[str, str], report: Report) -> tuple[list[str], list[str], list[str]]:
    requirements = bodies.get("requirements", "")
    fr_ids = FR_RE.findall(requirements)
    check_sequence(fr_ids, "FR", report, "requirements")

    nfr_rows = parse_table(bodies.get("nfr", ""))
    nfr_ids = ids_from_table(nfr_rows, "NFR")
    check_sequence(nfr_ids, "NFR", report, "nfr")
    for row in nfr_rows:
        if len(row) < 4 or not re.match(r"^NFR-\d{3}$", row[0]):
            continue
        if not row[2] or not row[3]:
            report.error("nfr-incomplete", f"{row[0]} must include a target and a measurement.", row[0])
            continue
        if not MEASURABLE_RE.search(row[2]):
            report.warning("nfr-unmeasured", f"{row[0]} target has no number or comparator.", row[0])

    slo_rows = parse_table(bodies.get("slo", ""))
    slo_ids = ids_from_table(slo_rows, "SLO")
    check_sequence(slo_ids, "SLO", report, "slo")
    for row in slo_rows:
        if len(row) < 5 or not re.match(r"^SLO-\d{3}$", row[0]):
            continue
        if not all(row[1:5]):
            report.error("slo-incomplete", f"{row[0]} must include SLI, target, window, and error budget.", row[0])
            continue
        if not MEASURABLE_RE.search(row[2]):
            report.warning("slo-unmeasured", f"{row[0]} target has no number or comparator.", row[0])

    return fr_ids, nfr_ids, slo_ids


def check_capacity(bodies: dict[str, str], report: Report) -> list[str]:
    rows = parse_table(bodies.get("capacity", ""))
    ids = ids_from_table(rows, "CAP")
    check_sequence(ids, "CAP", report, "capacity")
    for row in rows:
        if len(row) < 6 or not re.match(r"^CAP-\d{3}$", row[0]):
            continue
        if not all(row[1:6]):
            report.error(
                "capacity-incomplete",
                f"{row[0]} must include metric, inputs, formula, result, and assumption.",
                row[0],
            )
            continue
        if not NUMBER_RE.search(row[4]):
            report.error("capacity-no-number", f"{row[0]} result must contain a number.", row[0])
        if not any(token in row[3] for token in ("=", "/", "*", "+", "-")):
            report.warning("capacity-no-formula", f"{row[0]} formula does not show arithmetic.", row[0])
    return ids


def check_architecture(bodies: dict[str, str], report: Report, require_diagram: bool) -> None:
    architecture = bodies.get("architecture", "")
    if require_diagram and not has_diagram(architecture):
        report.error(
            "missing-diagram",
            "The architecture section must include a Mermaid or ASCII diagram.",
            "architecture",
        )
    if "trust boundar" not in architecture.lower():
        report.warning("missing-trust-boundaries", "The architecture section should state trust boundaries.", "architecture")


def check_data(bodies: dict[str, str], report: Report) -> None:
    data = bodies.get("data", "")
    lowered = data.lower()
    if "sql" not in lowered or "nosql" not in lowered:
        report.error("storage-choice-missing", "The data section must compare SQL and NoSQL.", "data")
    if not any(token in lowered for token in ("rationale", "chosen", "why", "rejected", "trade-off")):
        report.warning("storage-rationale-missing", "The storage choice should include a rationale.", "data")
    if "source of truth" not in lowered:
        report.warning("source-of-truth-missing", "The data section should name the source of truth.", "data")


def check_components_and_flows(bodies: dict[str, str], report: Report) -> tuple[list[str], list[str]]:
    component_rows = parse_table(bodies.get("components", ""))
    component_ids = ids_from_table(component_rows, "COMP")
    check_sequence(component_ids, "COMP", report, "components")
    for row in component_rows:
        if len(row) < 5 or not re.match(r"^COMP-\d{3}$", row[0]):
            continue
        if not all(row[1:5]):
            report.error("component-incomplete", f"{row[0]} must include responsibility, interface, and owner.", row[0])

    flow_rows = parse_table(bodies.get("flows", ""))
    flow_ids = ids_from_table(flow_rows, "FLOW")
    check_sequence(flow_ids, "FLOW", report, "flows")
    for row in flow_rows:
        if len(row) < 5 or not re.match(r"^FLOW-\d{3}$", row[0]):
            continue
        if not all(row[1:5]):
            report.error("flow-incomplete", f"{row[0]} must include trigger, steps, and failure behavior.", row[0])
    return component_ids, flow_ids


def check_risks(bodies: dict[str, str], report: Report) -> tuple[list[str], dict[str, int]]:
    rows = parse_table(bodies.get("risks", ""))
    ids = ids_from_table(rows, "RISK")
    check_sequence(ids, "RISK", report, "risks")
    counts = {level: 0 for level in ALLOWED_LEVELS}
    for row in rows:
        if len(row) < 8 or not re.match(r"^RISK-\d{3}$", row[0]):
            continue
        likelihood, impact, severity, confidence = (cell.lower() for cell in row[2:6])
        if likelihood not in ALLOWED_LEVELS:
            report.error("invalid-likelihood", f"{row[0]} likelihood must be High, Medium, or Low.", row[0])
        if impact not in ALLOWED_LEVELS:
            report.error("invalid-impact", f"{row[0]} impact must be High, Medium, or Low.", row[0])
        if severity not in ALLOWED_LEVELS:
            report.error("invalid-severity", f"{row[0]} severity must be High, Medium, or Low.", row[0])
        else:
            counts[severity] += 1
        if confidence not in ALLOWED_CONFIDENCE:
            report.error(
                "invalid-confidence",
                f"{row[0]} confidence must be Confirmed, Likely, or Assumption.",
                row[0],
            )
        if not row[6] or not row[7]:
            report.error("risk-incomplete", f"{row[0]} must include a mitigation and an owner.", row[0])
        if severity == "high" and confidence == "assumption":
            report.warning("high-risk-assumption", f"{row[0]} is High severity but only an assumption.", row[0])
    return ids, counts


def check_security(bodies: dict[str, str], report: Report) -> list[str]:
    security = bodies.get("security", "").lower()
    for token in ("threat model", "authentication", "authorization", "secret", "rate limit"):
        if token not in security:
            report.error("security-gap", f"The security section must cover '{token}'.", "security")
    rows = parse_table(bodies.get("security", ""))
    threat_ids = ids_from_table(rows, "THREAT")
    check_sequence(threat_ids, "THREAT", report, "security")
    for row in rows:
        if len(row) < 6 or not re.match(r"^THREAT-\d{3}$", row[0]):
            continue
        if not all(row[1:6]):
            report.error("threat-incomplete", f"{row[0]} must include asset, actor, boundary, and control.", row[0])
    return threat_ids


def check_observability(bodies: dict[str, str], report: Report) -> None:
    observability = bodies.get("observability", "").lower()
    for token in ("log", "metric", "trace", "alert"):
        if token not in observability:
            report.error("observability-gap", f"The observability section must cover '{token}'.", "observability")


def check_resilience(bodies: dict[str, str], report: Report) -> None:
    resilience = bodies.get("resilience", "").lower()
    tokens = (
        ("timeout", ("timeout", "time out")),
        ("retry", ("retry", "retries")),
        ("circuit breaker", ("circuit breaker",)),
        ("backup", ("backup",)),
        ("disaster recovery", ("disaster", "recovery")),
    )
    for label, options in tokens:
        if not any(option in resilience for option in options):
            report.error("resilience-gap", f"The resilience section must cover '{label}'.", "resilience")


def check_adrs(bodies: dict[str, str], report: Report, min_adrs: int) -> list[str]:
    records = split_adrs(bodies.get("decisions", ""))
    ids = [record[0] for record in records]
    check_sequence(ids, "ADR", report, "decisions")
    if len(ids) < min_adrs:
        report.error("too-few-adrs", f"At least {min_adrs} ADRs are required; found {len(ids)}.", "decisions")
    for identifier, title, body in records:
        if not title.strip():
            report.error("adr-no-title", f"{identifier} must have a title.", identifier)
        for label in ("Status", "Context", "Decision", "Alternatives", "Consequences"):
            if not field_value(body, label):
                report.error("adr-incomplete", f"{identifier} is missing '{label}'.", identifier)
        status = field_value(body, "Status").lower()
        if status and status not in ALLOWED_ADR_STATUS:
            report.error("adr-invalid-status", f"{identifier} status '{status}' is not allowed.", identifier)
    return ids


def check_tradeoffs(bodies: dict[str, str], report: Report) -> None:
    rows = parse_table(bodies.get("tradeoffs", ""))
    body_rows = [row for row in rows if len(row) >= 4 and row[0].lower() not in {"decision", "id"}]
    if len(rows) < 2 or not body_rows:
        report.error("tradeoffs-missing", "The trade-offs section must contain a decision table.", "tradeoffs")


def check_assumptions(bodies: dict[str, str], report: Report) -> None:
    assumptions = bodies.get("assumptions", "")
    if not any(line.startswith(("-", "*")) for line in content_lines(assumptions)):
        report.warning("assumptions-format", "Assumptions should be a bullet list.", "assumptions")


def check_questions(bodies: dict[str, str], report: Report, min_questions: int) -> list[str]:
    records = split_questions(bodies.get("qa", ""))
    ids = [record[0] for record in records]
    check_sequence(ids, "Q", report, "qa")
    if len(ids) < min_questions:
        report.error("too-few-questions", f"At least {min_questions} answered questions are required; found {len(ids)}.", "qa")
    for identifier, body in records:
        question = field_value(body, "Question")
        answer = field_value(body, "Answer")
        if not question:
            report.error("qa-no-question", f"{identifier} is missing a question.", identifier)
        if not answer:
            report.error("qa-no-answer", f"{identifier} is missing an answer.", identifier)
    return ids


def check_counts(text: str, report: Report, actual: dict[str, int]) -> None:
    match = COUNTS_RE.search(text)
    if not match:
        report.error("missing-counts", "Missing <!-- system-design:counts ... --> marker.")
        return
    attributes = parse_attributes(match.group(1))
    for key, value in actual.items():
        raw = attributes.get(key)
        if raw is None:
            report.error("counts-missing-key", f"The counts marker is missing '{key}'.", "counts")
            continue
        try:
            expected = int(raw)
        except ValueError:
            report.error("counts-invalid", f"The counts marker has a non-integer '{key}={raw}'.", "counts")
            continue
        if expected != value:
            report.error(
                "counts-mismatch",
                f"Counts marker says {key}={expected} but {value} items were found.",
                "counts",
            )


def check_traceability(bodies: dict[str, str], report: Report, requirement_ids: list[str]) -> None:
    rows = parse_table(bodies.get("traceability", ""))
    indexed: dict[str, str] = {}
    for row in rows:
        if row:
            indexed[row[0]] = " | ".join(row)
    for identifier in requirement_ids:
        row = indexed.get(identifier)
        if row is None:
            report.error("traceability-missing", f"{identifier} is missing from the traceability table.", "traceability")
            continue
        if not re.search(r"\b(COMP|FLOW)-\d{3}\b", row):
            report.error(
                "traceability-no-component",
                f"{identifier} must map to at least one component or flow.",
                identifier,
            )
        if not re.search(r"\b(ADR|RISK)-\d{3}\b", row):
            report.error(
                "traceability-no-decision",
                f"{identifier} must map to at least one ADR or risk.",
                identifier,
            )


def check_dod(bodies: dict[str, str], report: Report) -> None:
    dod = bodies.get("dod", "")
    checked = re.findall(r"^\s*[-*]\s+\[[ xX]\]", dod, re.MULTILINE)
    if len(checked) < 5:
        report.error("dod-incomplete", "The definition of done must contain at least five checklist items.", "dod")


def validate_text(text: str, report: Report, *, min_questions: int = 6, min_adrs: int = 3, require_diagram: bool = True) -> Report:
    report.stats.setdefault("files", [])

    if not text.strip():
        report.error("empty-file", "The artifact is empty.")
        return report

    check_artifact_marker(text, report)
    check_metadata(text, report)

    bodies = section_bodies(text, report)
    check_sections(bodies, report)

    fr_ids, nfr_ids, slo_ids = check_requirements(bodies, report)
    cap_ids = check_capacity(bodies, report)
    check_architecture(bodies, report, require_diagram)
    check_data(bodies, report)
    component_ids, flow_ids = check_components_and_flows(bodies, report)
    risk_ids, risk_counts = check_risks(bodies, report)
    threat_ids = check_security(bodies, report)
    check_observability(bodies, report)
    check_resilience(bodies, report)
    adr_ids = check_adrs(bodies, report, min_adrs)
    check_tradeoffs(bodies, report)
    check_assumptions(bodies, report)
    question_ids = check_questions(bodies, report, min_questions)

    actual_counts = {
        "fr": len(fr_ids),
        "nfr": len(nfr_ids),
        "slo": len(slo_ids),
        "adr": len(adr_ids),
        "risk": len(risk_ids),
    }
    check_counts(text, report, actual_counts)
    check_traceability(bodies, report, fr_ids + nfr_ids)
    check_dod(bodies, report)
    check_placeholders(text, report)
    check_secrets(text, report)

    report.stats.update(
        {
            "fr": len(fr_ids),
            "nfr": len(nfr_ids),
            "slo": len(slo_ids),
            "capacity": len(cap_ids),
            "components": len(component_ids),
            "flows": len(flow_ids),
            "adr": len(adr_ids),
            "risk": len(risk_ids),
            "threat": len(threat_ids),
            "questions": len(question_ids),
            "risk_severity": risk_counts,
        }
    )
    return report


def validate_texts(
    texts: Iterable[tuple[str, str]],
    *,
    min_questions: int = 6,
    min_adrs: int = 3,
    require_diagram: bool = True,
) -> Report:
    entries = list(texts)
    if len(entries) == 1:
        name, text = entries[0]
        report = validate_text(
            text,
            Report(),
            min_questions=min_questions,
            min_adrs=min_adrs,
            require_diagram=require_diagram,
        )
        report.stats["files"] = [name]
        return report

    report = Report()
    files: list[str] = []
    for name, text in entries:
        files.append(name)
        local = Report()
        validate_text(
            text,
            local,
            min_questions=min_questions,
            min_adrs=min_adrs,
            require_diagram=require_diagram,
        )
        report.errors.extend(
            Issue(issue.level, issue.code, issue.message, f"{name}:{issue.location}" if issue.location else name)
            for issue in local.errors
        )
        report.warnings.extend(
            Issue(issue.level, issue.code, issue.message, f"{name}:{issue.location}" if issue.location else name)
            for issue in local.warnings
        )
        for key, value in local.stats.items():
            if key == "files":
                continue
            report.stats[f"{name}:{key}"] = value
    report.stats["files"] = files
    return report


def validate_files(
    paths: Iterable[str | Path],
    *,
    min_questions: int = 6,
    min_adrs: int = 3,
    require_diagram: bool = True,
) -> Report:
    texts: list[tuple[str, str]] = []
    report = Report()
    for raw in paths:
        path = Path(raw)
        try:
            texts.append((str(path), path.read_text(encoding="utf-8")))
        except FileNotFoundError:
            report.error("missing-file", f"Missing file: {path}", str(path))
        except OSError as error:
            report.error("unreadable-file", f"Cannot read {path}: {error}", str(path))
    if report.errors:
        return report
    return validate_texts(
        texts,
        min_questions=min_questions,
        min_adrs=min_adrs,
        require_diagram=require_diagram,
    )


def format_issue(issue: Issue) -> str:
    location = f" ({issue.location})" if issue.location else ""
    return f"{issue.level.upper()} [{issue.code}] {issue.message}{location}"


def print_report(report: Report, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        return
    for issue in report.errors:
        print(format_issue(issue), file=sys.stderr)
    for issue in report.warnings:
        print(format_issue(issue), file=sys.stderr)
    stats = report.stats
    summary = ", ".join(
        f"{key}={stats[key]}"
        for key in ("fr", "nfr", "slo", "adr", "risk")
        if key in stats
    )
    print(f"{'PASS' if report.ok() else 'FAIL'}: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    if summary:
        print(f"Items: {summary}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_design.py",
        description="Validate SYSTEM-DESIGN.md against the System Design artifact contract.",
    )
    parser.add_argument("paths", nargs="+", help="One or more SYSTEM-DESIGN.md files")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable JSON report")
    parser.add_argument("--min-questions", type=int, default=6, help="Minimum answered questions")
    parser.add_argument("--min-adrs", type=int, default=3, help="Minimum architecture decision records")
    parser.add_argument(
        "--allow-no-diagram",
        action="store_true",
        help="Do not require a Mermaid or ASCII diagram in the architecture section",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = validate_files(
        args.paths,
        min_questions=args.min_questions,
        min_adrs=args.min_adrs,
        require_diagram=not args.allow_no_diagram,
    )
    print_report(report, args.json)
    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
