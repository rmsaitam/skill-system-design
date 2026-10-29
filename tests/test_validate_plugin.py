from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from validate_plugin import main, parse_frontmatter, validate_plugin


ROOT = Path(__file__).resolve().parents[1]


def copy_plugin(tmp_path: Path) -> Path:
    target = tmp_path / "plugin"
    shutil.copytree(
        ROOT,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "__pycache__",
            ".pytest_cache",
            "htmlcov",
            "coverage.xml",
            ".coverage",
            "uv.lock",
        ),
    )
    return target


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_real_plugin_passes() -> None:
    report = validate_plugin(ROOT)
    assert report.ok, [issue.message for issue in report.errors]
    assert report.stats["version"] == "0.1.0"
    assert not report.warnings


def test_cli_json_pass(capsys) -> None:
    exit_code = main([str(ROOT), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["stats"]["version"] == "0.1.0"


def test_cli_strict_fails_on_placeholder_url(tmp_path, capsys) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".claude-plugin/plugin.json"
    data = load_json(path)
    data["author"]["url"] = "https://github.com/your-org/system-design"
    save_json(path, data)
    exit_code = main([str(plugin), "--strict"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "placeholder-url" in captured.err


def test_missing_required_file(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    (plugin / "assets/icon.svg").unlink()
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-file" and "icon.svg" in issue.message for issue in report.errors)


def test_invalid_json(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    (plugin / "plugin.json").write_text("{", encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-json" for issue in report.errors)


def test_duplicate_json_key(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    (plugin / "plugin.json").write_text(
        '{"name":"system-design","name":"system-design","description":"A valid description for the plugin."}',
        encoding="utf-8",
    )
    report = validate_plugin(plugin)
    assert any(issue.code == "duplicate-json-key" for issue in report.errors)


def test_json_root_must_be_object(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    (plugin / "plugin.json").write_text("[]", encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-json-root" for issue in report.errors)


def test_root_manifest_extra_key(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "plugin.json"
    data = load_json(path)
    data["version"] = "0.1.0"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "root-extra-key" for issue in report.errors)


def test_root_manifest_requires_antigravity_schema(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "plugin.json"
    data = load_json(path)
    data["$schema"] = "https://example.com/plugin.json"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-schema" for issue in report.errors)


def test_root_manifest_name_must_match(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "plugin.json"
    data = load_json(path)
    data["name"] = "other"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "wrong-name" for issue in report.errors)


def test_version_mismatch(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".claude-plugin/plugin.json"
    data = load_json(path)
    data["version"] = "9.9.9"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "version-mismatch" for issue in report.errors)


def test_missing_marketplace_source(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".cursor-plugin/marketplace.json"
    data = load_json(path)
    data["plugins"][0]["source"] = "./missing-directory"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-directory" for issue in report.errors)


def test_path_escape_is_rejected(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".cursor-plugin/plugin.json"
    data = load_json(path)
    data["logo"] = "../outside.svg"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "path-escape" for issue in report.errors)


def test_invalid_svg(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    (plugin / "assets/logo.svg").write_text("<not-svg/>", encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-svg" for issue in report.errors)


def test_missing_skill_reference(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "skills/system-design/SKILL.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("references/question-bank.md", "references/missing.md"), encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-reference" for issue in report.errors)


def test_missing_skill_content(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "skills/system-design/SKILL.md"
    path.write_text(path.read_text(encoding="utf-8").replace("SYSTEM-DESIGN.md", "report.md"), encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-skill-content" for issue in report.errors)


def test_missing_command_content(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "commands/system-design-validate.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("validate_design.py", "validator.py"), encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-command-content" for issue in report.errors)


def test_command_requires_argument_hint(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "commands/system-design.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("argument-hint: System idea, service, or architecture scope notes\n", ""), encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-argument-hint" for issue in report.errors)


def test_openai_yaml_requires_skill_invocation(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "agents/openai.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("$system-design", "system-design"), encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-skill-invocation" for issue in report.errors)


def test_openai_yaml_requires_all_fields(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "agents/openai.yaml"
    path.write_text('interface:\n  display_name: "System Design"\n', encoding="utf-8")
    report = validate_plugin(plugin)
    assert sum(issue.code == "missing-openai-field" for issue in report.errors) >= 2


def test_placeholder_in_readme(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nTODO: remove this line.\n", encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "placeholder" for issue in report.errors)


def test_placeholder_in_inline_code_is_ignored(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "README.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nThe token `TODO` is documentation.\n", encoding="utf-8")
    report = validate_plugin(plugin)
    assert report.ok, [issue.message for issue in report.errors]


def test_parse_frontmatter_reads_nested_metadata() -> None:
    values = parse_frontmatter(
        '---\nname: system-design\ndescription: A useful description\nlicense: MIT\nmetadata:\n  author: Example\n  version: "0.1.0"\n---\n\nBody\n'
    )
    assert values is not None
    assert values["name"] == "system-design"
    assert values["author"] == "Example"
    assert values["version"] == "0.1.0"


@pytest.mark.parametrize(
    "relative",
    [
        ".claude-plugin/plugin.json",
        ".codex-plugin/plugin.json",
        ".cursor-plugin/plugin.json",
    ],
)
def test_invalid_semver_is_rejected(tmp_path, relative) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / relative
    data = load_json(path)
    data["version"] = "v1"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-version" for issue in report.errors)


@pytest.mark.parametrize(
    ("relative", "key", "expected_code"),
    [
        (".claude-plugin/plugin.json", "description", "missing-manifest-key"),
        (".codex-plugin/plugin.json", "author", "missing-author"),
        (".cursor-plugin/plugin.json", "license", "missing-license"),
    ],
)
def test_generic_manifest_required_keys(tmp_path, relative, key, expected_code) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / relative
    data = load_json(path)
    data.pop(key)
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == expected_code for issue in report.errors)


@pytest.mark.parametrize(
    "relative",
    [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json"],
)
def test_generic_manifest_name_must_be_system_design(tmp_path, relative) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / relative
    data = load_json(path)
    data["name"] = "other"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "wrong-name" for issue in report.errors)


def test_author_url_must_be_valid(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".codex-plugin/plugin.json"
    data = load_json(path)
    data["author"]["url"] = "not-a-url"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-url" for issue in report.errors)


def test_codex_interface_requires_capabilities_prompts_and_assets(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".codex-plugin/plugin.json"
    data = load_json(path)
    interface = data["interface"]
    interface["capabilities"] = []
    interface["defaultPrompt"] = []
    interface["screenshots"] = "none"
    interface["brandColor"] = "red"
    interface["composerIcon"] = "./assets/missing.svg"
    save_json(path, data)
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert {"missing-capabilities", "missing-prompts", "invalid-screenshots", "invalid-brand-color", "missing-asset"} <= codes


def test_codex_interface_requires_all_fields(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".codex-plugin/plugin.json"
    data = load_json(path)
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
        data["interface"].pop(key)
    save_json(path, data)
    report = validate_plugin(plugin)
    assert sum(issue.code == "invalid-manifest-value" for issue in report.errors) >= 5


def test_codex_interface_requires_object(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".codex-plugin/plugin.json"
    data = load_json(path)
    data["interface"] = "none"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-interface" for issue in report.errors)


def test_claude_marketplace_owner_and_schema(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".claude-plugin/marketplace.json"
    data = load_json(path)
    data.pop("$schema")
    data.pop("owner")
    save_json(path, data)
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "missing-schema" in codes
    assert "missing-owner" in codes


def test_marketplace_requires_plugins(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".cursor-plugin/marketplace.json"
    data = load_json(path)
    data["plugins"] = []
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-plugins" for issue in report.errors)


def test_marketplace_rejects_invalid_plugin_entry(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".cursor-plugin/marketplace.json"
    data = load_json(path)
    data["plugins"] = ["system-design"]
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-plugin-entry" for issue in report.errors)


def test_marketplace_rejects_wrong_name(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".cursor-plugin/marketplace.json"
    data = load_json(path)
    data["name"] = "other"
    data["plugins"][0]["name"] = "other"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert sum(issue.code == "wrong-name" for issue in report.errors) >= 2


def test_cursor_marketplace_requires_owner_and_metadata(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".cursor-plugin/marketplace.json"
    data = load_json(path)
    data.pop("owner")
    data.pop("metadata")
    save_json(path, data)
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "missing-owner" in codes
    assert "missing-metadata" in codes


def test_copilot_version_mismatch(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".github/plugin/marketplace.json"
    data = load_json(path)
    data["metadata"]["version"] = "9.9.9"
    data["plugins"][0]["version"] = "9.9.9"
    save_json(path, data)
    report = validate_plugin(plugin)
    assert sum(issue.code == "version-mismatch" for issue in report.errors) >= 2


def test_copilot_requires_owner_and_metadata(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".github/plugin/marketplace.json"
    data = load_json(path)
    data.pop("owner")
    data["metadata"] = "none"
    save_json(path, data)
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "missing-owner" in codes
    assert "missing-metadata" in codes


def test_codex_marketplace_policy(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".agents/plugins/marketplace.json"
    data = load_json(path)
    plugin_entry = data["plugins"][0]
    plugin_entry["policy"]["installation"] = "DISABLED"
    plugin_entry["policy"]["authentication"] = "NONE"
    plugin_entry.pop("category")
    save_json(path, data)
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "invalid-policy" in codes
    assert "invalid-manifest-value" in codes


def test_codex_marketplace_requires_policy(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".agents/plugins/marketplace.json"
    data = load_json(path)
    data["plugins"][0].pop("policy")
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-policy" for issue in report.errors)


def test_codex_marketplace_requires_interface(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / ".agents/plugins/marketplace.json"
    data = load_json(path)
    data.pop("interface")
    save_json(path, data)
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-interface" for issue in report.errors)


def test_skill_requires_frontmatter(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "skills/system-design/SKILL.md"
    path.write_text("# No frontmatter\n", encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-frontmatter" for issue in report.errors)


def test_skill_rejects_weak_description_and_version(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "skills/system-design/SKILL.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"description: .*", "description: Short.", text, count=1)
    text = text.replace('version: "0.1.0"', 'version: "9.9.9"')
    path.write_text(text, encoding="utf-8")
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "weak-description" in codes
    assert "version-mismatch" in codes


def test_skill_rejects_wrong_name_and_license(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "skills/system-design/SKILL.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("name: system-design", "name: other", 1)
    text = text.replace("license: MIT", "license: Apache", 1)
    path.write_text(text, encoding="utf-8")
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "wrong-name" in codes
    assert "missing-license" in codes


def test_skill_requires_author(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    path = plugin / "skills/system-design/SKILL.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("  author: Reginaldo (rmsaitam)\n", "", 1)
    path.write_text(text, encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "missing-author" for issue in report.errors)


def test_docs_and_tooling_checks(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    readme = plugin / "README.md"
    readme.write_text("# Empty\n", encoding="utf-8")
    license_path = plugin / "LICENSE"
    license_path.write_text("Not a license\n", encoding="utf-8")
    pyproject = plugin / "pyproject.toml"
    pyproject.write_text("[project]\nname = \"x\"\n", encoding="utf-8")
    makefile = plugin / "Makefile"
    makefile.write_text("test:\n\ttrue\n", encoding="utf-8")
    ci = plugin / ".github/workflows/ci.yml"
    ci.write_text("name: CI\n", encoding="utf-8")
    gitignore = plugin / ".gitignore"
    gitignore.write_text("__pycache__/\n", encoding="utf-8")
    report = validate_plugin(plugin)
    codes = {issue.code for issue in report.errors}
    assert "missing-readme-content" in codes
    assert "invalid-license" in codes
    assert "missing-pyproject-content" in codes
    assert "missing-make-target" in codes
    assert "missing-ci-step" in codes
    assert "missing-gitignore" in codes


def test_invalid_toml_is_rejected(tmp_path) -> None:
    plugin = copy_plugin(tmp_path)
    (plugin / "pyproject.toml").write_text("[project\nname = x\n", encoding="utf-8")
    report = validate_plugin(plugin)
    assert any(issue.code == "invalid-toml" for issue in report.errors)
