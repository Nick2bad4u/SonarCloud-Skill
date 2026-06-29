from __future__ import annotations
# pyright: reportUnusedCallResult=false

import argparse
from pathlib import Path

import pytest

import manage_sonar_findings
from sonar_manage_api import ProjectContext, SonarCliError


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


def test_parse_args_builds_command_table_and_normalizes_global_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "manage_sonar_findings.py",
            "summary",
            "--page-size",
            "10",
            "--repo",
            ".",
            "--json",
        ],
    )

    args = manage_sonar_findings.parse_args()

    assert args.command == "summary"
    assert args.repo == "."
    assert args.json is True
    assert args.page_size == 10


def test_normalize_global_args_requires_values() -> None:
    with pytest.raises(SonarCliError, match="Missing value"):
        manage_sonar_findings.normalize_global_args(["summary", "--repo"])


def test_command_wrappers_parse_csv_and_key_value_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = make_context(tmp_path)

    def fake_fetch_settings_values(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"settings": []}

    def fake_fetch_settings_definitions(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"definitions": []}

    def fake_direct_api_call(**kwargs: object) -> dict[str, object]:
        del kwargs
        return {"response": "ok"}

    monkeypatch.setattr(
        manage_sonar_findings,
        "fetch_settings_values",
        fake_fetch_settings_values,
    )
    monkeypatch.setattr(
        manage_sonar_findings,
        "fetch_settings_definitions",
        fake_fetch_settings_definitions,
    )
    monkeypatch.setattr(
        manage_sonar_findings,
        "direct_api_call",
        fake_direct_api_call,
    )

    cases: tuple[tuple[str, dict[str, object]], ...] = (
        ("settings-values", {"settings": []}),
        ("settings-definitions", {"definitions": []}),
        ("api-call", {"response": "ok"}),
    )
    for command, expected in cases:
        args = argparse.Namespace(
            command=command,
            component=None,
            endpoint="/api/custom",
            form_params=["body=true"],
            keys=["alpha,beta"],
            method="GET",
            query_params=["ps=1"],
            dry_run=False,
        )

        assert manage_sonar_findings.dispatch_command(args, context) == expected


def test_dispatch_command_rejects_unknown_command(tmp_path: Path) -> None:
    context = make_context(tmp_path)
    args = argparse.Namespace(command="unknown")

    with pytest.raises(SonarCliError, match="Unsupported command"):
        manage_sonar_findings.dispatch_command(args, context)
