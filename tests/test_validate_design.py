from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from validate_design import (
    SECTION_RE,
    Report,
    format_issue,
    has_diagram,
    main,
    marker_positions,
    metadata_value,
    parse_attributes,
    parse_table,
    section_bodies,
    validate_files,
    validate_text,
    validate_texts,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "valid_design.md"


def valid_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def run(text: str, **kwargs) -> Report:
    report = Report()
    validate_text(text, report, **kwargs)
    return report


def codes(report: Report) -> set[str]:
    return {issue.code for issue in report.errors}


def warning_codes(report: Report) -> set[str]:
    return {issue.code for issue in report.warnings}


def replace_once(text: str, old: str, new: str) -> str:
    assert old in text
    return text.replace(old, new, 1)


def test_valid_fixture_passes_strict() -> None:
    report = validate_files([FIXTURE])
    assert report.ok(), [issue.message for issue in report.errors]
    assert not report.warnings
    assert report.stats["fr"] == 3
    assert report.stats["nfr"] == 4
    assert report.stats["slo"] == 3
    assert report.stats["adr"] == 3
    assert report.stats["risk"] == 4
    assert report.stats["questions"] == 6
    assert report.stats["risk_severity"] == {"high": 2, "medium": 2, "low": 0}


def test_valid_fixture_cli_json(capsys) -> None:
    exit_code = main([str(FIXTURE), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["stats"]["fr"] == 3


def test_cli_strict_fails_on_warning(capsys) -> None:
    text = replace_once(valid_text(), "p99 <= 50 ms at peak", "fast enough")
    path = Path(__file__).resolve().parent / "fixtures" / "warning_design.md"
    path.write_text(text, encoding="utf-8")
    try:
        exit_code = main([str(path), "--strict"])
    finally:
        path.unlink()
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "nfr-unmeasured" in captured.err


def test_empty_text() -> None:
    report = run("")
    assert "empty-file" in codes(report)


def test_missing_artifact_marker() -> None:
    text = valid_text().replace("<!-- system-design:artifact type=design version=1 -->", "")
    report = run(text)
    assert "missing-artifact-marker" in codes(report)


def test_wrong_artifact_type_and_version() -> None:
    text = valid_text().replace("type=design version=1", "type=report version=2")
    report = run(text)
    assert {"invalid-artifact-type", "invalid-artifact-version"} <= codes(report)


def test_missing_metadata_and_invalid_values() -> None:
    text = valid_text()
    text = replace_once(text, "- Status: Draft\n", "")
    text = replace_once(text, "- Date: 2026-01-01", "- Date: 01/01/2026")
    report = run(text)
    assert "missing-metadata" in codes(report)
    assert "invalid-date" in codes(report)


def test_invalid_status() -> None:
    text = valid_text().replace("- Status: Draft", "- Status: Maybe", 1)
    report = run(text)
    assert "invalid-status" in codes(report)


def test_missing_section_and_empty_section() -> None:
    text = valid_text().replace("<!-- system-design:section id=context -->", "<!-- system-design:section id=other -->")
    text = text.replace("## 7. Data Model and Storage", "## 7. Data Model and Storage\n", 1)
    report = run(text)
    assert "missing-section" in codes(report)
    assert "duplicate-section" not in codes(report)


def test_empty_required_section() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=context -->")
    end = text.index("<!-- system-design:section id=requirements -->")
    text = text[:start] + "<!-- system-design:section id=context -->\n## 1. Context\n\n" + text[end:]
    report = run(text)
    assert "empty-section" in codes(report)


def test_section_missing_id_and_duplicate() -> None:
    text = valid_text().replace(
        "<!-- system-design:section id=context -->",
        "<!-- system-design:section -->\n<!-- system-design:section id=requirements -->",
        1,
    )
    report = run(text)
    assert "section-missing-id" in codes(report)
    assert "duplicate-section" in codes(report)


def test_missing_fr() -> None:
    text = valid_text()
    text = text.replace("- **FR-002**: A visitor must be redirected from a valid short code to the original URL with an HTTP redirect.\n", "")
    report = run(text)
    assert "non-sequential-ids" in codes(report)


def test_duplicate_fr() -> None:
    text = valid_text().replace(
        "- **FR-003**: The system must record a click event for analytics without blocking the redirect.",
        "- **FR-002**: A duplicate requirement.",
        1,
    )
    report = run(text)
    assert "duplicate-id" in codes(report)


def test_nfr_incomplete_and_unmeasured() -> None:
    text = valid_text().replace("| NFR-001 | Redirect latency | p99 <= 50 ms at peak | Load test and production latency histogram |", "| NFR-001 | Redirect latency | | |", 1)
    text = text.replace("| NFR-002 | Redirect availability | 99.95% monthly | Synthetic probes and SLO dashboard |", "| NFR-002 | Redirect availability | often | Synthetic probes |", 1)
    report = run(text)
    assert "nfr-incomplete" in codes(report)
    assert "nfr-unmeasured" in warning_codes(report)


def test_slo_incomplete_and_unmeasured() -> None:
    text = valid_text().replace("| SLO-001 | Successful redirects / valid redirect requests | >= 99.95% | 30 days | 21.6 minutes |", "| SLO-001 | Success | | | |", 1)
    text = text.replace("| SLO-002 | Redirect requests faster than 50 ms | >= 99% | 30 days | 1% of requests |", "| SLO-002 | Latency | good | 30 days | 1% |", 1)
    report = run(text)
    assert "slo-incomplete" in codes(report)
    assert "slo-unmeasured" in warning_codes(report)


def test_capacity_incomplete_no_number_and_no_formula() -> None:
    text = valid_text().replace(
        "| CAP-001 | Peak redirect QPS | 10M MAU, 30 redirects per user per day, peak factor 5 | 10,000,000 * 30 * 5 / 86,400 | 17,361 QPS | Traffic is spread outside the peak |",
        "| CAP-001 | Peak redirect QPS | 10M MAU | unknown | many | Traffic is spread |",
        1,
    )
    text = text.replace(
        "| CAP-002 | Peak create QPS | 10M MAU, 3 creates per user per day, peak factor 5 | 10,000,000 * 3 * 5 / 86,400 | 1,736 QPS | Creates follow the same peak factor |",
        "| CAP-002 | Peak create QPS | 10M MAU | arithmetic here | 1736 | Assumption |",
        1,
    )
    report = run(text)
    assert "capacity-no-number" in codes(report)
    assert "capacity-no-formula" in warning_codes(report)


def test_capacity_missing_row() -> None:
    text = valid_text()
    for line in list(text.splitlines()):
        if line.startswith("| CAP-003 |"):
            text = text.replace(line + "\n", "", 1)
    report = run(text)
    assert "non-sequential-ids" in codes(report)


def test_architecture_requires_diagram() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=architecture -->")
    end = text.index("<!-- system-design:section id=data -->")
    section = "<!-- system-design:section id=architecture -->\n## 6. High-Level Architecture\n\n- Trust boundaries: edge and data.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "missing-diagram" in codes(report)
    relaxed = run(text, require_diagram=False)
    assert "missing-diagram" not in codes(relaxed)


def test_architecture_trust_boundary_warning() -> None:
    text = valid_text().replace("- Trust boundaries: client to edge, edge to API, API to data stores, and API to the event queue.", "", 1)
    report = run(text)
    assert "missing-trust-boundaries" in warning_codes(report)


def test_data_requires_sql_nosql_rationale_and_source() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=data -->")
    end = text.index("<!-- system-design:section id=components -->")
    section = "<!-- system-design:section id=data -->\n## 7. Data Model and Storage\n\n- A relational store is used.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "storage-choice-missing" in codes(report)
    assert "storage-rationale-missing" in warning_codes(report)
    assert "source-of-truth-missing" in warning_codes(report)


def test_components_and_flows_incomplete() -> None:
    text = valid_text().replace(
        "| COMP-001 | Edge Load Balancer | TLS termination, routing, and rate limiting | HTTPS | Platform |",
        "| COMP-001 | Edge Load Balancer | | | |",
        1,
    )
    text = text.replace(
        "| FLOW-001 | Create link | User submits a URL | Validate, check quota, allocate code, insert, return short URL | Return a typed error and do not partially write |",
        "| FLOW-001 | Create link | | | |",
        1,
    )
    report = run(text)
    assert "component-incomplete" in codes(report)
    assert "flow-incomplete" in codes(report)


def test_invalid_risk_values_and_high_assumption() -> None:
    text = valid_text().replace(
        "| RISK-004 | Egress cost grows faster than traffic | Medium | Medium | Medium | Assumption | Per-tenant quotas, cost alerts, and response compression | Platform |",
        "| RISK-004 | Egress cost grows | Often | Medium | Medium | Assumption | Quotas | Platform |",
        1,
    )
    text = text.replace(
        "| RISK-001 | Hot link causes cache stampede | Medium | High | High | Likely | Request coalescing, jittered TTL, and per-key limits | Link team |",
        "| RISK-001 | Hot link causes cache stampede | Medium | High | High | Assumption | Request coalescing | Link team |",
        1,
    )
    report = run(text)
    assert "invalid-likelihood" in codes(report)
    assert "high-risk-assumption" in warning_codes(report)


@pytest.mark.parametrize(
    ("needle", "replacement", "expected"),
    [
        ("Medium | High | High | Likely", "Medium | High | High | Maybe", "invalid-confidence"),
        ("Medium | High | High | Likely", "Medium | High | Critical | Likely", "invalid-severity"),
        ("Medium | High | High | Likely", "Medium | Severe | High | Likely", "invalid-impact"),
    ],
)
def test_invalid_risk_columns(needle: str, replacement: str, expected: str) -> None:
    text = replace_once(valid_text(), needle, replacement)
    report = run(text)
    assert expected in codes(report)


def test_risk_missing_mitigation_and_owner() -> None:
    text = valid_text().replace(
        "| RISK-002 | Primary database is a single point of failure | Low | High | High | Confirmed | Synchronous standby, tested failover, and connection retry | Data platform |",
        "| RISK-002 | Primary database is a single point of failure | Low | High | High | Confirmed | | |",
        1,
    )
    report = run(text)
    assert "risk-incomplete" in codes(report)


def test_security_gaps_and_threat_incomplete() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=security -->")
    end = text.index("<!-- system-design:section id=observability -->")
    section = "<!-- system-design:section id=security -->\n## 12. Security\n\n- Nothing here.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "security-gap" in codes(report)
    assert "missing-ids" in codes(report)


def test_threat_incomplete() -> None:
    text = valid_text().replace(
        "| THREAT-001 | Short-code enumeration and scraping | Link inventory | External attacker | Client to edge | Rate limit by IP and API key, anomaly detection, and random codes |",
        "| THREAT-001 | Enumeration | Link inventory | | | |",
        1,
    )
    report = run(text)
    assert "threat-incomplete" in codes(report)


def test_observability_gaps() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=observability -->")
    end = text.index("<!-- system-design:section id=resilience -->")
    section = "<!-- system-design:section id=observability -->\n## 13. Observability\n\n- Dashboards only.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "observability-gap" in codes(report)


def test_resilience_gaps() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=resilience -->")
    end = text.index("<!-- system-design:section id=decisions -->")
    section = "<!-- system-design:section id=resilience -->\n## 14. Resilience\n\n- We hope for the best.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "resilience-gap" in codes(report)


def test_adr_incomplete_and_invalid_status() -> None:
    text = valid_text().replace("- Status: Accepted\n- Context: Link creation needs uniqueness constraints, transactional writes, and relational integrity, while the write volume is modest.", "- Status: Maybe\n- Context: Link creation needs uniqueness.", 1)
    text = text.replace("- Alternatives: A wide-column NoSQL store and an event-sourced store were evaluated.\n", "", 1)
    report = run(text)
    assert "adr-incomplete" in codes(report)
    assert "adr-invalid-status" in codes(report)


def test_too_few_adrs() -> None:
    text = valid_text()
    start = text.index("### ADR-003:")
    end = text.index("<!-- system-design:section id=assumptions -->")
    text = text[:start] + text[end:]
    report = run(text)
    assert "too-few-adrs" in codes(report) or "non-sequential-ids" in codes(report)


def test_tradeoffs_missing() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=tradeoffs -->")
    end = text.index("<!-- system-design:section id=risks -->")
    section = "<!-- system-design:section id=tradeoffs -->\n## 10. Trade-offs\n\n- It depends.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "tradeoffs-missing" in codes(report)


def test_assumptions_format_warning() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=assumptions -->")
    end = text.index("<!-- system-design:section id=qa -->")
    section = "<!-- system-design:section id=assumptions -->\n## 16. Assumptions\n\nThere are assumptions.\n\n"
    text = text[:start] + section + text[end:]
    report = run(text)
    assert "assumptions-format" in warning_codes(report)


def test_questions_missing_and_incomplete() -> None:
    text = valid_text()
    start = text.index("### Q-005")
    end = text.index("<!-- system-design:section id=traceability -->")
    text = text[:start] + text[end:]
    text = text.replace("- Answer: 99.95% monthly, which yields a 21.6-minute error budget.", "", 1)
    report = run(text)
    assert "too-few-questions" in codes(report)
    assert "qa-no-answer" in codes(report)


def test_question_missing_and_no_question_text() -> None:
    text = valid_text().replace("- Question: What is the read/write ratio?", "", 1)
    report = run(text)
    assert "qa-no-question" in codes(report)


def test_counts_missing_mismatch_and_invalid() -> None:
    base = valid_text()
    missing = base.replace("<!-- system-design:counts fr=3 nfr=4 slo=3 adr=3 risk=4 -->", "", 1)
    assert "missing-counts" in codes(run(missing))

    mismatch = base.replace("fr=3 nfr=4 slo=3 adr=3 risk=4", "fr=9 nfr=4 slo=3 adr=3 risk=4", 1)
    assert "counts-mismatch" in codes(run(mismatch))

    invalid = base.replace("fr=3 nfr=4 slo=3 adr=3 risk=4", "fr=three nfr=4 slo=3 adr=3 risk=4", 1)
    assert "counts-invalid" in codes(run(invalid))

    missing_key = base.replace("fr=3 nfr=4 slo=3 adr=3 risk=4", "fr=3 nfr=4 slo=3 adr=3", 1)
    assert "counts-missing-key" in codes(run(missing_key))


def test_traceability_missing_component_and_decision() -> None:
    text = valid_text().replace(
        "| FR-001 | Create a short link | COMP-003, FLOW-001 | ADR-001, RISK-002 |",
        "| FR-001 | Create a short link | | |",
        1,
    )
    report = run(text)
    assert "traceability-no-component" in codes(report)
    assert "traceability-no-decision" in codes(report)

    missing = valid_text().replace("| FR-003 | Record click analytics | COMP-006, COMP-007, FLOW-003 | ADR-003, RISK-003 |\n", "", 1)
    assert "traceability-missing" in codes(run(missing))


def test_dod_incomplete() -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=dod -->")
    section = "<!-- system-design:section id=dod -->\n## 19. Definition of Done\n\n- [ ] One item.\n"
    text = text[:start] + section
    report = run(text)
    assert "dod-incomplete" in codes(report)


def test_placeholders_and_secrets() -> None:
    text = valid_text().replace("- Owner: Architecture team", "- Owner: Architecture team\n- Note: TODO finish this", 1)
    text = text.replace("- Open question: What is the approved monthly infrastructure budget ceiling?", "- Password: supersecretvalue", 1)
    report = run(text)
    assert "placeholder" in codes(report)
    assert "possible-secret" in codes(report)


def test_redacted_secret_is_allowed() -> None:
    text = valid_text().replace(
        "- Open question: What is the approved monthly infrastructure budget ceiling?",
        "- Password: [REDACTED]",
        1,
    )
    report = run(text)
    assert "possible-secret" not in codes(report)


def test_validate_texts_combines_reports() -> None:
    report = validate_texts([("good.md", valid_text()), ("bad.md", "")])
    assert report.stats["files"] == ["good.md", "bad.md"]
    assert any(issue.code == "empty-file" for issue in report.errors)
    assert any(issue.location.startswith("bad.md") for issue in report.errors)


def test_validate_files_missing_and_unreadable(tmp_path) -> None:
    missing = tmp_path / "missing.md"
    report = validate_files([missing])
    assert "missing-file" in codes(report)

    unreadable = tmp_path / "unreadable.md"
    unreadable.mkdir()
    report = validate_files([unreadable])
    assert "unreadable-file" in codes(report)


def test_parse_attributes_and_metadata() -> None:
    attributes = parse_attributes('type=design version="1" id=\'context\'')
    assert attributes == {"type": "design", "version": "1", "id": "context"}
    text = dedent(
        """\
        - Status: Approved
        - owner: Architecture team
        - Date: 2026-01-01
        """
    )
    assert metadata_value(text, "Status") == "Approved"
    assert metadata_value(text, "Owner") == "Architecture team"
    assert metadata_value(text, "Missing") == ""


def test_parse_table_handles_separator_and_empty_rows() -> None:
    body = dedent(
        """\
        | ID | Name |
        | --- | --- |
        | FR-001 | First |
        |  |  |
        text
        """
    )
    rows = parse_table(body)
    assert rows == [["ID", "Name"], ["FR-001", "First"]]


def test_section_bodies_and_markers() -> None:
    text = dedent(
        """\
        <!-- system-design:section id=a -->
        A
        <!-- system-design:section id=b -->
        B
        """
    )
    report = Report()
    bodies = section_bodies(text, report)
    assert bodies == {"a": "\nA\n", "b": "\nB\n"}
    positions = marker_positions(text, SECTION_RE)
    assert len(positions) == 2
    assert not report.errors


def test_has_diagram_variants() -> None:
    assert has_diagram("```mermaid\nflowchart LR\nA --> B\n```")
    assert has_diagram("```\nA -> B\n```")
    assert has_diagram("flowchart TD")
    assert not has_diagram("No diagram here.")


def test_format_issue_with_and_without_location() -> None:
    report = run("")
    issue = report.errors[0]
    assert "[" in format_issue(issue)
    assert "(" not in format_issue(issue)


def test_cli_allow_no_diagram(capsys, tmp_path) -> None:
    text = valid_text()
    start = text.index("<!-- system-design:section id=architecture -->")
    end = text.index("<!-- system-design:section id=data -->")
    section = "<!-- system-design:section id=architecture -->\n## 6. High-Level Architecture\n\n- Trust boundaries: edge and data.\n\n"
    path = tmp_path / "design.md"
    path.write_text(text[:start] + section + text[end:], encoding="utf-8")
    assert main([str(path)]) == 1
    assert main([str(path), "--allow-no-diagram"]) == 0
    capsys.readouterr()


def test_cli_missing_file(capsys, tmp_path) -> None:
    exit_code = main([str(tmp_path / "missing.md")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "missing-file" in captured.err


def test_cli_json_failure(capsys, tmp_path) -> None:
    path = tmp_path / "design.md"
    path.write_text("", encoding="utf-8")
    exit_code = main([str(path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 1
    assert payload["status"] == "fail"


def test_min_adrs_and_min_questions_flags(capsys) -> None:
    assert main([str(FIXTURE), "--min-adrs", "4"]) == 1
    capsys.readouterr()
    assert main([str(FIXTURE), "--min-questions", "7"]) == 1
    capsys.readouterr()
    assert main([str(FIXTURE), "--min-adrs", "2", "--min-questions", "5"]) == 0
    capsys.readouterr()
