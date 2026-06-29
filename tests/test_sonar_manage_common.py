from __future__ import annotations

# pyright: reportUnusedCallResult=false
from pathlib import Path

import pytest
from sonar_manage_api import ProjectContext, RequestSpec, SonarCliError
from sonar_manage_common import (
    build_dry_run_payload,
    build_dry_run_result,
    extract_issue_state,
    normalize_keys,
    parse_name_value_pairs,
    resolve_csv_values,
    resolve_tag_values,
)


def make_context(tmp_path: Path) -> ProjectContext:
    return ProjectContext(
        repo_root=tmp_path,
        project_key="project-key",
        organization=None,
        base_url="https://sonarcloud.io",
        token="token",
        token_env_name="SONAR_TOKEN",
        auth_scheme="auto",
        sonar_properties_path=None,
    )


def test_normalize_keys_rejects_empty_values() -> None:
    with pytest.raises(SonarCliError, match="At least one --issue"):
        normalize_keys([" ", ""], argument_name="issue")


def test_parse_name_value_pairs_validates_shape() -> None:
    assert parse_name_value_pairs(["one=1", "two = 2"], argument_name="query-param") == {
        "one": "1",
        "two": "2",
    }

    with pytest.raises(SonarCliError, match="Expected key=value"):
        parse_name_value_pairs(["broken"], argument_name="query-param")

    with pytest.raises(SonarCliError, match="Empty key"):
        parse_name_value_pairs(["=value"], argument_name="query-param")


def test_resolve_csv_and_tag_values() -> None:
    assert resolve_csv_values(["one,two", " three "], argument_name="tag") == [
        "one",
        "two",
        "three",
    ]
    assert resolve_tag_values(None, clear=True, argument_name="tag") == []

    with pytest.raises(SonarCliError, match="Provide at least one --tag"):
        resolve_tag_values(None, clear=False, argument_name="tag")


def test_extract_issue_state_validates_payload_shape() -> None:
    assert extract_issue_state(
        {
            "issues": [
                {
                    "status": "OPEN",
                    "resolution": None,
                    "type": "BUG",
                    "severity": "MAJOR",
                    "component": "src/app.py",
                    "line": 10,
                    "message": "message",
                    "tags": ["tag"],
                }
            ]
        },
        "ISSUE-1",
    ) == {
        "issue": "ISSUE-1",
        "status": "OPEN",
        "resolution": None,
        "type": "BUG",
        "severity": "MAJOR",
        "component": "src/app.py",
        "line": 10,
        "message": "message",
        "tags": ["tag"],
    }

    with pytest.raises(SonarCliError, match="Unexpected issue state"):
        extract_issue_state([], "ISSUE-1")

    with pytest.raises(SonarCliError, match="No issue details"):
        extract_issue_state({"issues": []}, "ISSUE-1")


def test_build_dry_run_payload(tmp_path: Path) -> None:
    request_spec = RequestSpec(
        method="POST",
        endpoint="/api/settings/set",
        form={"key": "value"},
    )

    assert build_dry_run_result(description="Set setting", request_spec=request_spec) == {
        "description": "Set setting",
        "method": "POST",
        "endpoint": "/api/settings/set",
        "query": None,
        "form": {"key": "value"},
        "dryRun": True,
    }
    assert (
        build_dry_run_payload(
            context=make_context(tmp_path),
            description="Set setting",
            request_spec=request_spec,
        )["projectKey"]
        == "project-key"
    )
