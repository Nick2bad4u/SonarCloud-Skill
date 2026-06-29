from __future__ import annotations
# pyright: reportUnusedCallResult=false

from pathlib import Path
from typing import Any

import pytest

import sonar_manage_diagnostics
from sonar_manage_api import ProjectContext, RequestSpec


def make_context(tmp_path: Path) -> ProjectContext:
    properties_path = tmp_path / "sonar-project.properties"
    properties_path.write_text(
        "sonar.typescript.tsconfigPaths=tsconfig.json\nsonar.exclusions=**/docs/**\n",
        encoding="utf8",
    )
    return ProjectContext(
        repo_root=tmp_path,
        project_key="project-key",
        organization="org-key",
        base_url="https://sonarcloud.io",
        token="token",
        token_env_name="SONAR_TOKEN",
        auth_scheme="auto",
        sonar_properties_path=properties_path,
    )


def test_scan_local_tsconfigs_classifies_extends(tmp_path: Path) -> None:
    (tmp_path / "tsconfig-base.json").write_text("{}", encoding="utf8")
    (tmp_path / "tsconfig.json").write_text(
        '{"extends": ["./tsconfig-base", "@scope/tsconfig"]}',
        encoding="utf8",
    )
    skipped = tmp_path / "node_modules" / "pkg"
    skipped.mkdir(parents=True)
    (skipped / "tsconfig.json").write_text("{}", encoding="utf8")

    scan = sonar_manage_diagnostics.scan_local_tsconfigs(tmp_path)

    by_path = {item["path"]: item for item in scan}
    assert by_path["tsconfig.json"] == {
        "path": "tsconfig.json",
        "exists": True,
        "extends": ["./tsconfig-base", "@scope/tsconfig"],
        "localExtends": ["tsconfig-base.json"],
        "packageExtends": ["@scope/tsconfig"],
    }
    assert by_path["tsconfig-base.json"] == {
        "path": "tsconfig-base.json",
        "exists": True,
        "extends": [],
    }


def test_describe_tsconfig_reports_parse_error(tmp_path: Path) -> None:
    tsconfig = tmp_path / "tsconfig.json"
    tsconfig.write_text("{", encoding="utf8")

    assert "parseError" in sonar_manage_diagnostics.describe_tsconfig(
        tmp_path,
        tsconfig,
        "tsconfig.json",
    )


def test_investigate_tsconfig_warning_builds_suggestions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(tmp_path)
    (tmp_path / "tsconfig.json").write_text("{}", encoding="utf8")

    def fake_api_request(*, context: ProjectContext, spec: RequestSpec) -> dict[str, Any]:
        del context
        if spec.endpoint == "/api/settings/values":
            return {
                "settings": [
                    {
                        "key": sonar_manage_diagnostics.TS_CONFIG_SETTING_KEY,
                        "value": "tsconfig.json",
                    }
                ]
            }
        return {}

    monkeypatch.setattr(sonar_manage_diagnostics, "api_request", fake_api_request)

    def fake_fetch_ce_component(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"current": {"id": "TASK-1"}}

    def fake_fetch_ce_task(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"task": {"id": "TASK-1"}}

    def fake_fetch_project_analyses(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"analyses": []}

    monkeypatch.setattr(
        sonar_manage_diagnostics,
        "fetch_ce_component",
        fake_fetch_ce_component,
    )
    monkeypatch.setattr(
        sonar_manage_diagnostics,
        "fetch_ce_task",
        fake_fetch_ce_task,
    )
    monkeypatch.setattr(
        sonar_manage_diagnostics,
        "fetch_project_analyses",
        fake_fetch_project_analyses,
    )

    payload = sonar_manage_diagnostics.investigate_tsconfig_warning(context=context)

    assert payload["ceTask"] == {"task": {"id": "TASK-1"}}
    assert payload["rootTsconfigCandidates"] == ["tsconfig.json"]
    assert any("already declares" in suggestion for suggestion in payload["suggestions"])


def test_build_tsconfig_warning_suggestions_for_docs_workspace(tmp_path: Path) -> None:
    context = make_context(tmp_path)

    suggestions = sonar_manage_diagnostics.build_tsconfig_warning_suggestions(
        context=context,
        settings_payload={},
        sonar_properties={},
        local_scan=[
            {
                "path": "docs/docusaurus/tsconfig.json",
                "packageExtends": ["@docusaurus/tsconfig"],
            }
        ],
        local_root_candidates=["tsconfig.json"],
    )

    assert any("@docusaurus/tsconfig" in suggestion for suggestion in suggestions)
