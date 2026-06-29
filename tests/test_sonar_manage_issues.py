from __future__ import annotations

# pyright: reportUnusedCallResult=false
from pathlib import Path
from typing import Any

import pytest
import sonar_manage_issues
from sonar_manage_api import ProjectContext, RequestSpec, SonarCliError


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


def test_fetch_issue_and_hotspot_payloads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_api_request(*, context: ProjectContext, spec: RequestSpec) -> dict[str, Any]:
        del context
        if spec.endpoint == "/api/hotspots/search":
            return {"hotspots": [{"key": "HOTSPOT-1"}], "paging": {"total": 1}}
        if spec.endpoint == "/api/hotspots/show":
            assert spec.query is not None
            return {"key": spec.query["hotspot"], "status": "TO_REVIEW"}
        return {"issues": [{"key": "ISSUE-1"}], "total": 1}

    monkeypatch.setattr(sonar_manage_issues, "api_request", fake_api_request)
    context = make_context(tmp_path)

    assert (
        sonar_manage_issues.fetch_issues(
            context=context,
            issue_statuses="OPEN",
            page=1,
            page_size=50,
            extra_query={"types": "BUG"},
        )["total"]
        == 1
    )
    hotspots = sonar_manage_issues.fetch_hotspots(
        context=context,
        hotspot_status="TO_REVIEW",
        page=1,
        page_size=10,
        include_details=True,
        extra_query=None,
    )

    assert hotspots["details"] == [{"key": "HOTSPOT-1", "status": "TO_REVIEW"}]


def test_issue_mutations_support_dry_run_and_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_api_request(*, context: ProjectContext, spec: RequestSpec) -> dict[str, Any]:
        del context
        if spec.method == "GET":
            return {
                "issues": [
                    {
                        "status": "OPEN",
                        "resolution": None,
                        "type": "BUG",
                        "severity": "MAJOR",
                        "component": "src/app.py",
                        "line": 1,
                        "message": "message",
                        "tags": ["triaged"],
                    }
                ]
            }
        return {}

    monkeypatch.setattr(sonar_manage_issues, "api_request", fake_api_request)
    context = make_context(tmp_path)

    assert (
        sonar_manage_issues.add_issue_comment(
            context=context,
            issue_key="ISSUE-1",
            text="reviewed",
            dry_run=True,
        )["result"]["endpoint"]
        == "/api/issues/add_comment"
    )
    assert (
        sonar_manage_issues.assign_issue(
            context=context,
            issue_key="ISSUE-1",
            assignee="nick",
            dry_run=False,
        )["status"]
        == "OPEN"
    )
    assert sonar_manage_issues.set_issue_tags(
        context=context,
        issue_key="ISSUE-1",
        tags=["triaged"],
        dry_run=False,
    )["tags"] == ["triaged"]
    assert (
        sonar_manage_issues.transition_issues(
            context=context,
            issue_keys=["ISSUE-1"],
            transition="resolve",
            comment="fixed",
            dry_run=True,
        )["results"][0]["endpoint"]
        == "/api/issues/do_transition"
    )

    with pytest.raises(SonarCliError, match="--text"):
        sonar_manage_issues.add_issue_comment(
            context=context,
            issue_key="ISSUE-1",
            text=" ",
            dry_run=False,
        )


def test_hotspot_helpers_and_review(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_api_request(*, context: ProjectContext, spec: RequestSpec) -> dict[str, Any]:
        del context
        if spec.endpoint == "/api/hotspots/show":
            return {"status": "REVIEWED", "line": 10, "message": "message"}
        return {}

    monkeypatch.setattr(sonar_manage_issues, "api_request", fake_api_request)
    context = make_context(tmp_path)

    assert sonar_manage_issues.hotspot_keys_from_items([{"key": "HOTSPOT-1"}, {"missing": True}, "bad"]) == [
        "HOTSPOT-1"
    ]
    assert sonar_manage_issues.fetch_hotspot_details(
        context=context,
        hotspots=[{"key": "HOTSPOT-1"}],
    ) == [{"status": "REVIEWED", "line": 10, "message": "message"}]
    assert (
        sonar_manage_issues.review_hotspots(
            context=context,
            hotspot_keys=["HOTSPOT-1"],
            status="REVIEWED",
            resolution="SAFE",
            comment="safe",
            dry_run=False,
        )["results"][0]["resolution"]
        == "SAFE"
    )

    with pytest.raises(SonarCliError, match="--status"):
        sonar_manage_issues.review_hotspots(
            context=context,
            hotspot_keys=["HOTSPOT-1"],
            status=" ",
            resolution="SAFE",
            comment=None,
            dry_run=True,
        )
