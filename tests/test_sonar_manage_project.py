from __future__ import annotations

# pyright: reportUnusedCallResult=false
from pathlib import Path
from typing import Any

import pytest
import sonar_manage_project
from sonar_manage_api import ProjectContext, RequestSpec, SonarCliError


def make_context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        repo_root=tmp_path,
        project_key="project-key",
        organization="org-key",
        base_url="https://sonarcloud.io",
        token="token",
        token_env_name="SONAR_TOKEN",
        auth_scheme="auto",
        sonar_properties_path=None,
    )


def test_fetch_project_payloads_call_expected_endpoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[RequestSpec] = []

    def fake_api_request(*, context: ProjectContext, spec: RequestSpec) -> dict[str, Any]:
        del context
        calls.append(spec)
        return {"endpoint": spec.endpoint, "query": spec.query}

    monkeypatch.setattr(sonar_manage_project, "api_request", fake_api_request)
    context = make_context(tmp_path)

    assert (
        sonar_manage_project.fetch_measures(
            context=context,
            component="component",
            metrics=["coverage", "bugs"],
        )["endpoint"]
        == "/api/measures/component"
    )
    assert (
        sonar_manage_project.fetch_measure_history(
            context=context,
            component="component",
            metrics=["coverage"],
            from_date="2026-01-01",
            to_date=None,
        )["endpoint"]
        == "/api/measures/search_history"
    )
    assert (
        sonar_manage_project.fetch_project_component_info(
            context=context,
            component="component",
        )["endpoint"]
        == "/api/components/show"
    )
    assert (
        sonar_manage_project.fetch_quality_gate_status(
            context=context,
            project_key="project-key",
        )["endpoint"]
        == "/api/qualitygates/project_status"
    )
    assert sonar_manage_project.list_quality_gates(context=context)["query"] == {
        "organization": "org-key",
    }

    assert [call.method for call in calls] == ["GET", "GET", "GET", "GET", "GET"]


def test_quality_gate_and_settings_mutations_support_dry_run(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    assert (
        sonar_manage_project.set_quality_gate(
            context=context,
            project_key="project-key",
            gate_id="42",
            gate_name=None,
            dry_run=True,
        )["result"]["endpoint"]
        == "/api/qualitygates/select"
    )
    assert (
        sonar_manage_project.unset_quality_gate(
            context=context,
            project_key="project-key",
            dry_run=True,
        )["result"]["endpoint"]
        == "/api/qualitygates/deselect"
    )
    assert sonar_manage_project.set_setting_value(
        context=context,
        component="project-key",
        key="sonar.exclusions",
        value="docs/**",
        values=None,
        dry_run=True,
    )["result"]["form"] == {
        "component": "project-key",
        "key": "sonar.exclusions",
        "value": "docs/**",
    }
    assert (
        sonar_manage_project.reset_setting_value(
            context=context,
            component="project-key",
            key="sonar.exclusions",
            dry_run=True,
        )["result"]["endpoint"]
        == "/api/settings/reset"
    )


def test_quality_gate_name_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    context = make_context(tmp_path)

    def fake_list_quality_gates(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"qualitygates": [{"name": "Sonar way", "id": 7}]}

    monkeypatch.setattr(
        sonar_manage_project,
        "list_quality_gates",
        fake_list_quality_gates,
    )

    assert (
        sonar_manage_project.resolve_quality_gate_id(
            context=context,
            gate_id=None,
            gate_name="Sonar way",
        )
        == "7"
    )

    with pytest.raises(SonarCliError, match="Either --gate-id"):
        sonar_manage_project.resolve_quality_gate_id(
            context=context,
            gate_id=None,
            gate_name=None,
        )


def test_profile_tags_and_direct_api_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[RequestSpec] = []

    def fake_api_request(*, context: ProjectContext, spec: RequestSpec) -> dict[str, Any]:
        del context
        calls.append(spec)
        return {"ok": True}

    monkeypatch.setattr(sonar_manage_project, "api_request", fake_api_request)
    context = make_context(tmp_path)

    assert sonar_manage_project.list_quality_profiles(
        context=context,
        project_key="project-key",
        language="py",
        quality_profile=None,
    ) == {"ok": True}
    assert sonar_manage_project.fetch_quality_profile_changelog(
        context=context,
        quality_profile_key="profile",
    ) == {"ok": True}
    assert sonar_manage_project.search_project_tags(
        context=context,
        query_text="quality",
        page_size=10,
    ) == {"ok": True}
    assert sonar_manage_project.set_project_tags(
        context=context,
        project_key="project-key",
        tags=["quality"],
        dry_run=True,
    )["result"]["form"] == {"project": "project-key", "tags": "quality"}
    assert sonar_manage_project.direct_api_call(
        context=context,
        endpoint="/api/custom",
        method="GET",
        query={"ps": "1"},
        form={},
        dry_run=False,
    ) == {"projectKey": "project-key", "response": {"ok": True}}

    assert calls[-1].endpoint == "/api/custom"
