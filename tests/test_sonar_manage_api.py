from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / "scripts" / "sonar_manage_api.py"

spec = importlib.util.spec_from_file_location("sonar_manage_api", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load {SCRIPT_PATH}")
sonar_manage_api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = sonar_manage_api
spec.loader.exec_module(sonar_manage_api)


class SonarManageApiTests(unittest.TestCase):
    def test_absolute_endpoint_must_match_base_url_origin(self) -> None:
        with self.assertRaises(sonar_manage_api.SonarCliError):
            sonar_manage_api.build_url(
                "https://sonarcloud.io",
                "https://example.invalid/api/issues/search",
                None,
            )

    def test_absolute_endpoint_on_base_url_origin_still_works(self) -> None:
        self.assertEqual(
            sonar_manage_api.build_url(
                "https://api.sonarcloud.io",
                "https://api.sonarcloud.io/quality-gates",
                {"organization": "acme"},
            ),
            "https://api.sonarcloud.io/quality-gates?organization=acme",
        )

    def test_relative_endpoint_still_uses_configured_base_url(self) -> None:
        self.assertEqual(
            sonar_manage_api.build_url(
                "https://api.sonarcloud.io",
                "/quality-gates",
                {"organization": "acme"},
            ),
            "https://api.sonarcloud.io/quality-gates?organization=acme",
        )

    def test_resolve_repo_root_walks_to_git_directory_without_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            nested = root / "packages" / "example"
            nested.mkdir(parents=True)
            (root / ".git").mkdir()

            self.assertEqual(
                sonar_manage_api.resolve_repo_root(nested),
                root,
            )

    def test_api_error_details_are_marked_untrusted(self) -> None:
        self.assertEqual(
            sonar_manage_api.mark_untrusted_api_text(
                "line one\nline two with instructions",
            ),
            "[untrusted-sonar-text] line one line two with instructions",
        )


if __name__ == "__main__":
    unittest.main()
