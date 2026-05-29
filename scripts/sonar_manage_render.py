from __future__ import annotations

import json
from typing import Any


def emit_output(payload: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2))
        return

    if not isinstance(payload, dict):
        print(payload)
        return

    print(render_text(payload))


def render_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []

    append_context_fields(lines, payload)
    append_sample_section(
        lines,
        payload.get("openIssues"),
        count_label="Open issues",
        sample_label="Issue sample:",
    )
    append_sample_section(
        lines,
        payload.get("hotspots"),
        count_label="Hotspots",
        sample_label="Hotspot sample:",
    )
    append_quality_gate_status(lines, payload)
    append_quality_gate(lines, payload)
    append_measures(lines, payload)
    append_list_section(lines, payload.get("results"), heading="Results:", key_field=None)
    append_list_section(
        lines,
        payload.get("issues"),
        heading_prefix="Issues returned",
        key_field="key",
    )
    append_list_section(
        lines,
        payload.get("hotspots"),
        heading_prefix="Hotspots returned",
        key_field="key",
    )
    append_list_section(
        lines,
        payload.get("details"),
        heading_prefix="Detail items returned",
        key_field="key",
        skip_empty=True,
    )

    if not lines:
        return json.dumps(payload, indent=2)

    return "\n".join(lines)


def append_context_fields(lines: list[str], payload: dict[str, Any]) -> None:
    for label, key in (
        ("Project", "projectKey"),
        ("Repo", "repoRoot"),
        ("Organization", "organization"),
        ("Base URL", "baseUrl"),
        ("Token env", "tokenEnv"),
        ("Auth scheme", "authScheme"),
    ):
        value = payload.get(key)
        if isinstance(value, str) and value:
            lines.append(f"{label}: {value}")


def append_sample_section(
    lines: list[str],
    section: Any,
    *,
    count_label: str,
    sample_label: str,
) -> None:
    if not isinstance(section, dict):
        return

    lines.append(f"{count_label}: {section.get('total', 0)}")
    sample = section.get("sample")
    if isinstance(sample, list) and sample:
        lines.append(sample_label)
        lines.extend(format_sample_items(sample, key_field="key"))


def append_quality_gate_status(lines: list[str], payload: dict[str, Any]) -> None:
    quality_gate_status = payload.get("qualityGateStatus")
    if not isinstance(quality_gate_status, dict):
        return

    project_status = quality_gate_status.get("projectStatus")
    if isinstance(project_status, dict) and isinstance(project_status.get("status"), str):
        lines.append(f"Quality gate status: {project_status['status']}")


def append_quality_gate(lines: list[str], payload: dict[str, Any]) -> None:
    quality_gate = payload.get("qualityGate")
    if not isinstance(quality_gate, dict):
        return

    name = payload.get("name") or quality_gate.get("name")
    nested = quality_gate.get("qualityGate")
    if not isinstance(name, str) and isinstance(nested, dict):
        name = nested.get("name")
    if isinstance(name, str) and name:
        lines.append(f"Quality gate: {name}")


def append_measures(lines: list[str], payload: dict[str, Any]) -> None:
    measures = payload.get("measures")
    if not isinstance(measures, dict):
        return

    component = measures.get("component")
    if not isinstance(component, dict):
        return

    raw_measures = component.get("measures")
    if isinstance(raw_measures, list):
        lines.append("Measures:")
        lines.extend(format_sample_items(raw_measures, key_field="metric"))


def append_list_section(
    lines: list[str],
    items: Any,
    *,
    key_field: str | None,
    heading: str | None = None,
    heading_prefix: str | None = None,
    skip_empty: bool = False,
) -> None:
    if not isinstance(items, list) or (skip_empty and not items):
        return

    lines.append(heading or f"{heading_prefix}: {len(items)}")
    lines.extend(format_sample_items(items, key_field=key_field))


def format_sample_items(items: list[Any], *, key_field: str | None) -> list[str]:
    return [format_sample_item(item, key_field=key_field) for item in items]


def format_sample_item(item: Any, *, key_field: str | None) -> str:
    if not isinstance(item, dict):
        return f"- {item}"

    return f"- {format_item_identifier(item, key_field)}{' | '.join(format_item_details(item))}"


def format_item_identifier(item: dict[str, Any], key_field: str | None) -> str:
    if key_field is None:
        return ""

    key_value = item.get(key_field)
    if isinstance(key_value, str) and key_value:
        return f"{key_value}: "
    return ""


def format_item_details(item: dict[str, Any]) -> list[str]:
    detail_parts: list[str] = []
    for candidate_key in (
        "status",
        "resolution",
        "component",
        "line",
        "message",
        "name",
        "metric",
        "value",
    ):
        candidate_value = item.get(candidate_key)
        if isinstance(candidate_value, str) and candidate_value:
            detail_parts.append(candidate_value)
        elif isinstance(candidate_value, int):
            detail_parts.append(f"line {candidate_value}")
    return detail_parts
