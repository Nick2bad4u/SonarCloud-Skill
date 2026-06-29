# Sonar Manage Findings Command Guide

Use this reference after loading `SKILL.md` when you need command-specific syntax.

All examples assume a Sonar token is already available through `SONAR_TOKEN` or a variable passed with `--token-env`.

## Global Options

- `--repo`: path inside the target repository, default `.`.
- `--project-key`: explicit Sonar project key when `sonar-project.properties` is unavailable.
- `--organization`: explicit Sonar organization key.
- `--base-url`: SonarCloud or SonarQube base URL.
- `--token-env`: token environment variable name. Repeat for fallbacks.
- `--auth-scheme`: `auto`, `bearer`, or `basic`.
- `--json`: emit machine-readable output.

## Inspection

```powershell
python "<path-to-skill>/scripts/manage_sonar_findings.py" summary --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" list-issues --repo "." --page-size 100
python "<path-to-skill>/scripts/manage_sonar_findings.py" issue-changelog --repo "." --issue AZ123 --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" list-hotspots --repo "." --include-details --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" show-hotspot --repo "." --hotspot AZ999 --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" measures --repo "." --metric alert_status --metric coverage --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" measures-history --repo "." --metric coverage --from-date 2026-03-01 --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" project-info --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" ce-component --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" ce-task --repo "." --task-id AX123 --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" project-analyses --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" tsconfig-warning-check --repo "." --json
```

## Issue Mutations

Dry-run first unless the user has already approved the exact mutation.

```powershell
python "<path-to-skill>/scripts/manage_sonar_findings.py" comment-issue --repo "." --issue AZ123 --text "Reviewed during release hardening." --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" assign-issue --repo "." --issue AZ123 --assignee "Nick2bad4u@github" --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" set-issue-tags --repo "." --issue AZ123 --tag security --tag workflow --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" set-issue-tags --repo "." --issue AZ123 --clear --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" transition-issue --repo "." --issue AZ123 --transition resolve --comment "Fixed in code." --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" transition-issue --repo "." --issue AZ123 --transition falsepositive --comment "Reviewed as a false positive in this context." --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" transition-issue --repo "." --issue AZ123 --transition wontfix --comment "Accepted technical debt." --dry-run
```

## Hotspot Mutations

Review the code path before marking a hotspot safe or fixed.

```powershell
python "<path-to-skill>/scripts/manage_sonar_findings.py" review-hotspot --repo "." --hotspot AZ999 --status REVIEWED --resolution SAFE --comment "Reviewed as safe in this context." --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" review-hotspot --repo "." --hotspot AZ999 --status REVIEWED --resolution FIXED --comment "Fixed in code." --dry-run
```

## Quality Gates And Profiles

```powershell
python "<path-to-skill>/scripts/manage_sonar_findings.py" quality-gate-status --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" list-quality-gates --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" get-quality-gate --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" set-quality-gate --repo "." --gate-name "Sonar way" --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" unset-quality-gate --repo "." --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" list-quality-profiles --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" quality-profile-changelog --repo "." --quality-profile <profile-key> --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" set-quality-profile --repo "." --quality-profile <profile-key> --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" unset-quality-profile --repo "." --quality-profile <profile-key> --dry-run
```

## Settings And Tags

```powershell
python "<path-to-skill>/scripts/manage_sonar_findings.py" settings-values --repo "." --key sonar.typescript.tsconfigPaths --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" settings-definitions --repo "." --key sonar.typescript.tsconfigPaths --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" settings-set --repo "." --key sonar.typescript.tsconfigPaths --value tsconfig.json --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" settings-reset --repo "." --key sonar.typescript.tsconfigPaths --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" search-project-tags --repo "." --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" set-project-tags --repo "." --tag quality --tag typescript --dry-run
python "<path-to-skill>/scripts/manage_sonar_findings.py" set-project-tags --repo "." --clear --dry-run
```

## Raw API Fallback

Prefer wrapped commands when available. Use `api-call` for gaps, with relative endpoints when possible.

```powershell
python "<path-to-skill>/scripts/manage_sonar_findings.py" api-call --repo "." --endpoint /api/issues/search --query-param componentKeys=MyOrg_MyProject --query-param ps=1 --json
python "<path-to-skill>/scripts/manage_sonar_findings.py" api-call --base-url https://api.sonarcloud.io --endpoint /quality-gates --method GET --json
```
