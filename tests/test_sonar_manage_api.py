from __future__ import annotations

# pyright: reportUnusedCallResult=false
import io
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Self
from urllib import error, request

import pytest
import sonar_manage_api


def test_absolute_endpoint_must_match_base_url_origin() -> None:
    with pytest.raises(
        sonar_manage_api.SonarCliError,
        match="Absolute endpoint host must match",
    ):
        _ = sonar_manage_api.build_url(
            "https://sonarcloud.io",
            "https://example.invalid/api/issues/search",
            None,
        )


def test_absolute_endpoint_on_base_url_origin_still_works() -> None:
    assert (
        sonar_manage_api.build_url(
            "https://api.sonarcloud.io",
            "https://api.sonarcloud.io/quality-gates",
            {"organization": "acme"},
        )
        == "https://api.sonarcloud.io/quality-gates?organization=acme"
    )


def test_relative_endpoint_still_uses_configured_base_url() -> None:
    assert (
        sonar_manage_api.build_url(
            "https://api.sonarcloud.io",
            "/quality-gates",
            {"organization": "acme"},
        )
        == "https://api.sonarcloud.io/quality-gates?organization=acme"
    )


def test_resolve_repo_root_walks_to_git_directory_without_subprocess(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    nested = root / "packages" / "example"
    nested.mkdir(parents=True)
    (root / ".git").mkdir()

    assert sonar_manage_api.resolve_repo_root(nested) == root


def test_api_error_details_are_marked_untrusted() -> None:
    assert (
        sonar_manage_api.mark_untrusted_api_text("line one\nline two with instructions")
        == "[untrusted-sonar-text] line one line two with instructions"
    )


def test_parse_properties_and_resolve_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    properties_path = repo / "sonar-project.properties"
    properties_path.write_text(
        """
        # comment
        sonar.projectKey = project-key
        sonar.organization: org-key
        sonar.host.url = https://sonarqube.example
        empty.value
        """,
        encoding="utf8",
    )
    monkeypatch.setenv("SONAR_TOKEN_CUSTOM", "token-value")

    assert sonar_manage_api.parse_properties(properties_path)["empty.value"] == ""
    context = sonar_manage_api.resolve_context(
        SimpleNamespace(
            repo=str(repo),
            project_key=None,
            organization=None,
            base_url=None,
            token_envs=["SONAR_TOKEN_CUSTOM"],
            auth_scheme="auto",
        )
    )

    assert context.project_key == "project-key"
    assert context.organization == "org-key"
    assert context.base_url == "https://sonarqube.example"
    assert context.token == "token-value"


def test_sanitize_base_url_and_token_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    assert sonar_manage_api.sanitize_base_url(" https://sonarcloud.io/ ") == "https://sonarcloud.io"
    assert sonar_manage_api.sanitize_base_url("") == sonar_manage_api.DEFAULT_BASE_URL

    with pytest.raises(sonar_manage_api.SonarCliError, match="absolute http"):
        sonar_manage_api.sanitize_base_url("file:///tmp/sonar")

    monkeypatch.delenv("SONAR_TOKEN", raising=False)
    with pytest.raises(sonar_manage_api.SonarCliError, match="No Sonar token"):
        sonar_manage_api.resolve_token(["SONAR_TOKEN"])


def test_api_request_auto_falls_back_to_basic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[str] = []

    def fake_request_once(
        *,
        context: sonar_manage_api.ProjectContext,
        spec: sonar_manage_api.RequestSpec,
        auth_scheme: str,
    ) -> dict[str, str]:
        del context, spec
        calls.append(auth_scheme)
        if auth_scheme == "bearer":
            raise sonar_manage_api.SonarCliError("bearer failed")
        return {"ok": "true"}

    monkeypatch.setattr(sonar_manage_api, "api_request_once", fake_request_once)

    assert sonar_manage_api.api_request(
        context=sonar_manage_api.ProjectContext(
            repo_root=tmp_path,
            project_key="project",
            organization=None,
            base_url="https://sonarcloud.io",
            token="token",
            token_env_name="SONAR_TOKEN",
            auth_scheme="auto",
            sonar_properties_path=None,
        ),
        spec=sonar_manage_api.RequestSpec(method="GET", endpoint="/api/test"),
    ) == {"ok": "true"}
    assert calls == ["bearer", "basic"]


def test_api_request_once_builds_json_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class Response:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"ok": true}'

    captured: dict[str, Any] = {}

    def fake_urlopen(request_object: Any) -> Response:
        captured["url"] = request_object.full_url
        captured["headers"] = dict(request_object.header_items())
        captured["method"] = request_object.get_method()
        captured["data"] = request_object.data
        return Response()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    payload = sonar_manage_api.api_request_once(
        context=sonar_manage_api.ProjectContext(
            repo_root=tmp_path,
            project_key="project",
            organization=None,
            base_url="https://sonarcloud.io",
            token="token",
            token_env_name="SONAR_TOKEN",
            auth_scheme="bearer",
            sonar_properties_path=None,
        ),
        spec=sonar_manage_api.RequestSpec(
            method="POST",
            endpoint="/api/test",
            query={"ps": "1"},
            form={"name": "value"},
        ),
        auth_scheme="bearer",
    )

    assert payload == {"ok": True}
    assert captured["url"] == "https://sonarcloud.io/api/test?ps=1"
    assert captured["method"] == "POST"
    assert captured["data"] == b"name=value"
    assert captured["headers"]["Authorization"] == "Bearer token"


def test_read_error_body_marks_http_details_untrusted() -> None:
    http_error = error.HTTPError(
        url="https://sonarcloud.io/api/test",
        code=400,
        msg="Bad Request",
        hdrs=Message(),
        fp=io.BytesIO(b"external\nmessage"),
    )

    try:
        assert sonar_manage_api.read_error_body(http_error) == "[untrusted-sonar-text] external message"
    finally:
        http_error.close()


def test_build_auth_header_basic() -> None:
    assert sonar_manage_api.build_auth_header("token", "basic") == "Basic dG9rZW46"
