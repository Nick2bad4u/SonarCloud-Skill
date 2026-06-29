from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from sonar_manage_api import (
    RequestSpec,
    SonarCliError,
    api_request,
    parse_properties,
    require_json_object,
)

if TYPE_CHECKING:
    from pathlib import Path

    from sonar_manage_api import ProjectContext

type JsonObject = dict[str, Any]

TS_CONFIG_SETTING_KEY = "sonar.typescript.tsconfigPaths"
DEFAULT_PROJECT_ANALYSES_PAGE_SIZE = 5


def fetch_ce_component(*, context: ProjectContext, component: str) -> JsonObject:
    payload = api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint="/api/ce/component",
            query={"component": component},
        ),
    )
    return require_json_object(payload, "Unexpected CE component payload.")


def fetch_ce_task(*, context: ProjectContext, task_id: str) -> JsonObject:
    payload = api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint="/api/ce/task",
            query={"id": task_id},
        ),
    )
    return require_json_object(payload, "Unexpected CE task payload.")


def fetch_project_analyses(
    *,
    context: ProjectContext,
    project_key: str,
    page: int,
    page_size: int,
) -> JsonObject:
    payload = api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint="/api/project_analyses/search",
            query={
                "project": project_key,
                "p": str(max(1, page)),
                "ps": str(max(1, page_size)),
            },
        ),
    )
    return require_json_object(payload, "Unexpected project analyses payload.")


def investigate_tsconfig_warning(*, context: ProjectContext) -> JsonObject:
    settings_payload = api_request(
        context=context,
        spec=RequestSpec(
            method="GET",
            endpoint="/api/settings/values",
            query={
                "component": context.project_key,
                "keys": TS_CONFIG_SETTING_KEY,
            },
        ),
    )
    ce_component = fetch_ce_component(context=context, component=context.project_key)
    analyses = fetch_project_analyses(
        context=context,
        project_key=context.project_key,
        page=1,
        page_size=DEFAULT_PROJECT_ANALYSES_PAGE_SIZE,
    )
    local_scan = scan_local_tsconfigs(context.repo_root)
    local_root_candidates = list_root_tsconfig_candidates(context.repo_root)
    sonar_properties = (
        parse_properties(context.sonar_properties_path) if context.sonar_properties_path is not None else {}
    )

    ce_task_payload = None
    last_task = ce_component.get("current") or ce_component.get("queue") or ce_component.get("task")
    if isinstance(last_task, dict):
        last_task_object = cast("JsonObject", last_task)
        task_id = last_task_object.get("id")
        if isinstance(task_id, str) and task_id:
            try:
                ce_task_payload = fetch_ce_task(context=context, task_id=task_id)
            except SonarCliError:
                ce_task_payload = None

    settings_object = cast("JsonObject", settings_payload) if isinstance(settings_payload, dict) else {}
    suggestions = build_tsconfig_warning_suggestions(
        context=context,
        settings_payload=settings_object,
        sonar_properties=sonar_properties,
        local_scan=local_scan,
        local_root_candidates=local_root_candidates,
    )

    return {
        "projectKey": context.project_key,
        "organization": context.organization,
        "sonarPropertyValue": sonar_properties.get(TS_CONFIG_SETTING_KEY),
        "settings": settings_payload,
        "ceComponent": ce_component,
        "ceTask": ce_task_payload,
        "projectAnalyses": analyses,
        "localTsconfigs": local_scan,
        "rootTsconfigCandidates": local_root_candidates,
        "suggestions": suggestions,
        "limitations": [
            join_message(
                "The public SonarCloud API surfaces task metadata, but it does",
                "not reliably expose full scanner logs for every analysis.",
            ),
            join_message(
                "If the exact missing tsconfig path is not present in CE task",
                "metadata, you still need the scanner-side logs from CI or local",
                "analysis output.",
            ),
        ],
    }


def join_message(*parts: str) -> str:
    return " ".join(parts)


def scan_local_tsconfigs(repo_root: Path) -> list[JsonObject]:
    results: list[JsonObject] = []
    for file_path in sorted(repo_root.rglob("tsconfig*.json")):
        relative_path = file_path.relative_to(repo_root).as_posix()
        if should_skip_tsconfig_path(relative_path):
            continue

        results.append(describe_tsconfig(repo_root, file_path, relative_path))

    return results


def describe_tsconfig(repo_root: Path, file_path: Path, relative_path: str) -> JsonObject:
    item: JsonObject = {"path": relative_path, "exists": True}
    try:
        payload = json.loads(file_path.read_text(encoding="utf8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:  # pragma: no cover - best effort reporting only
        item["parseError"] = str(error)
        return item

    extends_values = normalize_extends_values(payload.get("extends"))
    item["extends"] = extends_values
    local_extends, missing_local_extends, package_extends = classify_extends_values(
        repo_root, file_path, extends_values
    )
    add_if_present(item, "localExtends", local_extends)
    add_if_present(item, "missingLocalExtends", missing_local_extends)
    add_if_present(item, "packageExtends", package_extends)
    return item


def classify_extends_values(
    repo_root: Path, file_path: Path, extends_values: list[str]
) -> tuple[list[str], list[str], list[str]]:
    local_extends: list[str] = []
    missing_local_extends: list[str] = []
    package_extends: list[str] = []
    for extend_value in extends_values:
        if not is_local_extends_value(extend_value):
            package_extends.append(extend_value)
            continue

        resolved_path = resolve_local_extends(file_path, extend_value)
        resolved_relative = resolved_path.relative_to(repo_root).as_posix()
        target = local_extends if resolved_path.exists() else missing_local_extends
        target.append(resolved_relative)
    return local_extends, missing_local_extends, package_extends


def add_if_present(target: JsonObject, key: str, values: list[str]) -> None:
    if values:
        target[key] = values


def should_skip_tsconfig_path(relative_path: str) -> bool:
    skip_fragments = (
        "node_modules/",
        "/node_modules/",
        ".docusaurus/",
        "build/",
        "dist/",
        "coverage/",
        ".cache/",
        "temp/",
    )
    return any(fragment in relative_path for fragment in skip_fragments)


def normalize_extends_values(raw_extends: Any) -> list[str]:
    if isinstance(raw_extends, str):
        value = raw_extends.strip()
        return [value] if value else []

    if isinstance(raw_extends, list):
        values: list[str] = []
        for item in cast("list[object]", raw_extends):
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    values.append(stripped)
        return values

    return []


def is_local_extends_value(value: str) -> bool:
    return value.startswith((".", "..", "/"))


def resolve_local_extends(tsconfig_path: Path, extend_value: str) -> Path:
    candidate = (tsconfig_path.parent / extend_value).resolve()
    if candidate.suffix == "":
        return candidate.with_suffix(".json")
    return candidate


def list_root_tsconfig_candidates(repo_root: Path) -> list[str]:
    candidates: list[str] = []
    for name in (
        "tsconfig.json",
        "tsconfig.build.json",
        "tsconfig.eslint.json",
        "tsconfig.js.json",
        "tsconfig.vitest-typecheck.json",
    ):
        candidate = repo_root / name
        if candidate.exists():
            candidates.append(name)
    return candidates


def build_tsconfig_warning_suggestions(
    *,
    context: ProjectContext,
    settings_payload: dict[str, Any],
    sonar_properties: dict[str, str],
    local_scan: list[JsonObject],
    local_root_candidates: list[str],
) -> list[str]:
    suggestions: list[str] = []
    configured_setting = find_setting_value(settings_payload, TS_CONFIG_SETTING_KEY)

    property_value = sonar_properties.get(TS_CONFIG_SETTING_KEY)
    if property_value:
        suggestions.append(
            join_message(
                f"The repo already declares {TS_CONFIG_SETTING_KEY}={property_value}.",
                "If warnings persist, the current Sonar analysis is likely stale.",
            )
        )
    elif configured_setting:
        suggestions.append(
            join_message(
                "Project settings currently override",
                f"{TS_CONFIG_SETTING_KEY}={configured_setting}.",
                "Compare that with the repo-local sonar-project.properties value.",
            )
        )
    elif local_root_candidates:
        suggestions.append(
            join_message(
                "If Sonar keeps discovering unwanted tsconfig files, consider setting",
                f"{TS_CONFIG_SETTING_KEY} to only the root configs:",
                ", ".join(local_root_candidates),
            )
        )

    append_docs_workspace_suggestion(suggestions, local_scan)

    if context.sonar_properties_path is not None:
        append_exclusion_suggestions(suggestions, sonar_properties)

    if not suggestions:
        suggestions.append(
            join_message(
                "No obvious local tsconfig mismatch was detected. Check the latest",
                "scanner logs for the exact missing path and compare it with the",
                "local tsconfig graph.",
            )
        )

    return suggestions


def find_setting_value(settings_payload: JsonObject, key: str) -> Any:
    settings_entries = settings_payload.get("settings")
    if not isinstance(settings_entries, list):
        return None

    for setting in cast("list[object]", settings_entries):
        if isinstance(setting, dict):
            setting_object = cast("JsonObject", setting)
            if setting_object.get("key") == key:
                return setting_object.get("value")
    return None


def append_docs_workspace_suggestion(suggestions: list[str], local_scan: list[JsonObject]) -> None:
    docs_workspace_entry = next(
        (item for item in local_scan if item.get("path") == "docs/docusaurus/tsconfig.json"),
        None,
    )
    if not isinstance(docs_workspace_entry, dict):
        return

    package_extends = docs_workspace_entry.get("packageExtends")
    if isinstance(package_extends, list) and "@docusaurus/tsconfig" in package_extends:
        suggestions.append(
            join_message(
                "The docs workspace tsconfig extends @docusaurus/tsconfig, which",
                "is not a repo-local file. If Sonar still scans docs, that",
                "workspace is the most likely source of the missing-tsconfig warning.",
            )
        )


def append_exclusion_suggestions(suggestions: list[str], sonar_properties: dict[str, str]) -> None:
    exclusions = sonar_properties.get("sonar.exclusions", "")
    if "**/docs/**" in exclusions:
        suggestions.append(
            join_message(
                "docs/** is already excluded in sonar-project.properties, so",
                "docs-related tsconfig warnings should disappear after a fresh analysis.",
            )
        )
    if "**/scripts/**" in exclusions and "**/benchmark/**" in exclusions:
        suggestions.append(
            join_message(
                "scripts/** and benchmark/** are already excluded, so remaining",
                "warnings are less likely to come from repo tooling on the next analysis.",
            )
        )
