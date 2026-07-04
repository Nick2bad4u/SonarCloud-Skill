# SonarCloud Skill

[![latest GitHub release.](https://flat.badgen.net/github/release/Nick2bad4u/SonarCloud-Skill?color=cyan)](https://github.com/Nick2bad4u/SonarCloud-Skill/releases) [![GitHub stars.](https://flat.badgen.net/github/stars/Nick2bad4u/SonarCloud-Skill?color=yellow)](https://github.com/Nick2bad4u/SonarCloud-Skill/stargazers) [![GitHub forks.](https://flat.badgen.net/github/forks/Nick2bad4u/SonarCloud-Skill?color=green)](https://github.com/Nick2bad4u/SonarCloud-Skill/forks) [![GitHub open issues.](https://flat.badgen.net/github/open-issues/Nick2bad4u/SonarCloud-Skill?color=red)](https://github.com/Nick2bad4u/SonarCloud-Skill/issues) [![GitHub PRs.](https://flat.badgen.net/github/open-prs/Nick2bad4u/SonarCloud-Skill?color=orange)](https://github.com/Nick2bad4u/SonarCloud-Skill/pulls?q=sort%3Aupdated-desc+is%3Apr+is%3Aopen) [![GitHub license](https://flat.badgen.net/github/license/Nick2bad4u/SonarCloud-Skill?color=purple)](https://github.com/Nick2bad4u/SonarCloud-Skill/blob/main/LICENSE) [![GitHub Dependabot](https://flat.badgen.net/github/dependabot/Nick2bad4u/SonarCloud-Skill?color=blue)](https://github.com/Nick2bad4u/SonarCloud-Skill/network/updates) 

An open-agent skill for inspecting and managing **SonarCloud** and **SonarQube** findings.

This repository provides:

- a reusable `sonar-manage-findings` skill (`skills/sonar-manage-findings/SKILL.md`)
- a Python CLI helper to query and triage project findings
- GitHub automation for security/scanning hygiene

---

## What this skill can do

With a Sonar token in an environment variable, you can:

- summarize project quality state (issues, hotspots, quality gate, selected metrics)
- list and inspect issues/hotspots
- comment, assign, retag, and transition issues (`resolve`, `wontfix`, `falsepositive`, etc.)
- review hotspots (`SAFE`, `FIXED`, etc.)
- inspect measures, measure history, analyses, and Compute Engine tasks
- inspect or mutate project settings, quality gate/profile association, and project tags
- fall back to direct API calls for unsupported endpoints

> The helper is repository-agnostic: pass `--repo` to any local checkout, or pass explicit `--project-key` / `--base-url`.

---

## Repository layout

```text
skills/
  sonar-manage-findings/
    SKILL.md
    LICENSE.txt
    agents/
      openai.yaml
    assets/
      sonar-manage-findings-small.svg
      sonar-manage-findings.png
    references/
      command-guide.md
    scripts/
      manage_sonar_findings.py
      sonar_manage_api.py
      sonar_manage_common.py
      sonar_manage_diagnostics.py
      sonar_manage_issues.py
      sonar_manage_project.py
      sonar_manage_render.py
README.md
CONTRIBUTING.md
SECURITY.md
CHANGELOG.md
```

---

## Agent compatibility

This package uses the `skills/sonar-manage-findings/` layout so `npx skills` can discover the full skill payload, including its `agents/`, `assets/`, `references/`, and `scripts/` folders.

Use `--agent universal` for agents that consume the shared `.agents/skills` layout. Use `--agent "*"` only when you intentionally want to install to every supported agent directory.

```powershell
npx skills add Nick2bad4u/SonarCloud-Skill -g --agent universal -y
npx skills add Nick2bad4u/SonarCloud-Skill -g --agent "*" -y
npm install --save-dev sonar-manage-findings-skill
npx skills experimental_sync --agent universal -y
```

OpenAI-specific display metadata lives in `skills/sonar-manage-findings/agents/openai.yaml`. The portable skill contract is `skills/sonar-manage-findings/SKILL.md` plus the referenced `assets/`, `references/`, and `scripts/` files.

---

## Publishing

The skill is packaged for GitHub releases and npm as `sonar-manage-findings-skill`.

Verify the package locally before publishing:

```powershell
npm run release:verify
npm publish --access public --provenance
```

GitHub Actions publishes with npm OIDC trusted publishing using `npm publish --access public --provenance`. Configure the npm package trusted publisher for repository `Nick2bad4u/SonarCloud-Skill` and workflow `.github/workflows/release-skill.yml`. The workflow intentionally does not use `npm stage` commands.

---

## Quick start

### 1) Prerequisites

- Python 3.10+
- A Sonar token exported to an environment variable (recommended: `SONAR_TOKEN`)

### 2) Set your token (do not pass it on CLI)

#### PowerShell

```powershell
$env:SONAR_TOKEN = "<your-token>"
```

#### Bash

```bash
export SONAR_TOKEN="<your-token>"
```

### 3) Run the helper

From repository root:

```powershell
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" summary --repo "."
```

Machine-readable output:

```powershell
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" summary --repo "." --json
```

---

## Common commands

```powershell
# List open/reopened issues
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" list-issues --repo "." --issue-statuses OPEN,CONFIRMED,REOPENED

# Show issue activity
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" issue-changelog --repo "." --issue AZ123

# Resolve an issue (dry-run first)
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" transition-issue --repo "." --issue AZ123 --transition resolve --comment "Fixed in code." --dry-run

# List hotspots awaiting review
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" list-hotspots --repo "." --hotspot-status TO_REVIEW --include-details

# Check quality gate
python "skills/sonar-manage-findings/scripts/manage_sonar_findings.py" quality-gate-status --repo "."
```

For the full command surface and workflows, see:

- `skills/sonar-manage-findings/SKILL.md`

---

## Security notes

- Never paste tokens into command arguments or commit them to git.
- Prefer environment variables and secret managers.
- Use `--dry-run` before bulk mutation actions.

More details: [`SECURITY.md`](./SECURITY.md)

---

## Contributing

Contributions are welcome. Please read:

- [`CONTRIBUTING.md`](./CONTRIBUTING.md)
- [`CHANGELOG.md`](./CHANGELOG.md)

---

## Releases and downloads

This repository includes a release workflow that creates a downloadable zip bundle:

- Workflow: `.github/workflows/release-skill.yml`
- Trigger:
  - push a tag like `v0.1.0`
  - run manually via **workflow_dispatch** with:
    - `release_type`: `patch` / `minor` / `major`
    - `version`: optional explicit `x.y.z` (overrides `release_type`)
    - `ref`: branch to release from (default `main`)
- Asset: `sonarcloud-skill-<tag>.zip`

Examples:

```powershell
# Manual patch bump from main
gh workflow run "Release Skill Bundle" -f release_type=patch -f ref=main

# Manual explicit release version
gh workflow run "Release Skill Bundle" -f release_type=patch -f version=0.2.0 -f ref=main
```

---

## License

Released under [The Unlicense](./LICENSE).
