#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
BRAND_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
PLACEHOLDER_RE = re.compile(
    r"\b(?:TODO|TBD|FIXME)\b|\[insert\b|<insert\b|\[placeholder\b|<placeholder\b",
    re.IGNORECASE,
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
YAML_PAIR_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$")

REQUIRED_FILES = (
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json",
    ".cursor-plugin/marketplace.json",
    ".github/plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
    "agents/openai.yaml",
    "assets/icon.svg",
    "assets/logo.svg",
    "commands/system-design.md",
    "commands/system-design-critique.md",
    "commands/system-design-validate.md",
    "skills/system-design/SKILL.md",
    "skills/system-design/references/question-bank.md",
    "skills/system-design/references/design-template.md",
    "skills/system-design/references/capacity-planning.md",
    "skills/system-design/references/architecture-patterns.md",
    "skills/system-design/references/data-modeling.md",
    "skills/system-design/references/tradeoffs-baseline.md",
    "skills/system-design/references/security-observability-checklist.md",
    "skills/system-design/references/validation-checklist.md",
    "skills/system-design/scripts/validate_design.py",
    "scripts/validate_plugin.py",
    "tests/conftest.py",
    "tests/test_validate_design.py",
    "tests/test_validate_plugin.py",
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "Makefile",
    ".gitignore",
    ".github/workflows/ci.yml",
)
SCAN_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml"}
EXCLUDED_PARTS = {".git", ".pytest_cache", "__pycache__", ".venv", "tests", "fixtures"}


class DuplicateKeyError(ValueError):
    pass


@dataclass
class Issue:
    level: str
    code: str
    message: str
    location: str = ""


@dataclass
class Report:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    stats: dict[str, object] = field(default_factory=dict)

    def error(self, code: str, message: str, location: str = "") -> None:
        self.errors.append(Issue("error", code, message, location))

    def warning(self, code: str, message: str, location: str = "") -> None:
        self.warnings.append(Issue("warning", code, message, location))

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "status": "pass" if self.ok else "fail",
            "stats": self.stats,
            "errors": [issue.__dict__ for issue in self.errors],
            "warnings": [issue.__dict__ for issue in self.warnings],
        }


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def load_json(path: Path, report: Report) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)
    except FileNotFoundError:
        report.error("missing-file", f"Missing file: {path}", str(path))
        return None
    except DuplicateKeyError as error:
        report.error("duplicate-json-key", f"Duplicate JSON key {error} in {path}.", str(path))
        return None
    except json.JSONDecodeError as error:
        report.error("invalid-json", f"Invalid JSON in {path}: {error}.", str(path))
        return None
    except OSError as error:
        report.error("unreadable-file", f"Cannot read {path}: {error}.", str(path))
        return None
    if not isinstance(data, dict):
        report.error("invalid-json-root", f"{path} must contain a JSON object.", str(path))
        return None
    return data


def read_text(path: Path, report: Report) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        report.error("missing-file", f"Missing file: {path}", str(path))
    except OSError as error:
        report.error("unreadable-file", f"Cannot read {path}: {error}.", str(path))
    return ""


def expected_version(root: Path, report: Report) -> str:
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return ""
    text = read_text(pyproject, report)
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            report.error("invalid-toml", f"Invalid pyproject.toml: {error}.", "pyproject.toml")
            return ""
        version = data.get("project", {}).get("version", "")
        return version if isinstance(version, str) else ""
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def require_keys(
    data: dict[str, object],
    keys: Iterable[str],
    location: str,
    report: Report,
) -> None:
    for key in keys:
        if key not in data or data[key] in ("", None, [], {}):
            report.error("missing-manifest-key", f"{location} is missing {key}.", location)


def require_string(
    data: dict[str, object],
    key: str,
    location: str,
    report: Report,
    minimum: int = 1,
) -> str:
    value = data.get(key)
    if not isinstance(value, str) or len(value.strip()) < minimum:
        report.error(
            "invalid-manifest-value",
            f"{location} needs a string {key} of at least {minimum} characters.",
            location,
        )
        return ""
    return value.strip()


def check_url(value: str, location: str, report: Report) -> None:
    if not value:
        return
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        report.error("invalid-url", f"{location} contains an invalid URL: {value}.", location)
    if "your-org" in value:
        report.warning("placeholder-url", f"{location} still contains a placeholder URL.", location)


def resolve_path(root: Path, value: str) -> Path:
    return (root / value).resolve()


def check_relative_path(
    root: Path,
    value: object,
    location: str,
    report: Report,
    expect_directory: bool = False,
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        report.error("missing-path", f"{location} needs a path.", location)
        return None
    candidate = resolve_path(root, value)
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        report.error("path-escape", f"{location} points outside the plugin root.", location)
        return None
    if expect_directory and not candidate.is_dir():
        report.error("missing-directory", f"{location} points to missing directory {value}.", location)
        return None
    if not expect_directory and not candidate.is_file():
        report.error("missing-asset", f"{location} points to missing file {value}.", location)
        return None
    return candidate


def check_required_files(root: Path, report: Report) -> None:
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file():
            report.error("missing-file", f"Missing required file: {relative}.", relative)
            continue
        try:
            if path.stat().st_size == 0:
                report.error("empty-file", f"Required file is empty: {relative}.", relative)
        except OSError as error:
            report.error("unreadable-file", f"Cannot inspect {relative}: {error}.", relative)


def check_root_manifest(root: Path, report: Report) -> None:
    data = load_json(root / "plugin.json", report)
    if data is None:
        return
    allowed = {"$schema", "name", "description"}
    extra = sorted(set(data) - allowed)
    if extra:
        report.error(
            "root-extra-key",
            f"Root plugin.json contains keys rejected by the minimal Antigravity schema: {', '.join(extra)}.",
            "plugin.json",
        )
    schema = require_string(data, "$schema", "plugin.json", report)
    if schema and not schema.startswith("https://antigravity.google/schemas/"):
        report.error("invalid-schema", "Root plugin.json has an unexpected schema URL.", "plugin.json")
    name = require_string(data, "name", "plugin.json", report)
    if name and name != "system-design":
        report.error("wrong-name", "Root plugin name must be system-design.", "plugin.json")
    require_string(data, "description", "plugin.json", report, minimum=30)


def check_generic_manifest(
    root: Path,
    relative: str,
    report: Report,
    version: str,
    require_license: bool = True,
) -> dict[str, object] | None:
    data = load_json(root / relative, report)
    if data is None:
        return None
    require_keys(data, ("name", "version", "description"), relative, report)
    name = require_string(data, "name", relative, report)
    if name and name != "system-design":
        report.error("wrong-name", f"{relative} name must be system-design.", relative)
    manifest_version = require_string(data, "version", relative, report)
    if manifest_version:
        if not SEMVER_RE.match(manifest_version):
            report.error("invalid-version", f"{relative} version must be semantic.", relative)
        if version and manifest_version != version:
            report.error(
                "version-mismatch",
                f"{relative} version {manifest_version} does not match {version}.",
                relative,
            )
    require_string(data, "description", relative, report, minimum=30)
    if require_license and data.get("license") != "MIT":
        report.error("missing-license", f"{relative} must declare the MIT license.", relative)
    author = data.get("author")
    if isinstance(author, dict):
        require_string(author, "name", f"{relative}:author", report)
        check_url(str(author.get("url", "")), f"{relative}:author", report)
    elif isinstance(author, str) and author.strip():
        pass
    else:
        report.error("missing-author", f"{relative} needs an author.", relative)
    for key in ("homepage", "repository"):
        if key in data:
            check_url(str(data[key]), f"{relative}:{key}", report)
    return data


def check_marketplace_common(
    root: Path,
    relative: str,
    report: Report,
) -> tuple[dict[str, object] | None, list[object]]:
    data = load_json(root / relative, report)
    if data is None:
        return None, []
    name = require_string(data, "name", relative, report)
    if name and name != "system-design":
        report.error("wrong-name", f"{relative} marketplace name must be system-design.", relative)
    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        report.error("missing-plugins", f"{relative} needs a non-empty plugins list.", relative)
        return data, []
    for index, plugin in enumerate(plugins):
        location = f"{relative}:plugins[{index}]"
        if not isinstance(plugin, dict):
            report.error("invalid-plugin-entry", f"{location} must be an object.", location)
            continue
        plugin_name = require_string(plugin, "name", location, report)
        if plugin_name and plugin_name != "system-design":
            report.error("wrong-name", f"{location} name must be system-design.", location)
        require_string(plugin, "description", location, report, minimum=30)
    return data, plugins


def check_marketplace_source(
    root: Path,
    plugin: dict[str, object],
    location: str,
    report: Report,
) -> None:
    source = plugin.get("source")
    if isinstance(source, str):
        check_relative_path(root, source, f"{location}:source", report, expect_directory=True)
    elif isinstance(source, dict):
        if source.get("source") != "local":
            report.error("invalid-source", f"{location} source must be local.", location)
        check_relative_path(root, source.get("path"), f"{location}:source.path", report, expect_directory=True)
    else:
        report.error("missing-source", f"{location} needs a source.", location)


def check_claude(root: Path, report: Report, version: str) -> None:
    check_generic_manifest(root, ".claude-plugin/plugin.json", report, version)
    data, plugins = check_marketplace_common(root, ".claude-plugin/marketplace.json", report)
    if data is not None:
        schema = data.get("$schema")
        if not isinstance(schema, str) or "anthropic.com" not in schema:
            report.error(
                "missing-schema",
                ".claude-plugin/marketplace.json needs the Claude marketplace schema.",
                ".claude-plugin/marketplace.json",
            )
        owner = data.get("owner")
        if not isinstance(owner, dict) or not owner.get("name"):
            report.error("missing-owner", "Claude marketplace needs an owner name.", ".claude-plugin/marketplace.json")
        else:
            check_url(str(owner.get("url", "")), ".claude-plugin/marketplace.json:owner", report)
    for index, plugin in enumerate(plugins):
        if isinstance(plugin, dict):
            check_marketplace_source(root, plugin, f".claude-plugin/marketplace.json:plugins[{index}]", report)


def check_codex(root: Path, report: Report, version: str) -> None:
    data = check_generic_manifest(root, ".codex-plugin/plugin.json", report, version)
    if data is None:
        return
    check_relative_path(root, data.get("skills"), ".codex-plugin/plugin.json:skills", report, expect_directory=True)
    interface = data.get("interface")
    if not isinstance(interface, dict):
        report.error("missing-interface", "Codex manifest needs an interface object.", ".codex-plugin/plugin.json")
        return
    location = ".codex-plugin/plugin.json:interface"
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        require_string(interface, key, location, report)
    capabilities = interface.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        report.error("missing-capabilities", f"{location} needs capabilities.", location)
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not prompts:
        report.error("missing-prompts", f"{location} needs default prompts.", location)
    elif any(not isinstance(prompt, str) or not prompt.strip() for prompt in prompts):
        report.error("invalid-prompt", f"{location} has an invalid default prompt.", location)
    website = str(interface.get("websiteURL", ""))
    check_url(website, f"{location}:websiteURL", report)
    brand = str(interface.get("brandColor", ""))
    if not BRAND_COLOR_RE.match(brand):
        report.error("invalid-brand-color", f"{location} brandColor must be a hex color.", location)
    for key in ("composerIcon", "logo"):
        check_relative_path(root, interface.get(key), f"{location}:{key}", report)
    screenshots = interface.get("screenshots")
    if not isinstance(screenshots, list):
        report.error("invalid-screenshots", f"{location} screenshots must be a list.", location)


def check_cursor(root: Path, report: Report, version: str) -> None:
    data = check_generic_manifest(root, ".cursor-plugin/plugin.json", report, version)
    if data is not None:
        check_relative_path(root, data.get("skills"), ".cursor-plugin/plugin.json:skills", report, expect_directory=True)
        check_relative_path(root, data.get("commands"), ".cursor-plugin/plugin.json:commands", report, expect_directory=True)
        check_relative_path(root, data.get("logo"), ".cursor-plugin/plugin.json:logo", report)
    marketplace, plugins = check_marketplace_common(root, ".cursor-plugin/marketplace.json", report)
    if marketplace is not None:
        owner = marketplace.get("owner")
        if not isinstance(owner, dict) or not owner.get("name"):
            report.error("missing-owner", "Cursor marketplace needs an owner name.", ".cursor-plugin/marketplace.json")
        metadata = marketplace.get("metadata")
        if not isinstance(metadata, dict) or not metadata.get("description"):
            report.error(
                "missing-metadata",
                "Cursor marketplace needs metadata.description.",
                ".cursor-plugin/marketplace.json",
            )
    for index, plugin in enumerate(plugins):
        if isinstance(plugin, dict):
            check_marketplace_source(root, plugin, f".cursor-plugin/marketplace.json:plugins[{index}]", report)


def check_copilot(root: Path, report: Report, version: str) -> None:
    data, plugins = check_marketplace_common(root, ".github/plugin/marketplace.json", report)
    if data is not None:
        owner = data.get("owner")
        if not isinstance(owner, dict) or not owner.get("name"):
            report.error("missing-owner", "Copilot marketplace needs an owner name.", ".github/plugin/marketplace.json")
        metadata = data.get("metadata")
        if not isinstance(metadata, dict):
            report.error("missing-metadata", "Copilot marketplace needs metadata.", ".github/plugin/marketplace.json")
        else:
            metadata_version = str(metadata.get("version", ""))
            if version and metadata_version != version:
                report.error(
                    "version-mismatch",
                    f"Copilot marketplace version {metadata_version} does not match {version}.",
                    ".github/plugin/marketplace.json",
                )
            require_string(metadata, "description", ".github/plugin/marketplace.json:metadata", report, minimum=30)
    for index, plugin in enumerate(plugins):
        if isinstance(plugin, dict):
            location = f".github/plugin/marketplace.json:plugins[{index}]"
            plugin_version = str(plugin.get("version", ""))
            if version and plugin_version != version:
                report.error("version-mismatch", f"{location} version does not match {version}.", location)
            check_marketplace_source(root, plugin, location, report)


def check_codex_marketplace(root: Path, report: Report) -> None:
    data, plugins = check_marketplace_common(root, ".agents/plugins/marketplace.json", report)
    if data is not None:
        interface = data.get("interface")
        if not isinstance(interface, dict) or not interface.get("displayName"):
            report.error("missing-interface", "Codex marketplace needs interface.displayName.", ".agents/plugins/marketplace.json")
    for index, plugin in enumerate(plugins):
        if not isinstance(plugin, dict):
            continue
        location = f".agents/plugins/marketplace.json:plugins[{index}]"
        check_marketplace_source(root, plugin, location, report)
        policy = plugin.get("policy")
        if not isinstance(policy, dict):
            report.error("missing-policy", f"{location} needs a policy.", location)
        else:
            if policy.get("installation") != "AVAILABLE":
                report.error("invalid-policy", f"{location} installation policy must be AVAILABLE.", location)
            if policy.get("authentication") != "ON_INSTALL":
                report.error("invalid-policy", f"{location} authentication policy must be ON_INSTALL.", location)
        require_string(plugin, "category", location, report)


def parse_frontmatter(text: str) -> dict[str, str] | None:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    values: dict[str, str] = {}
    for line in match.group(1).splitlines():
        pair = YAML_PAIR_RE.match(line)
        if pair:
            values[pair.group(1)] = pair.group(2).strip().strip('"')
    return values


def check_skill(root: Path, report: Report, version: str) -> None:
    relative = "skills/system-design/SKILL.md"
    text = read_text(root / relative, report)
    if not text:
        return
    frontmatter = parse_frontmatter(text)
    if frontmatter is None:
        report.error("missing-frontmatter", f"{relative} needs YAML frontmatter.", relative)
        return
    if frontmatter.get("name") != "system-design":
        report.error("wrong-name", f"{relative} frontmatter name must be system-design.", relative)
    description = frontmatter.get("description", "")
    if len(description) < 80:
        report.error("weak-description", f"{relative} description is too short.", relative)
    if frontmatter.get("license") != "MIT":
        report.error("missing-license", f"{relative} must declare the MIT license.", relative)
    if version and frontmatter.get("version") != version:
        report.error("version-mismatch", f"{relative} version does not match {version}.", relative)
    if not frontmatter.get("author"):
        report.error("missing-author", f"{relative} needs an author.", relative)
    for link in LINK_RE.findall(text):
        if link.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (root / relative).parent / link
        if not target.exists():
            report.error("missing-reference", f"{relative} references missing {link}.", relative)
    for required in (
        "validate_design.py",
        "SYSTEM-DESIGN.md",
        "Mermaid",
        "capacity",
        "SLO",
        "trade-off",
        "High",
        "Medium",
        "Low",
        "threat model",
    ):
        if required not in text:
            report.error("missing-skill-content", f"{relative} must mention {required}.", relative)


def check_openai_yaml(root: Path, report: Report) -> None:
    relative = "agents/openai.yaml"
    text = read_text(root / relative, report)
    if not text:
        return
    values: dict[str, str] = {}
    for line in text.splitlines():
        pair = YAML_PAIR_RE.match(line)
        if pair:
            values[pair.group(1)] = pair.group(2).strip().strip('"')
    for key in ("display_name", "short_description", "default_prompt"):
        if not values.get(key):
            report.error("missing-openai-field", f"{relative} needs {key}.", relative)
    if "$system-design" not in values.get("default_prompt", ""):
        report.error("missing-skill-invocation", f"{relative} default_prompt must invoke $system-design.", relative)


def check_svg(root: Path, relative: str, report: Report) -> None:
    path = root / relative
    if not path.is_file():
        return
    try:
        tree = ET.parse(path)
    except ET.ParseError as error:
        report.error("invalid-svg", f"{relative} is not valid XML: {error}.", relative)
        return
    if tree.getroot().tag.split("}")[-1] != "svg":
        report.error("invalid-svg", f"{relative} root element must be svg.", relative)


def check_command(root: Path, relative: str, report: Report, expected_text: str) -> None:
    text = read_text(root / relative, report)
    if not text:
        return
    frontmatter = parse_frontmatter(text)
    if frontmatter is None:
        report.error("missing-frontmatter", f"{relative} needs command frontmatter.", relative)
        return
    if len(frontmatter.get("description", "")) < 20:
        report.error("weak-description", f"{relative} needs a useful description.", relative)
    if not frontmatter.get("argument-hint"):
        report.error("missing-argument-hint", f"{relative} needs an argument hint.", relative)
    for required in ("system-design", expected_text):
        if required not in text:
            report.error("missing-command-content", f"{relative} must mention {required}.", relative)


def check_commands(root: Path, report: Report) -> None:
    check_command(root, "commands/system-design.md", report, "Do not implement")
    check_command(root, "commands/system-design-critique.md", report, "trade-offs")
    check_command(root, "commands/system-design-validate.md", report, "validate_design.py")


def check_docs(root: Path, report: Report, version: str) -> None:
    readme = read_text(root / "README.md", report)
    for required in (
        "System Design",
        "Install",
        "SYSTEM-DESIGN.md",
        "Mermaid",
        "capacity",
        "SLO",
        "trade-off",
        "High",
        "Medium",
        "Low",
        "MIT",
        "validate_design.py",
    ):
        if required not in readme:
            report.error("missing-readme-content", f"README.md must mention {required}.", "README.md")
    license_text = read_text(root / "LICENSE", report)
    if not license_text.startswith("MIT License"):
        report.error("invalid-license", "LICENSE must start with 'MIT License'.", "LICENSE")
    if "Copyright (c) 2026" not in license_text:
        report.error("invalid-license", "LICENSE needs the 2026 copyright line.", "LICENSE")

    pyproject = read_text(root / "pyproject.toml", report)
    for required in ("requires-python", "pytest", "pytest-cov", "fail_under = 80"):
        if required not in pyproject:
            report.error("missing-pyproject-content", f"pyproject.toml must contain {required}.", "pyproject.toml")
    if version and f'version = "{version}"' not in pyproject:
        report.error("version-mismatch", f"pyproject.toml does not declare version {version}.", "pyproject.toml")

    makefile = read_text(root / "Makefile", report)
    for target in ("test:", "coverage:", "validate:"):
        if target not in makefile:
            report.error("missing-make-target", f"Makefile is missing the {target} target.", "Makefile")

    ci = read_text(root / ".github/workflows/ci.yml", report)
    for required in ("pytest", "validate_plugin.py", "coverage"):
        if required not in ci:
            report.error("missing-ci-step", f"CI workflow must run {required}.", ".github/workflows/ci.yml")

    gitignore = read_text(root / ".gitignore", report)
    if ".coverage" not in gitignore:
        report.error("missing-gitignore", ".gitignore must ignore coverage output.", ".gitignore")


def strip_fenced_code(text: str) -> str:
    return re.sub(r"(?ms)^```.*?^```\s*$", "", text)


def strip_inline_code(text: str) -> str:
    return re.sub(r"`[^`\n]+`", "", text)


def strip_comments(text: str) -> str:
    return re.sub(r"(?s)<!--.*?-->", "", text)


def scan_placeholders(root: Path, report: Report) -> None:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in SCAN_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        relative = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        cleaned = strip_inline_code(strip_fenced_code(strip_comments(text)))
        for match in PLACEHOLDER_RE.finditer(cleaned):
            line = cleaned.count("\n", 0, match.start()) + 1
            report.error(
                "placeholder",
                f"{relative} contains unresolved placeholder {match.group(0)!r}.",
                f"{relative}:{line}",
            )
        if path.suffix == ".json":
            load_json(path, report)


def validate_plugin(root: Path = Path("."), strict: bool = False) -> Report:
    root = root.resolve()
    report = Report()
    check_required_files(root, report)
    version = expected_version(root, report)
    report.stats["version"] = version
    if version and not SEMVER_RE.match(version):
        report.error("invalid-version", "pyproject.toml version must be semantic.", "pyproject.toml")
    check_root_manifest(root, report)
    check_claude(root, report, version)
    check_codex(root, report, version)
    check_cursor(root, report, version)
    check_copilot(root, report, version)
    check_codex_marketplace(root, report)
    check_skill(root, report, version)
    check_openai_yaml(root, report)
    check_svg(root, "assets/icon.svg", report)
    check_svg(root, "assets/logo.svg", report)
    check_commands(root, report)
    check_docs(root, report, version)
    scan_placeholders(root, report)
    report.stats["errors"] = len(report.errors)
    report.stats["warnings"] = len(report.warnings)
    report.stats["strict"] = strict
    return report


def format_issue(issue: Issue) -> str:
    location = f" ({issue.location})" if issue.location else ""
    return f"[{issue.level.upper()}] {issue.code}: {issue.message}{location}"


def print_report(report: Report, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return
    for issue in report.errors:
        print(format_issue(issue), file=sys.stderr)
    for issue in report.warnings:
        print(format_issue(issue), file=sys.stderr)
    status = "PASS" if report.ok else "FAIL"
    print(
        f"{status}: plugin version {report.stats.get('version') or 'unknown'}, "
        f"{report.stats.get('errors', 0)} errors, {report.stats.get('warnings', 0)} warnings."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the System Design plugin structure.")
    parser.add_argument("root", nargs="?", default=".", help="Plugin repository root")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="Emit a JSON report")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    report = validate_plugin(Path(args.root), strict=args.strict)
    print_report(report, args.json)
    if report.errors:
        return 1
    if args.strict and report.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
